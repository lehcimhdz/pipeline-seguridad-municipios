#!/usr/bin/env python3
"""Ejecuta la prevalidación y extracción inicial de un paquete municipal."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = (
    " Anexo.docx",
    " PAQUETE SEGURIDAD.docx",
    " PAQUETE GOBIERNO ABIERTO Y BUEN GOBIERNO.docx",
    " PAQUETE DESARROLLO URBANO SOSTENIBLE Y DERECHOS HUMANOS CONEXOS.docx",
)
SECURITY_SUFFIX = " PAQUETE SEGURIDAD.docx"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as document:
        xml = document.read("word/document.xml").decode("utf-8")
    text = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    text = re.sub(r"</w:p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#8217;", "'")
    )


def slug(value: str) -> str:
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def discover(input_dir: Path) -> tuple[str, dict[str, Path]]:
    documents: dict[str, Path] = {}
    prefixes: set[str] = set()
    for suffix in SUFFIXES:
        matches = sorted(input_dir.glob(f"*{suffix}"))
        if len(matches) != 1:
            raise ValueError(
                f"Se requiere exactamente un archivo con el sufijo {suffix!r}; "
                f"encontrados: {len(matches)}."
            )
        document = matches[0]
        documents[suffix] = document
        prefixes.add(document.name[: -len(suffix)])
    if len(prefixes) != 1:
        raise ValueError("Los cuatro documentos no comparten un mismo municipio.")
    return prefixes.pop(), documents


def extract_summary(text: str) -> list[dict[str, object]]:
    section = text.split("Indicador: Plan o programa de protección civil", 1)[0]
    matches = re.findall(r"(?m)^(\d+)\.\s+(.+?)\s*\n([A-ZÁÉÍÓÚÜÑ ]+)\s*$", section)
    if len(matches) != 18:
        raise ValueError(
            "No se pudieron extraer las 18 calificaciones generales del resumen "
            f"de seguridad; encontradas: {len(matches)}."
        )
    return [
        {
            "numero": int(number),
            "nombre": name.strip(),
            "calificacion_general_reportada": rating.strip(),
            "calificacion_ultimo_periodo": None,
            "evidencia": [
                {
                    "fuente": "PAQUETE SEGURIDAD",
                    "ubicacion": "Resumen inicial de indicadores de seguridad",
                    "extracto": f"{number}. {name.strip()} — {rating.strip()}",
                }
            ],
        }
        for number, name, rating in matches
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "input" / "word")
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    arguments = parser.parse_args()

    municipality, documents = discover(arguments.input)
    texts = {suffix: docx_text(path) for suffix, path in documents.items()}
    anexo_text = texts[" Anexo.docx"]
    security_text = texts[SECURITY_SUFFIX]
    identity = re.search(
        r"municipio de\s+(.+?),\s+([A-ZÁÉÍÓÚÜÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]+)",
        anexo_text,
        re.IGNORECASE,
    )
    state = identity.group(2).strip() if identity else None
    indicators = extract_summary(security_text)

    dictionary_path = ROOT / "diccionario_datos_diagnostico_seguridad_municipal.json"
    dictionary = json.loads(dictionary_path.read_text(encoding="utf-8"))
    values = {key: None for key in dictionary["variables_documento"]}
    values.update(
        {
            "municipio": municipality,
            "estado": state,
            "año_inicial": 2014,
            "año_final": 2024,
        }
    )
    unresolved = sorted(key for key, value in values.items() if value is None)
    validations = [
        {
            "nivel": "bloqueante",
            "codigo": "CALIFICACION_ULTIMO_PERIODO_AUSENTE",
            "detalle": (
                "Las cuatro fuentes no contienen una calificación del último "
                "periodo ya calculada para los 18 indicadores."
            ),
        },
        {
            "nivel": "bloqueante",
            "codigo": "VARIABLES_SIN_VALOR_VALIDADO",
            "detalle": f"Quedan sin valor validado {len(unresolved)} variables del machote.",
            "variables": unresolved,
        },
    ]
    result = {
        "version": "1.0",
        "ejecutado_en": datetime.now(timezone.utc).isoformat(),
        "municipio": municipality,
        "estado": state,
        "estado_ejecucion": "requiere_revision",
        "contrato": {
            "diccionario": dictionary_path.name,
            "diccionario_sha256": sha256(dictionary_path),
            "plantilla": "templates/Machote_seguridad_general_con_calificacion.docx",
        },
        "fuentes": [
            {
                "archivo": path.name,
                "rol": (
                    "primaria"
                    if suffix == SECURITY_SUFFIX
                    else "control_cruzado_o_contexto"
                ),
                "sha256": sha256(path),
            }
            for suffix, path in documents.items()
        ],
        "valores_plantilla": values,
        "indicadores": indicators,
        "calculos": {
            "calificacion_general_reportada": "REGULAR",
            "calificacion_ultimo_periodo": None,
        },
        "validaciones": validations,
        "salida_word_generada": False,
    }
    json_dir = arguments.output / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    output_path = json_dir / f"{slug(municipality)}_diagnostico_seguridad_municipal.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"JSON de prevalidación: {output_path}")
    print("Estado: requiere_revision; no se generó Word final.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
