"""Consulta trazable y sin persistir secretos de la API de Indicadores INEGI."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_BASE = "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR"


def codigo_municipal(cve_ent: str, cve_mun: str) -> str:
    """Construye la clave INEGI de cinco dígitos sin inferirla del nombre."""
    if not re.fullmatch(r"\d{1,2}", cve_ent) or not re.fullmatch(r"\d{1,3}", cve_mun):
        raise ValueError("cve_ent debe tener uno o dos dígitos y cve_mun uno a tres.")
    return f"{cve_ent.zfill(2)}{cve_mun.zfill(3)}"


def _url(indicador: str, area: str, source: str, version: str, token: str) -> str:
    return f"{API_BASE}/{quote(indicador, safe='')}/es/{quote(area, safe='')}/false/{quote(source, safe='')}/{quote(version, safe='')}/{quote(token, safe='')}?type=json"


def _url_redactada(indicador: str, area: str, source: str, version: str) -> str:
    return f"{API_BASE}/{indicador}/es/{area}/false/{source}/{version}/[TOKEN_REDACTED]?type=json"


def _decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _obtener_json(url: str, timeout: float, opener=urlopen) -> tuple[dict[str, object], bytes]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "pipeline-seguridad-municipios/1.0"})
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as error:
        # No incluir str(error): contiene la URL, cuyo path lleva el token.
        raise RuntimeError(f"INEGI devolvió HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError(f"No fue posible conectar con INEGI: {error.reason}.") from error
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("INEGI respondió un JSON inválido.") from error
    if not isinstance(parsed, dict):
        raise ValueError("INEGI respondió una estructura no reconocida.")
    return parsed, raw


def _serie_poblacion(payload: dict[str, object], indicador: str, area: str) -> tuple[dict[int, Decimal], dict[str, object]]:
    series = payload.get("Series")
    if not isinstance(series, list) or len(series) != 1 or not isinstance(series[0], dict):
        raise ValueError(f"INEGI no devolvió una serie única para el indicador {indicador} y área {area}.")
    source = series[0]
    if str(source.get("INDICADOR")) != indicador:
        raise ValueError("INEGI devolvió un indicador distinto al solicitado.")
    observations = source.get("OBSERVATIONS")
    if not isinstance(observations, list):
        raise ValueError("INEGI no devolvió observaciones para la serie solicitada.")
    values: dict[int, Decimal] = {}
    excluded: list[dict[str, str]] = []
    for observation in observations:
        if not isinstance(observation, dict):
            raise ValueError("INEGI devolvió una observación no reconocida.")
        period = str(observation.get("TIME_PERIOD", ""))
        if not re.fullmatch(r"\d{4}", period):
            excluded.append({"periodo": period, "motivo": "Periodo no anual"})
            continue
        value = _decimal(observation.get("OBS_VALUE"))
        if value is None or value < 0 or observation.get("OBS_EXCEPTION"):
            excluded.append({"periodo": period, "motivo": "Valor ausente, inválido o excepcional"})
            continue
        year = int(period)
        if year in values:
            raise ValueError(f"INEGI devolvió un año duplicado ({year}) para el área {area}.")
        values[year] = value
    if not values:
        raise ValueError(f"INEGI no devolvió población anual utilizable para el área {area}.")
    metadata = {key.lower(): source.get(key) for key in ("INDICADOR", "FREQ", "TOPIC", "UNIT", "UNIT_MULT", "NOTE", "SOURCE", "LASTUPDATE", "STATUS")}
    metadata["observaciones_excluidas"] = excluded
    return values, metadata


def consultar_poblacion(
    *, token: str, cve_ent: str, cve_mun: str, definition: dict[str, object], timeout: float = 30.0, opener=urlopen
) -> tuple[dict[str, dict[int, Decimal]], dict[str, object], dict[str, bytes]]:
    """Obtiene población municipal y estatal, dejando el token fuera de la evidencia."""
    if not token.strip():
        raise ValueError("Falta INEGI_TOKEN; no se acepta un token en argumentos ni archivos.")
    if timeout <= 0:
        raise ValueError("El tiempo de espera de INEGI debe ser positivo.")
    indicator = str(definition["indicador_id"])
    source = str(definition["fuente_datos"])
    version = str(definition["version"])
    areas = {"municipal": codigo_municipal(cve_ent, cve_mun), "estatal": cve_ent.zfill(2)}
    result: dict[str, dict[int, Decimal]] = {}
    queries = []
    responses: dict[str, bytes] = {}
    for scope, area in areas.items():
        payload, raw = _obtener_json(_url(indicator, area, source, version, token), timeout, opener)
        values, metadata = _serie_poblacion(payload, indicator, area)
        result[f"poblacion_{scope}"] = values
        responses[scope] = raw
        queries.append({
            "ambito": scope,
            "area_geografica": area,
            "url_sin_secreto": _url_redactada(indicator, area, source, version),
            "respuesta_sha256": hashlib.sha256(raw).hexdigest(),
            "metadatos_serie": metadata,
            "años_recibidos": sorted(values),
        })
    provenance = {
        "proveedor": definition["proveedor"],
        "pagina_oficial": definition["pagina_oficial"],
        "indicador_id": indicator,
        "descripcion_indicador": definition["descripcion_indicador"],
        "fuente_datos": source,
        "version_api": version,
        "consultado_en_utc": datetime.now(timezone.utc).isoformat(),
        "consultas": queries,
    }
    return result, provenance, responses


def guardar_respuestas(responses: dict[str, bytes], directory: Path, run: str, cve_ent: str, cve_mun: str) -> dict[str, str]:
    """Conserva las respuestas originales de la API en archivos ignorados por Git."""
    directory.mkdir(parents=True, exist_ok=True)
    codes = {"municipal": codigo_municipal(cve_ent, cve_mun), "estatal": cve_ent.zfill(2)}
    paths = {}
    for scope, raw in responses.items():
        path = directory / f"inegi_poblacion_{scope}_{codes[scope]}_{run}.json"
        temporary = path.with_suffix(".json.tmp")
        try:
            with temporary.open("xb") as target:
                target.write(raw)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        paths[scope] = str(path)
    return paths
