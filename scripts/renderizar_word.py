#!/usr/bin/env python3
"""Renderiza el diagnóstico desde JSON, sin modificar el DOCX de referencia."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4
import zipfile

from lxml import etree as ET

from calificar import agregar
from componer_documento import PERIODOS, decimal_corto
from documentos import sha256

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates/Machote_seguridad_general_con_calificacion.docx'
DICTIONARY = ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json'
RULES = ROOT / 'reglas_calificacion.json'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML = '{http://www.w3.org/XML/1998/namespace}'
NS = {'w': W[1:-1]}
STYLE = 'ContenidoJSON'
MARKER = re.compile(r'\{\{\s*([^{}\s]+)\s*\}\}')
SELECTOR = '[ 1 · 2 · 3 · 4 · 5 ]'
PARSER = ET.XMLParser(resolve_entities=False, no_network=True)


def texto(node):
    return ''.join(t.text or '' for t in node.iter(W + 't'))


def xml_bytes(node):
    return ET.tostring(node, encoding='UTF-8', xml_declaration=True, standalone=True)


def run(value, model=None, generated=True):
    element = ET.Element(W + 'r')
    props = deepcopy(model.find(W + 'rPr')) if model is not None and model.find(W + 'rPr') is not None else ET.Element(W + 'rPr')
    if generated:
        for key in ('rStyle', 'highlight', 'color', 'rFonts'):
            for child in props.findall(W + key):
                props.remove(child)
        props.insert(0, ET.Element(W + 'rFonts', {W + 'ascii': 'Archivo Light', W + 'hAnsi': 'Archivo Light',
                                                   W + 'eastAsia': 'Archivo Light', W + 'cs': 'Archivo Light'}))
        ET.SubElement(props, W + 'color', {W + 'val': '000000'})
        ET.SubElement(props, W + 'highlight', {W + 'val': 'yellow'})
        props.insert(0, ET.Element(W + 'rStyle', {W + 'val': STYLE}))
    element.append(props)
    for i, line in enumerate(str(value).split('\n')):
        if i:
            ET.SubElement(element, W + 'br')
        ET.SubElement(element, W + 't', {XML + 'space': 'preserve'}).text = line
    return element


def parrafo(value, model=None, generated=True):
    p = ET.Element(W + 'p')
    if model is not None and model.find(W + 'pPr') is not None:
        p.append(deepcopy(model.find(W + 'pPr')))
    p.append(run(value, model.find('.//' + W + 'r') if model is not None else None, generated))
    formato_parrafo(p)
    return p


def color_generado(p, color='2F5496'):
    """Aplica la jerarquía azul del machote sin quitar el resaltado amarillo."""
    for r in p.iter(W + 'r'):
        props = r.find(W + 'rPr')
        if props is None:
            continue
        for node in props.findall(W + 'color'):
            props.remove(node)
        props.append(ET.Element(W + 'color', {W + 'val': color}))
    return p


def formato_parrafo(p, compact=False):
    """Conserva fuente/énfasis y ajusta la copia a lectura continua y tablas."""
    props = p.find(W + 'pPr')
    if props is None:
        props = ET.Element(W + 'pPr')
        p.insert(0, props)
    for key in ('spacing', 'ind', 'jc'):
        for child in props.findall(W + key):
            props.remove(child)
    ET.SubElement(props, W + 'spacing', {W + 'before': '0', W + 'after': '40' if compact else '120',
                                        W + 'line': '240' if compact else '276', W + 'lineRule': 'auto'})
    ET.SubElement(props, W + 'jc', {W + 'val': 'left'})


def reemplazar(p, token, replacement, first_only=False):
    """Sustituye marcadores incluso fragmentados; resalta sólo el texto nuevo."""
    while token in texto(p):
        start = texto(p).index(token)
        end = start + len(token)
        runs = list(p.iter(W + 'r'))
        spans = []
        offset = 0
        for r in runs:
            length = len(texto(r))
            if offset < end and offset + length > start:
                spans.append((r, offset, texto(r)))
            offset += length
        if not spans:
            raise ValueError('Marcador sin segmentos de texto editables.')
        parent = spans[0][0].getparent()
        if any(r.getparent() is not parent or any(c.tag not in (W + 'rPr', W + 't') for c in r)
               for r, _, _ in spans):
            raise ValueError(f'El marcador {token!r} cruza estructura compleja del DOCX; requiere revisión.')
        first, first_offset, first_text = spans[0]
        last, last_offset, last_text = spans[-1]
        before = first_text[:start - first_offset]
        after = last_text[end - last_offset:]
        index = parent.index(first)
        nodes = ([run(before, first, False)] if before else []) + [run(replacement, first)]
        if after:
            nodes.append(run(after, last, False))
        for r, _, _ in spans:
            parent.remove(r)
        for node in reversed(nodes):
            parent.insert(index, node)
        if first_only:
            break


def tabla_evidencia(rows):
    if not rows or any(not isinstance(row, list) for row in rows):
        raise ValueError('Tabla de evidencia vacía o inválida.')
    columns = max(map(len, rows))
    if not columns:
        raise ValueError('Tabla de evidencia sin columnas.')
    table = ET.Element(W + 'tbl')
    props = ET.SubElement(table, W + 'tblPr')
    ET.SubElement(props, W + 'tblStyle', {W + 'val': 'Tablanormal'})
    ET.SubElement(props, W + 'tblW', {W + 'w': '5000', W + 'type': 'pct'})
    borders = ET.SubElement(props, W + 'tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        ET.SubElement(borders, W + edge, {W + 'val': 'single', W + 'sz': '4', W + 'color': 'B7B7B7'})
    grid = ET.SubElement(table, W + 'tblGrid')
    for _ in range(columns):
        ET.SubElement(grid, W + 'gridCol', {W + 'w': str(9000 // columns)})
    for index, values in enumerate(rows):
        row = ET.SubElement(table, W + 'tr')
        if index == 0:
            ET.SubElement(ET.SubElement(row, W + 'trPr'), W + 'tblHeader')
        for value in list(values) + [''] * (columns - len(values)):
            cell = ET.SubElement(row, W + 'tc')
            cell_props = ET.SubElement(cell, W + 'tcPr')
            ET.SubElement(cell_props, W + 'tcW', {W + 'w': str(9000 // columns), W + 'type': 'dxa'})
            if index == 0:
                ET.SubElement(cell_props, W + 'shd', {W + 'val': 'clear', W + 'fill': '1F4E78'})
            elif index % 2 == 0:
                ET.SubElement(cell_props, W + 'shd', {W + 'val': 'clear', W + 'fill': 'EAF0F8'})
            p = parrafo(value)
            formato_parrafo(p, compact=True)
            rpr = p.find(W + 'r/' + W + 'rPr')
            ET.SubElement(rpr, W + 'sz', {W + 'val': '18'})
            if index == 0:
                ET.SubElement(rpr, W + 'b')
            cell.append(p)
    return table


def _cell(cell, value):
    model = cell.find(W + 'p')
    new = parrafo(value, model)
    formato_parrafo(new, compact=True)
    props = new.find(W + 'r/' + W + 'rPr')
    for child in props.findall(W + 'sz'):
        props.remove(child)
    props.insert(len(props) - 1, ET.Element(W + 'sz', {W + 'val': '18'}))
    for child in list(cell):
        if child.tag != W + 'tcPr':
            cell.remove(child)
    cell.append(new)


def _hoja(table, content):
    found = set()
    means = {'Promedio A.': 'proteccion_civil', 'Promedio B.': 'condiciones_del_personal',
             'Promedio C.': 'inteligencia_y_eficiencia_policial'}
    for row in table.findall(W + 'tr')[1:]:
        cells = row.findall(W + 'tc')
        label = texto(cells[0])
        if label.isdigit():
            number = int(label)
            item = next(r for r in content['hoja_computo'] if r['indicador'] == number)
            found.add(number)
            for cell, key in zip(cells[2:], ('general', 'ultimo_periodo', 'nota')):
                _cell(cell, item[key])
        else:
            for index, period in enumerate(PERIODOS, 1):
                value = 'Pendiente'
                for prefix, dimension in means.items():
                    if label.startswith(prefix):
                        value = content['promedios_dimension'][period][dimension] or 'Pendiente'
                if label == 'PROMEDIO DE LAS TRES DIMENSIONES':
                    mean = content['promedios_generales'][period]
                    value = decimal_corto(mean) if mean is not None else 'Pendiente'
                elif label.startswith('Candados aplicados'):
                    value = content['candados'][period] or 'Ninguno'
                elif label == 'CALIFICACIÓN':
                    value = content['calificaciones'][period]
                _cell(cells[index], value)
    if found != set(range(1, 19)):
        raise ValueError('La hoja de cómputo no contiene exactamente los indicadores 1–18.')
    # La tabla original contiene anchos distintos por fila; fijar una cuadrícula
    # común evita que las notas y los puntajes cambien de columna al paginar.
    widths = [550, 2500, 1050, 1050, 3350]
    props = table.find(W + 'tblPr')
    for key in ('tblW', 'tblLayout'):
        for node in props.findall(W + key):
            props.remove(node)
    ET.SubElement(props, W + 'tblW', {W + 'w': '5000', W + 'type': 'pct'})
    ET.SubElement(props, W + 'tblLayout', {W + 'type': 'fixed'})
    grid = table.find(W + 'tblGrid')
    for node in list(grid):
        grid.remove(node)
    for width in widths:
        ET.SubElement(grid, W + 'gridCol', {W + 'w': str(width)})
    for row in table.findall(W + 'tr'):
        column = 0
        for cell in row.findall(W + 'tc'):
            props = cell.find(W + 'tcPr')
            if props is None:
                props = ET.Element(W + 'tcPr')
                cell.insert(0, props)
            span_node = props.find(W + 'gridSpan')
            span = int(span_node.get(W + 'val')) if span_node is not None else 1
            for node in props.findall(W + 'tcW'):
                props.remove(node)
            props.insert(0, ET.Element(W + 'tcW', {W + 'w': str(sum(widths[column:column + span])), W + 'type': 'dxa'}))
            column += span


def _unique(blocks, predicate, description):
    matches = [i for i, b in enumerate(blocks) if predicate(texto(b).strip())]
    if len(matches) != 1:
        raise ValueError(f'No se encontró un ancla única: {description}.')
    return matches[0]


def seleccionar_documento(root, result, mode):
    """Selecciona el perfil de diagnóstico y mantiene el Anexo 1 de referencia."""
    body = root.find(W + 'body')
    original = list(body)
    content = result['contenido_word']
    selected = []
    if mode == 'borrador':
        selected.append(parrafo(content['aviso_borrador']))
    selected.append(color_generado(parrafo(content['titulo'], original[0])))
    selected.append(parrafo(content['periodo']))
    for period, prefix in [('general', 'CALIFICACIÓN GENERAL:'), ('ultimo_periodo', 'CALIFICACIÓN DEL ÚLTIMO PERIODO:')]:
        index = _unique(original, lambda t: t.startswith(prefix), prefix)
        p = deepcopy(original[index])
        suffix = texto(p).split(':', 1)[1]
        reemplazar(p, suffix, ' ' + content['calificaciones'][period])
        selected.append(p)
    for key, heading in [('resumen_general', 'Síntesis del periodo general'),
                         ('resumen_ultimo_periodo', 'Síntesis del último periodo')]:
        index = _unique(original, lambda t: MARKER.fullmatch(t) and MARKER.fullmatch(t)[1] == key, key)
        selected.extend([color_generado(parrafo(heading)), deepcopy(original[index])])
    index = _unique(original, lambda t: t == 'HOJA DE CÓMPUTO', 'HOJA DE CÓMPUTO')
    selected.append(deepcopy(original[index]))
    worksheet = deepcopy(original[index + 1])
    if worksheet.tag != W + 'tbl':
        raise ValueError('No se encontró la tabla de cómputo tras su encabezado.')
    _hoja(worksheet, content)
    for p in worksheet.iter(W + 'p'):
        formato_parrafo(p, compact=True)
    selected.append(worksheet)
    dimensions = {1: 'Protección civil', 4: 'Condiciones del personal', 11: 'Inteligencia y eficiencia policial'}
    for section in result['indicadores']:
        number = section['numero']
        key = f'analisis_indicador_{number:02d}'
        index = _unique(original, lambda t: MARKER.fullmatch(t) and MARKER.fullmatch(t)[1] == key, key)
        if number in dimensions:
            selected.append(color_generado(parrafo(dimensions[number])))
        heading, rating, benchmark, analysis = deepcopy(original[index-3:index+1])
        if texto(rating).count(SELECTOR) != 2 or not texto(benchmark).startswith('Benchmark:'):
            raise ValueError(f'Cambió la estructura del indicador {number}.')
        for paragraph in (heading, rating, benchmark):
            props = paragraph.find(W + 'pPr')
            if props is None:
                props = ET.Element(W + 'pPr')
                paragraph.insert(0, props)
            if props.find(W + 'keepNext') is None:
                props.insert(0, ET.Element(W + 'keepNext'))
            for alignment in props.findall(W + 'jc'):
                props.remove(alignment)
            ET.SubElement(props, W + 'jc', {W + 'val': 'left'})
        # Reemplazo de selectores por periodo sin alterar el texto circundante.
        for period in PERIODOS:
            value = section['evaluaciones'][period]['puntaje']
            reemplazar(rating, SELECTOR, str(value) if value is not None else 'Pendiente', first_only=True)
        selected.extend([heading, rating, benchmark, analysis])
        for table in section['tablas']:
            selected.append(color_generado(parrafo(f"Evidencia {table['ambito']} — PAQUETE SEGURIDAD, tabla {table['tabla']}")))
            selected.append(tabla_evidencia(table['filas']))
        selected.append(parrafo(next(a['cierre'] for a in content['analisis'] if a['indicador'] == number)))
    if mode == 'borrador':
        selected.append(parrafo('Pendientes de revisión', generated=False))
        for validation in result['validaciones']:
            detail = validation.get('detalle') or ', '.join(validation.get('variables', []))
            context = f" — indicador {validation['indicador']}" if 'indicador' in validation else ''
            context += f" — {validation['periodo']}" if 'periodo' in validation else ''
            selected.append(parrafo(f"{validation['codigo']}{context}: {detail}"))
    start = _unique(original, lambda t: t.startswith('Anexo 1. Fichas de calificación'), 'Anexo 1')
    # El Anexo 2 inicia la sección apaisada final. Conservarlo completo evita
    # dejar una sección horizontal vacía o cortar su tabla de referencias.
    selected.extend(deepcopy(original[start:]))
    for node in original:
        body.remove(node)
    for node in selected:
        body.append(node)
    for p in list(body.iter(W + 'p')):
        for match in list(MARKER.finditer(texto(p))):
            key = match[1]
            value = result['valores_plantilla'].get(key)
            if value is None:
                if mode == 'final':
                    raise ValueError(f'Falta variable activa: {key}.')
                value = f'Pendiente de revisión: {key}'
            if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                raise ValueError(f'Tipo de dato no válido para {key}.')
            if '{{' in str(value) or '}}' in str(value):
                raise ValueError(f'El contenido de {key} incluye marcadores sin resolver.')
            if MARKER.fullmatch(texto(p).strip()) and '\n\n' in str(value):
                parent = p.getparent()
                index = parent.index(p)
                paragraphs = [parrafo(piece, p) for piece in str(value).split('\n\n')]
                parent.remove(p)
                for offset, paragraph in enumerate(paragraphs):
                    parent.insert(index + offset, paragraph)
            else:
                reemplazar(p, match[0], str(value))


def validar_resultado(result, mode):
    content = result.get('contenido_word', {})
    if content.get('perfil') != 'diagnostico_desde_evidencia':
        raise ValueError('El JSON no contiene composición Word compatible; vuelva a ejecutar el pipeline.')
    sections = result['indicadores']
    ids = [s['numero'] for s in sections]
    if ids != list(range(1, 19)):
        raise ValueError('Se requieren los 18 indicadores ordenados, sin duplicados.')
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    dictionary = json.loads(DICTIONARY.read_text(encoding='utf-8'))
    active = {'municipio', 'estado', 'año_inicial', 'año_final', 'resumen_general', 'resumen_ultimo_periodo'} | {
        f'analisis_indicador_{i:02d}' for i in range(1, 19)}
    if set(content.get('variables_activas', [])) != active:
        raise ValueError('El listado de variables activas no corresponde al perfil editorial.')
    if sorted(row['indicador'] for row in content['hoja_computo']) != ids:
        raise ValueError('La hoja de cómputo debe tener los 18 indicadores sin duplicados.')
    if sorted(a['indicador'] for a in content['analisis']) != ids:
        raise ValueError('Se requieren los 18 análisis sin duplicados.')
    for key in active:
        value = result['valores_plantilla'].get(key)
        expected = dictionary['variables_documento'][key]['tipo_dato']
        if value is not None and not ((expected == 'string' and isinstance(value, str))
                                      or (expected == 'integer' and type(value) is int)):
            raise ValueError(f'Tipo incorrecto para la variable activa {key}.')
    for key in ('municipio', 'estado'):
        if result['valores_plantilla'].get(key) != result.get(key):
            raise ValueError(f'Identidad inconsistente: {key}.')
    for period in PERIODOS:
        scores = {s['numero']: s['evaluaciones'][period] for s in sections}
        computed = agregar(scores, rules)
        if computed != result['calculos'][period]:
            raise ValueError(f'Cálculos agregados inconsistentes en {period}.')
        if content['calificaciones'][period] != (computed['calificacion_final'] or 'PENDIENTE'):
            raise ValueError(f'Calificación editorial inconsistente en {period}.')
        for row in content['hoja_computo']:
            value = scores[row['indicador']]['puntaje']
            if row[period] != (str(value) if value is not None else 'Pendiente'):
                raise ValueError('La hoja de cómputo difiere de las evaluaciones.')
        for dimension, numbers in rules['dimensiones'].items():
            values = [scores[i]['puntaje'] for i in numbers]
            mean = None if None in values else decimal_corto(sum(Decimal(v) for v in values) / len(values))
            if content['promedios_dimension'][period][dimension] != mean:
                raise ValueError('Promedio editorial de dimensión inconsistente.')
        if content['promedios_generales'][period] != computed.get('promedio_tres_dimensiones'):
            raise ValueError('Promedio editorial general inconsistente.')
    if mode == 'final':
        if result.get('estado_ejecucion') != 'validado':
            raise ValueError('La versión final exige estado_ejecucion=validado.')
        if any(v.get('nivel') in ('bloqueante', 'revision') for v in result['validaciones']):
            raise ValueError('Existen bloqueos o revisiones pendientes: sólo se permite un borrador.')
        if any(result['calculos'][p].get('estado') != 'calculado' for p in PERIODOS):
            raise ValueError('La versión final exige todos los puntajes y ambas calificaciones.')
        if any(result['valores_plantilla'].get(k) in (None, '') for k in content['variables_activas']):
            raise ValueError('Hay variables activas sin resolver.')


def auditar(path, expected_generated=None):
    count = 0
    characters = 0
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError('El DOCX contiene una entrada ZIP dañada.')
        for name in archive.namelist():
            if not name.startswith('word/') or not name.endswith('.xml'):
                continue
            root = ET.fromstring(archive.read(name), PARSER)
            for p in root.iter(W + 'p'):
                value = texto(p)
                if '{{' in value or '}}' in value or SELECTOR in value or re.search(r'\[(?:borrar|verificar)\b', value, re.I):
                    raise ValueError(f'Marcador o instrucción editorial pendiente en {name}.')
            for r in root.iter(W + 'r'):
                style = r.find(W + 'rPr/' + W + 'rStyle')
                if style is not None and style.get(W + 'val') == STYLE:
                    count += 1
                    characters += len(texto(r))
                    highlight = r.find(W + 'rPr/' + W + 'highlight')
                    if highlight is None or highlight.get(W + 'val') != 'yellow':
                        raise ValueError('Contenido JSON sin resaltado amarillo.')
                    fonts = r.find(W + 'rPr/' + W + 'rFonts')
                    if fonts is None or fonts.get(W + 'ascii') != 'Archivo Light':
                        raise ValueError('Contenido JSON sin fuente Archivo Light.')
    if not count or (expected_generated is not None and count != expected_generated):
        raise ValueError('El contenido generado no coincide con la auditoría de inserciones.')
    return {'segmentos_json': count, 'caracteres_json': characters,
            'resaltado_amarillo_verificado': True, 'marcadores_pendientes': 0}


def renderizar(json_path, output_dir, mode='borrador', template=TEMPLATE):
    if mode not in ('borrador', 'final'):
        raise ValueError('Modo de documento no reconocido.')
    raw = json_path.read_bytes()
    result = json.loads(raw)
    for key, path in [('plantilla_sha256', template), ('diccionario_sha256', DICTIONARY), ('reglas_sha256', RULES)]:
        if result['contrato'].get(key) != sha256(path):
            raise ValueError(f'El JSON no corresponde al contrato actual: {key}.')
    validar_resultado(result, mode)
    with zipfile.ZipFile(template) as archive:
        files = {item.filename: archive.read(item.filename) for item in archive.infolist()}
        infos = archive.infolist()
    root = ET.fromstring(files['word/document.xml'], PARSER)
    # La paginación calculada del original deja de ser válida al componer la copia.
    for cached_break in list(root.iter(W + 'lastRenderedPageBreak')):
        cached_break.getparent().remove(cached_break)
    dictionary = json.loads(DICTIONARY.read_text(encoding='utf-8'))
    found = Counter(key for p in root.iter(W + 'p') for key in MARKER.findall(texto(p)))
    if found != Counter({k: v['apariciones'] for k, v in dictionary['variables_documento'].items()}):
        raise ValueError('Los marcadores de la plantilla no corresponden al diccionario.')
    seleccionar_documento(root, result, mode)
    generated = len(root.xpath('.//w:r[w:rPr/w:rStyle[@w:val="ContenidoJSON"]]', namespaces=NS))
    files['word/document.xml'] = xml_bytes(root)
    styles = ET.fromstring(files['word/styles.xml'], PARSER)
    if styles.xpath('./w:style[@w:styleId="ContenidoJSON"]', namespaces=NS):
        raise ValueError('La plantilla ya contiene el estilo reservado ContenidoJSON.')
    style = ET.SubElement(styles, W + 'style', {W + 'type': 'character', W + 'styleId': STYLE})
    ET.SubElement(style, W + 'name', {W + 'val': 'Contenido procedente del JSON'})
    ET.SubElement(ET.SubElement(style, W + 'rPr'), W + 'highlight', {W + 'val': 'yellow'})
    files['word/styles.xml'] = xml_bytes(styles)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid4().hex[:8]
    dest = output_dir / f'{json_path.stem}_{mode}_{suffix}.docx'
    with tempfile.TemporaryDirectory(prefix='.render-', dir=output_dir) as directory:
        temp = Path(directory) / 'documento.docx'
        with zipfile.ZipFile(temp, 'w') as archive:
            for info in infos:
                archive.writestr(info, files[info.filename])
        audit = auditar(temp, generated)
        # Publicación atómica y exclusiva dentro del mismo sistema de archivos.
        os.link(temp, dest)
    return {**audit, 'archivo': str(dest), 'sha256': sha256(dest), 'modo': mode,
            'json_fuente': str(json_path), 'json_sha256': hashlib.sha256(raw).hexdigest(),
            'plantilla_sha256': result['contrato']['plantilla_sha256'],
            'perfil': result['contenido_word']['perfil']}


def guardar_recibo(report, receipt):
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open('x', encoding='utf-8') as target:
        json.dump(report, target, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('json', type=Path, help='JSON municipal compuesto por el pipeline.')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/word')
    parser.add_argument('--modo', choices=('borrador', 'final'), default='borrador')
    args = parser.parse_args()
    try:
        report = renderizar(args.json, args.output, args.modo)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    # El recibo vincula el Word al JSON exacto sin modificar la entrada auditada.
    receipt = args.output.parent / 'json' / (Path(report['archivo']).stem + '_renderizado.json')
    guardar_recibo(report, receipt)
    print(f"Word ({args.modo}): {report['archivo']}")
    print(f"Resaltado amarillo verificado: {report['segmentos_json']} segmentos. Recibo: {receipt}")


if __name__ == '__main__':
    main()
