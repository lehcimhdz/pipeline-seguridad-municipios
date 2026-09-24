#!/usr/bin/env python3
"""Separa marcadores repetidos cuyo valor depende de su posición en el Word."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "diccionario_datos_diagnostico_seguridad_municipal.json"
DOCX_PATH = ROOT / "templates" / "Machote_seguridad_general_con_calificacion.docx"
PART = "word/document.xml"


def marker(key: str) -> str:
    return f"{{{{ {key} }}}}"


def replace_ordered(xml: str, old: str, keys: list[str]) -> str:
    occurrences = 0

    def replacement(_: re.Match[str]) -> str:
        nonlocal occurrences
        if occurrences >= len(keys):
            raise ValueError(f"Hay más apariciones de {old} que claves definidas.")
        value = marker(keys[occurrences])
        occurrences += 1
        return value

    result = re.sub(re.escape(old), replacement, xml)
    if occurrences != len(keys):
        raise ValueError(
            f"Se esperaban {len(keys)} apariciones de {old}; encontradas: {occurrences}."
        )
    return result


def write_docx(xml: str) -> None:
    with zipfile.ZipFile(DOCX_PATH, "r") as source:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False, dir=DOCX_PATH.parent) as temp:
            temporary = Path(temp.name)
        try:
            with zipfile.ZipFile(temporary, "w") as target:
                for item in source.infolist():
                    content = xml.encode("utf-8") if item.filename == PART else source.read(item.filename)
                    target.writestr(item, content)
            shutil.copystat(DOCX_PATH, temporary)
            temporary.replace(DOCX_PATH)
        finally:
            temporary.unlink(missing_ok=True)


def field(key: str, appearances: int, data_type: str, scope: str, description: str) -> dict[str, object]:
    return {
        "marcador": marker(key),
        "apariciones": appearances,
        "tipo_dato": data_type,
        "alcance": scope,
        "debe_contener": description,
    }


def main() -> int:
    dictionary = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    variables = dictionary["variables_documento"]
    for obsolete in (
        "año",
        "insertar_dos_a_tres_parrafos",
        "insertar_analisis_e_intercalar_graficas_y_o_tablas",
    ):
        if obsolete not in variables:
            raise ValueError(f"No existe la variable esperada: {obsolete}.")

    with zipfile.ZipFile(DOCX_PATH, "r") as document:
        xml = document.read(PART).decode("utf-8")

    xml = replace_ordered(
        xml,
        marker("año"),
        [
            "año_deterioro_inicial",
            "año_deterioro_final",
            *[
                key
                for _ in range(5)
                for key in ("año_ultimo_periodo_inicial", "año_ultimo_periodo_final")
            ],
        ],
    )
    xml = replace_ordered(
        xml,
        marker("insertar_dos_a_tres_parrafos"),
        ["resumen_general", "resumen_ultimo_periodo"],
    )
    xml = replace_ordered(
        xml,
        marker("insertar_analisis_e_intercalar_graficas_y_o_tablas"),
        [f"analisis_indicador_{number:02d}" for number in range(1, 19)],
    )

    variables.pop("año")
    variables.pop("insertar_dos_a_tres_parrafos")
    variables.pop("insertar_analisis_e_intercalar_graficas_y_o_tablas")
    variables.update(
        {
            "año_deterioro_inicial": field(
                "año_deterioro_inicial", 1, "integer", "tendencia_deterioro", "Año inicial del deterioro descrito."
            ),
            "año_deterioro_final": field(
                "año_deterioro_final", 1, "integer", "tendencia_deterioro", "Año final del deterioro descrito."
            ),
            "año_ultimo_periodo_inicial": field(
                "año_ultimo_periodo_inicial", 5, "integer", "ultimo_periodo", "Primer año del último periodo analizado."
            ),
            "año_ultimo_periodo_final": field(
                "año_ultimo_periodo_final", 5, "integer", "ultimo_periodo", "Último año del último periodo analizado."
            ),
            "resumen_general": field(
                "resumen_general", 1, "string", "diagnostico_general", "Dos o tres párrafos de interpretación del periodo completo."
            ),
            "resumen_ultimo_periodo": field(
                "resumen_ultimo_periodo", 1, "string", "diagnostico_ultimo_periodo", "Dos o tres párrafos de interpretación del último periodo."
            ),
        }
    )
    for number in range(1, 19):
        key = f"analisis_indicador_{number:02d}"
        variables[key] = field(
            key,
            1,
            "string",
            f"analisis_indicador_{number:02d}",
            f"Análisis y visualizaciones validadas del indicador {number}.",
        )

    dictionary["metadatos"]["cobertura_verificada"]["marcadores_de_variables_unicos"] = len(variables)
    write_docx(xml)
    JSON_PATH.write_text(json.dumps(dictionary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Variables contextualizadas: {len(variables)}; apariciones preservadas: 120.")


if __name__ == "__main__":
    main()
