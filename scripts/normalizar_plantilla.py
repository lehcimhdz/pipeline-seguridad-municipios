#!/usr/bin/env python3
"""Migra los marcadores de datos del machote a su contrato canónico.

Los marcadores canónicos tienen la forma ``{{ clave_del_diccionario }}``.
Los textos editoriales entre corchetes no se modifican.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "diccionario_datos_diagnostico_seguridad_municipal.json"
DOCX_PATH = ROOT / "templates" / "Machote_seguridad_general_con_calificacion.docx"
DOCUMENT_XML = "word/document.xml"

# Cada texto es un marcador existente del Word. El valor es la clave canónica
# en variables_documento. Los casos con listas de opciones son intencionales:
# el pipeline selecciona la opción validada y la inserta en el mismo lugar.
LEGACY_MARKERS = {
    "[MUNICIPIO]": "municipio",
    "[ESTADO]": "estado",
    "[AÑO INICIAL]": "año_inicial",
    "[AÑO FINAL]": "año_final",
    "[AÑO]": "año",
    "[AÑOS]": "años",
    "[AÑOS / INDICADORES]": "años_indicadores",
    "[RUBROS]": "rubros",
    "[RUBRO]": "rubro",
    "[CONDICIONES FALTANTES]": "condiciones_faltantes",
    "[N]": "n",
    "[TOTAL]": "total",
    "[INDICADORES]": "indicadores",
    "[INDICADOR]": "indicador",
    "[CAPACIDAD]": "capacidad",
    "[X]": "x",
    "[Y]": "y",
    "[SITUACIÓN INICIAL]": "situacion_inicial",
    "[SITUACIÓN FINAL]": "situacion_final",
    "[CAMBIO DE ADMINISTRACIÓN / FIN DE UN SUBSIDIO / OTRO]": "cambio_administracion_fin_subsidio_otro",
    "[NIVEL]": "nivel",
    "[igual / superior]": "comparacion_con_periodo_completo",
    "[igual / superior / inferior]": "comparacion_con_periodo_completo",
    "[igual / inferior]": "comparacion_con_periodo_completo",
    "[DIMENSIÓN]": "dimension",
    "[DIMENSIONES]": "dimensiones",
    "[TEMAS]": "temas",
    "[TEMAS FALTANTES]": "temas_faltantes",
    "[existe programa, pero no hubo capacitación / hubo capacitación, pero no hay programa vigente]": "situacion_programa_capacitacion",
    "[la dotación es incompleta / la capacitación no tiene continuidad / el estado de fuerza apenas alcanza para cubrir turnos]": "situacion_desempeno_personal",
    "[parte del personal no tiene control de confianza o CUP vigente / el estado de fuerza está por debajo del mínimo / no hay equipo de protección suficiente]": "carencia_relevante",
    "[personal sin certificación / sin equipo de protección / sin capacitación / sin datos]": "condicion_critica",
    "[HERRAMIENTA]": "herramienta",
    "[INDICADORES DE EFICIENCIA]": "indicadores_de_eficiencia",
    "[cámaras / registro de llamadas]": "herramienta_aislada",
    "[las puestas a disposición no guardan relación con la incidencia / se registraron fallecimientos de policías / no hay informe de resultados]": "problema_critico",
    "[INDICADORES CON 4 O 5]": "indicadores_con_4_o_5",
    "[INDICADORES CON 1 O 2]": "indicadores_con_1_o_2",
    "[por encima de / al nivel de]": "posicion_relativa",
    "[ESTÁNDAR]": "estandar",
    "[la protección ante desastres / las condiciones de los policías / la capacidad de prevenir el delito]": "dimension_con_carencias",
    "[INSERTAR DE DOS A TRES PÁRRAFOS]": "insertar_dos_a_tres_parrafos",
    "[INSERTAR ANÁLISIS E INTERCALAR GRÁFICAS Y/O TABLAS]": "insertar_analisis_e_intercalar_graficas_y_o_tablas",
}


def canonical_marker(key: str) -> str:
    return "{{ " + key + " }}"


def replace_document_xml(xml: str, expected: dict[str, int]) -> str:
    found = Counter()

    # Word dividió este marcador concreto en tres nodos w:t para aplicar formato.
    # Se conserva la estructura y el formato de los nodos; sólo queda el texto
    # canónico en el primero y los dos restantes se vacían.
    split_insert_pattern = re.compile(
        r"\[INSERTAR DE DOS A TRES P(</w:t>.*?<w:t>)Á(</w:t>.*?<w:t>)RRAFOS\]",
        re.DOTALL,
    )

    def replace_split_insert(match: re.Match[str]) -> str:
        found["insertar_dos_a_tres_parrafos"] += 1
        return canonical_marker("insertar_dos_a_tres_parrafos") + match.group(1) + match.group(2)

    xml, replacements = split_insert_pattern.subn(replace_split_insert, xml)
    if replacements != found["insertar_dos_a_tres_parrafos"]:
        raise ValueError("No se pudieron sustituir de forma segura los bloques de párrafos.")

    for legacy, key in LEGACY_MARKERS.items():
        occurrences = xml.count(legacy)
        if occurrences:
            found[key] += occurrences
            xml = xml.replace(legacy, canonical_marker(key))

    missing_mappings = set(expected) - set(LEGACY_MARKERS.values())
    if missing_mappings:
        raise ValueError(f"Faltan mapeos para: {', '.join(sorted(missing_mappings))}")

    incorrect = {
        key: (expected[key], found[key])
        for key in expected
        if expected[key] != found[key]
    }
    if incorrect:
        detail = "; ".join(
            f"{key}: esperadas={wanted}, encontradas={actual}"
            for key, (wanted, actual) in sorted(incorrect.items())
        )
        raise ValueError("Las frecuencias del Word no coinciden con el diccionario: " + detail)
    return xml


def write_docx_with_xml(xml: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False, dir=DOCX_PATH.parent) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        with zipfile.ZipFile(DOCX_PATH, "r") as source, zipfile.ZipFile(temp_path, "w") as target:
            for item in source.infolist():
                content = xml.encode("utf-8") if item.filename == DOCUMENT_XML else source.read(item.filename)
                target.writestr(item, content)
        shutil.copystat(DOCX_PATH, temp_path)
        temp_path.replace(DOCX_PATH)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    dictionary = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    variables = dictionary["variables_documento"]
    expected = {key: value["apariciones"] for key, value in variables.items()}

    with zipfile.ZipFile(DOCX_PATH, "r") as document:
        xml = document.read(DOCUMENT_XML).decode("utf-8")

    migrated_xml = replace_document_xml(xml, expected)
    for key, value in variables.items():
        value["marcador"] = canonical_marker(key)

    write_docx_with_xml(migrated_xml)
    JSON_PATH.write_text(
        json.dumps(dictionary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Plantilla normalizada: {len(variables)} variables canónicas.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
