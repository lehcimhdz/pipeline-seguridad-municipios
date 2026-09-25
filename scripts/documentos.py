"""Lectura de DOCX con coordenadas estables de párrafo, tabla, fila y celda."""
import hashlib
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def texto(element):
    return ''.join(node.text or '' for node in element.iter(W + 't'))


def leer_docx(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
    blocks = []
    tables = 0
    for position, element in enumerate(root.find(W + 'body'), 1):
        if element.tag == W + 'p':
            blocks.append({'tipo': 'parrafo', 'bloque': position, 'texto': texto(element)})
        elif element.tag == W + 'tbl':
            tables += 1
            rows = [[texto(cell) for cell in row.findall(W + 'tc')]
                    for row in element.findall(W + 'tr')]
            blocks.append({'tipo': 'tabla', 'bloque': position, 'tabla': tables, 'filas': rows})
    return blocks


def seccion_seguridad(blocks):
    active = False
    number = 0
    scope = None
    summary = []
    sections = []
    for block in blocks:
        if block['tipo'] == 'parrafo':
            text = block['texto'].strip()
            if text == 'SEGURIDAD':
                active = True
                continue
            if not active:
                continue
            if text.startswith('DESARROLLO URBANO SOSTENIBLE'):
                break
            if text.startswith('Indicador:'):
                number += 1
                if number > 18:
                    break
                sections.append({'numero': number, 'nombre': text.split(':', 1)[1].strip(), 'tablas': []})
                scope = None
            if text in ('Datos Municipales', 'Datos Estatales'):
                scope = 'municipal' if text == 'Datos Municipales' else 'estatal'
        elif active:
            if number == 0:
                summary = block['filas'][1:]
            else:
                sections[-1]['tablas'].append({**block, 'ambito': scope})
    if len(sections) != 18:
        raise ValueError(f'Se esperaban 18 secciones de seguridad; encontradas: {len(sections)}')
    ratings = {}
    for row in summary:
        match = re.match(r'^(\d+)\.', row[0]) if row else None
        if match and len(row) > 1:
            ratings[int(match[1])] = row[1].strip()
    for section in sections:
        section['calificacion_general_reportada'] = ratings.get(section['numero'])
    return sections


def registros(table):
    headers = table['filas'][0]
    try:
        year_index = headers.index('Año')
    except ValueError:
        return
    for row_number, row in enumerate(table['filas'][1:], 2):
        if not any(cell.strip() for cell in row):
            continue
        record = dict(zip(headers, row))
        year = row[year_index].strip() if year_index < len(row) else ''
        if not re.fullmatch(r'\d{4}', year):
            continue
        yield {'año': int(year), 'celdas': record,
               'tabla': table['tabla'], 'fila': row_number}
