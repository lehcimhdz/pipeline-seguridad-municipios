#!/usr/bin/env python3
"""Comprueba el contrato entre el diccionario de datos y el machote DOCX."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "diccionario_datos_diagnostico_seguridad_municipal.json"
DOCX_PATH = ROOT / "templates" / "Machote_seguridad_general_con_calificacion.docx"
CANONICAL = re.compile(r"\{\{\s*([^{}\s]+)\s*\}\}")
LEGACY = re.compile(r"\[[^\[\]]+\]")


def main() -> int:
    dictionary = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    expected = {
        key: (value["marcador"], value["apariciones"])
        for key, value in dictionary["variables_documento"].items()
    }
    expected_markers = {marker: key for key, (marker, _) in expected.items()}

    with zipfile.ZipFile(DOCX_PATH, "r") as document:
        xml = document.read("word/document.xml").decode("utf-8")

    actual = Counter(CANONICAL.findall(xml))
    errors = []
    for key, (marker, appearances) in expected.items():
        if marker != f"{{{{ {key} }}}}":
            errors.append(f"{key}: marcador no canónico: {marker}")
        if actual[key] != appearances:
            errors.append(f"{key}: esperadas={appearances}, encontradas={actual[key]}")

    unknown = sorted(set(actual) - set(expected))
    if unknown:
        errors.append("variables no declaradas: " + ", ".join(unknown))

    legacy = sorted(set(LEGACY.findall(xml)))
    declared_non_variables = set()
    for group in dictionary["marcadores_no_tratados_como_variables"].values():
        if "texto" in group:
            declared_non_variables.add(group["texto"])
        declared_non_variables.update(group.get("textos", []))
    unknown_legacy = sorted(set(legacy) - declared_non_variables)
    if unknown_legacy:
        errors.append("marcadores entre corchetes no declarados: " + ", ".join(unknown_legacy))

    if errors:
        print("Validación fallida:", file=sys.stderr)
        print("\n".join("- " + error for error in errors), file=sys.stderr)
        return 1

    print(
        "Validación correcta: "
        f"{len(expected)} variables y {sum(actual.values())} apariciones canónicas."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
