#!/usr/bin/env python3
"""Valida llaves simples, snake_case y la base de SEGURIDAD v3."""
from collections import Counter
import json
import re
import sys
import zipfile
from lxml import etree as ET
from contrato import cargar_contrato, ROOT
from fidelidad_machote import validar as validar_fidelidad

MARKER = re.compile(r'(?<!\{)\{([a-z][a-z0-9_]*)\}(?!\})')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def validar():
    contract = cargar_contrato()
    dictionary = json.loads((ROOT / contract['diccionario']['archivo']).read_text(encoding='utf-8'))
    total = Counter()
    for perfil, entry in contract['plantillas'].items():
        with zipfile.ZipFile(ROOT / entry['archivo']) as archive:
            files = {n: archive.read(n) for n in archive.namelist()}
            if archive.testzip():
                raise ValueError('DOCX dañado.')
            text = ''
            for name in archive.namelist():
                if name.startswith('word/') and name.endswith('.xml'):
                    root = ET.fromstring(archive.read(name))
                    text += ''.join(t.text or '' for t in root.iter(W + 't'))
        found = Counter(MARKER.findall(text))
        expected = {key: value['apariciones_por_documento'][perfil]
                    for key, value in dictionary['variables_documento'].items()
                    if value['apariciones_por_documento'][perfil]}
        if found != Counter(expected):
            raise ValueError(f'{perfil}: marcadores distintos al diccionario.')
        if re.search(r'\[[^\[\]]+\]|\{\{|\}\}', text):
            raise ValueError(f'{perfil}: instrucciones editoriales o marcadores antiguos pendientes.')
        with zipfile.ZipFile(ROOT / entry['origen']) as archive:
            original_files = {n: archive.read(n) for n in archive.namelist()}
        validar_fidelidad(original_files, files, contract['fidelidad'])
        indicators = re.findall(r'\{analisis_indicador_(\d{2})\}', text)
        if indicators != [f'{i:02d}' for i in range(1, 19)]:
            raise ValueError(f'{perfil}: orden de indicadores distinto al contrato.')
        total.update(found)
    for key, entry in dictionary['variables_documento'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', key) or entry['marcador'] != '{' + key + '}':
            raise ValueError(f'Variable no canónica: {key}')
        if total[key] != entry['apariciones']:
            raise ValueError(f'Apariciones inconsistentes: {key}')
    return len(total), sum(total.values())


def main():
    try:
        variables, appearances = validar()
    except (ValueError, OSError, KeyError) as error:
        print(f'Validación fallida: {error}', file=sys.stderr)
        return 1
    print(f'Validación correcta: {variables} variables y {appearances} apariciones en la base de SEGURIDAD v3.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
