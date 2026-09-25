"""Lectura local, trazable y validada de datos externos ya descargados."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from decimal import Decimal


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def leer_csv(path: Path) -> list[dict[str, str]]:
    sample = path.read_text(encoding="utf-8-sig")[:4096]
    dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source, dialect=dialect))


def fuente(path: Path, definition: dict[str, object]) -> dict[str, object]:
    return {
        "proveedor": definition["proveedor"],
        "pagina_oficial": definition["pagina_oficial"],
        "archivo": str(path),
        "sha256": sha256(path),
        "campos_requeridos": definition["campos_normalizados"],
    }


def validar_campos(rows: list[dict[str, str]], expected: list[str], name: str) -> None:
    if not rows:
        raise ValueError(f"La fuente externa {name} está vacía.")
    missing = set(expected) - set(rows[0])
    if missing:
        raise ValueError(f"La fuente externa {name} no tiene los campos normalizados: {sorted(missing)}.")


def seleccionar(rows: list[dict[str, str]], entity: tuple[str, str], years: set[int]) -> list[dict[str, str]]:
    state_code, municipality_code = entity
    result = []
    for row in rows:
        if row["cve_ent"].zfill(2) != state_code.zfill(2):
            continue
        if row["cve_mun"].zfill(3) != municipality_code.zfill(3):
            continue
        if int(row["año"]) in years:
            result.append(row)
    return result


def decimal(value: str) -> Decimal | None:
    try:
        value = Decimal(value.strip().replace(",", ""))
        return value if value.is_finite() else None
    except Exception:
        return None


def serie(rows: list[dict[str, str]], field: str) -> dict[int, Decimal]:
    result = {}
    for row in rows:
        value = decimal(row.get(field, ""))
        if value is None or value < 0:
            raise ValueError(f"Valor inválido para {field} en año {row.get('año')}.")
        year = int(row["año"])
        if year in result:
            raise ValueError(f"Año duplicado en serie externa: {year}.")
        result[year] = value
    return result


def serie_estatal(rows: list[dict[str, str]], state_code: str, field: str) -> dict[int, Decimal]:
    municipal_totals = {}
    published_totals = {}
    for row in rows:
        if row["cve_ent"].zfill(2) != state_code.zfill(2):
            continue
        value = decimal(row.get(field, ""))
        if value is None or value < 0:
            raise ValueError(f"Valor inválido para {field} en año {row.get('año')}.")
        year = int(row["año"])
        if row["cve_mun"].zfill(3) == "000":
            if year in published_totals:
                raise ValueError(f"Total estatal duplicado para el año {year}.")
            published_totals[year] = value
        else:
            municipal_totals[year] = municipal_totals.get(year, Decimal(0)) + value
    return published_totals or municipal_totals
