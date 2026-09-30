#!/usr/bin/env python3
"""Valida el único perfil de medición y su correspondencia con el machote."""
from collections import Counter
import json
import re
import sys
import zipfile
from lxml import etree as ET
from contrato import cargar_contrato, ROOT

MARKER = re.compile(r'(?<!\{)\{([a-z][a-z0-9_]*)\}(?!\})')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def validar():
    contract = cargar_contrato()
    dictionary = json.loads((ROOT / contract['diccionario']['archivo']).read_text(encoding='utf-8'))
    if dictionary['metadatos']['version'] != contract['version']:
        raise ValueError('Versiones de contrato y diccionario incompatibles.')
    total = Counter()
    for perfil, entry in contract['plantillas'].items():
        with zipfile.ZipFile(ROOT / entry['archivo']) as archive:
            if archive.testzip():
                raise ValueError('DOCX dañado.')
            text = ''
            paragraphs = []
            for name in archive.namelist():
                if name.startswith('word/') and name.endswith('.xml'):
                    root = ET.fromstring(archive.read(name))
                    text += ''.join(t.text or '' for t in root.iter(W + 't'))
                    if name == 'word/document.xml':
                        paragraphs = [''.join(t.text or '' for t in p.iter(W + 't')).strip()
                                      for p in root.find(W + 'body') if p.tag == W + 'p']
                        if root.find('.//' + W + 'tbl') is not None:
                            raise ValueError(f'{perfil}: la base narrativa no debe contener tablas.')
        found = Counter(MARKER.findall(text))
        expected = {key: value['apariciones_por_documento'][perfil]
                    for key, value in dictionary['variables_documento'].items()
                    if value['apariciones_por_documento'][perfil]}
        if found != Counter(expected):
            raise ValueError(f'{perfil}: marcadores distintos al diccionario.')
        if re.search(r'\[[^\[\]]+\]|\{\{|\}\}', text) or re.search(r'[{}]', MARKER.sub('', text)):
            raise ValueError(f'{perfil}: instrucciones editoriales o marcadores antiguos pendientes.')
        headings = [value for value in paragraphs if value in contract['titulos_indicadores']]
        if headings != contract['titulos_indicadores']:
            raise ValueError(f'{perfil}: orden de indicadores distinto al contrato.')
        if re.search(r'Indicador \d{2}:|\{(?:graficas|tablas|cierre)_', text):
            raise ValueError(f'{perfil}: contiene bloques de la composición técnica anterior.')
        if any(heading in text for heading in ('GOBIERNO ABIERTO Y BUEN GOBIERNO',
                'DESARROLLO URBANO SOSTENIBLE', 'DESARROLLO SOCIAL', 'DESARROLLO ECONÓMICO')):
            raise ValueError(f'{perfil}: contiene ejes ajenos al estudio de seguridad.')
        total.update(found)
    for key, entry in dictionary['variables_documento'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', key) or entry['marcador'] != '{' + key + '}':
            raise ValueError(f'Variable no canónica: {key}')
        if set(entry['apariciones_por_documento']) != {'medicion'}:
            raise ValueError(f'Variable de un producto fuera de alcance: {key}')
        if entry['tipo_dato'] != 'string' or entry['tipo_contenido'] != 'texto':
            raise ValueError(f'La variable {key} debe ser exclusivamente textual.')
        if total[key] != entry['apariciones']:
            raise ValueError(f'Apariciones inconsistentes: {key}')
    coverage = dictionary['metadatos']['cobertura_verificada']
    if len(total) != 25:
        raise ValueError('El estudio requiere exactamente 25 variables de texto.')
    if (coverage['marcadores_de_variables_unicos'], coverage['apariciones_de_variables']) != (len(total), sum(total.values())):
        raise ValueError('La cobertura declarada del diccionario no coincide con la base.')
    return len(total), sum(total.values())


def main():
    try:
        variables, appearances = validar()
    except (ValueError, OSError, KeyError) as error:
        print(f'Validación fallida: {error}', file=sys.stderr)
        return 1
    print(f'Validación correcta: {variables} variables y {appearances} apariciones en una base de SEGURIDAD.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
