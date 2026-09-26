#!/usr/bin/env python3
"""Renderiza la medición de SEGURIDAD con el machote de investigación v3."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
import zipfile
from lxml import etree as ET
from calificar import agregar
from componer_documento import PERIODOS, decimal_corto
from contrato import ROOT, CONTRACT, cargar_contrato, huellas
from documentos import sha256
from editorial import configurar
from graficas_word import agregar_grafica
from salidas import limpiar_salidas

TEMPLATE = ROOT / 'templates/seguridad_medicion_v3.docx'
DICTIONARY = ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json'
RULES = ROOT / 'reglas_calificacion.json'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML = '{http://www.w3.org/XML/1998/namespace}'
NS = {'w': W[1:-1]}
STYLE = 'ContenidoJSON'
MARKER = re.compile(r'(?<!\{)\{([a-z][a-z0-9_]*)\}(?!\})')
PARSER = ET.XMLParser(resolve_entities=False, no_network=True)


def slug(value):
    value = ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '_', value).strip('_')


def texto(node):
    return ''.join(t.text or '' for t in node.iter(W + 't'))


def xml_bytes(node):
    return ET.tostring(node, encoding='UTF-8', xml_declaration=True, standalone=True)


def run(value, model=None, generated=True):
    element = ET.Element(W + 'r')
    props = deepcopy(model.find(W + 'rPr')) if model is not None and model.find(W + 'rPr') is not None else ET.Element(W + 'rPr')
    if generated:
        for key in ('rStyle', 'highlight', 'shd'):
            for child in props.findall(W + key):
                props.remove(child)
        props.insert(0, ET.Element(W + 'rStyle', {W + 'val': STYLE}))
        ET.SubElement(props, W + 'highlight', {W + 'val': 'yellow'})
        ET.SubElement(props, W + 'shd', {W + 'val': 'clear', W + 'color': 'auto', W + 'fill': 'FFFF00'})
    element.append(props)
    for i, line in enumerate(str(value).split('\n')):
        if i:
            ET.SubElement(element, W + 'br')
        ET.SubElement(element, W + 't', {XML + 'space': 'preserve'}).text = line
    return element


def parrafo(value, model=None, generated=True, perfil='medicion', rol='cuerpo', inicial=True):
    p = ET.Element(W + 'p')
    if model is not None and model.find(W + 'pPr') is not None:
        p.append(deepcopy(model.find(W + 'pPr')))
    p.append(run(value, model.find('.//' + W + 'r') if model is not None else None, generated))
    return configurar(p, perfil, rol, inicial)


def reemplazar(p, token, replacement, first_only=False):
    """Resuelve marcadores fragmentados, conservando estilos y texto circundante."""
    while token in texto(p):
        start = texto(p).index(token); end = start + len(token)
        spans = []; offset = 0
        for r in p.iter(W + 'r'):
            value = texto(r)
            if offset < end and offset + len(value) > start:
                spans.append((r, offset, value))
            offset += len(value)
        if not spans:
            raise ValueError('Marcador sin segmentos editables.')
        parent = spans[0][0].getparent()
        if any(r.getparent() is not parent or any(c.tag not in (W + 'rPr', W + 't') for c in r) for r, _, _ in spans):
            raise ValueError(f'Marcador en estructura compleja: {token}')
        first, first_offset, first_text = spans[0]
        last, last_offset, last_text = spans[-1]
        before = first_text[:start - first_offset]; after = last_text[end - last_offset:]
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


def tabla_evidencia(rows, perfil='medicion'):
    if not rows or any(not isinstance(row, list) for row in rows) or not max(map(len, rows)):
        raise ValueError('Tabla vacía o inválida.')
    columns = max(map(len, rows))
    table = ET.Element(W + 'tbl')
    props = ET.SubElement(table, W + 'tblPr')
    ET.SubElement(props, W + 'tblW', {W + 'w': '5000', W + 'type': 'pct'})
    borders = ET.SubElement(props, W + 'tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        ET.SubElement(borders, W + edge, {W + 'val': 'single', W + 'sz': '4', W + 'color': 'B7B7B7'})
    grid = ET.SubElement(table, W + 'tblGrid')
    for _ in range(columns):
        ET.SubElement(grid, W + 'gridCol', {W + 'w': str(9000 // columns)})
    years = perfil == 'anexo' and any(str(value).strip() in ('Año', 'Porcentaje') for value in rows[0])
    for index, values in enumerate(rows):
        row = ET.SubElement(table, W + 'tr')
        rowprops = ET.SubElement(row, W + 'trPr')
        if index == 0:
            ET.SubElement(rowprops, W + 'tblHeader')
        ET.SubElement(rowprops, W + 'cantSplit')
        for value in list(values) + [''] * (columns - len(values)):
            cell = ET.SubElement(row, W + 'tc')
            cellprops = ET.SubElement(cell, W + 'tcPr')
            ET.SubElement(cellprops, W + 'tcW', {W + 'w': str(9000 // columns), W + 'type': 'dxa'})
            if index % 2 == 0:
                ET.SubElement(cellprops, W + 'shd', {W + 'val': 'clear', W + 'fill': 'DAE3F3' if index == 0 else 'EAF0F8'})
            role = ('tabla_anios_' if years else 'tabla_') + ('titulo' if index == 0 else 'cuerpo')
            cell.append(parrafo(value, perfil=perfil, rol=role))
    return table


def validar_resultado(result, mode):
    content = result.get('contenido_word', {})
    if content.get('perfil') != 'seguridad_investigacion_v3':
        raise ValueError('El JSON no contiene composición Word compatible; vuelva a ejecutar el pipeline.')
    sections = result['indicadores']; ids = [s['numero'] for s in sections]
    if ids != list(range(1, 19)):
        raise ValueError('Se requieren los 18 indicadores ordenados, sin duplicados.')
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    dictionary = json.loads(DICTIONARY.read_text(encoding='utf-8'))
    active = set(dictionary['variables_documento'])
    if set(content.get('variables_activas', [])) != active:
        raise ValueError('Variables activas distintas al contrato editorial.')
    if sorted(row['indicador'] for row in content['hoja_computo']) != ids or sorted(a['indicador'] for a in content['analisis']) != ids:
        raise ValueError('Se requieren 18 análisis y filas de cómputo.')
    for key in active:
        value = result['valores_plantilla'].get(key)
        expected = dictionary['variables_documento'][key]['tipo_dato']
        if value is not None and not ((expected == 'string' and isinstance(value, str)) or (expected == 'array' and isinstance(value, list))):
            raise ValueError(f'Tipo incorrecto para {key}.')
        if isinstance(value, str) and (re.search(r'[{}]', value) or '[INSERTAR' in value.upper()):
            raise ValueError(f'Contenido con marcadores pendientes: {key}')
        if (value is None or (isinstance(value, str) and not value.strip())) and mode == 'final':
            raise ValueError(f'Variable pendiente: {key}')
    for key in ('municipio', 'estado'):
        if result['valores_plantilla'].get(key) != result.get(key):
            raise ValueError(f'Identidad inconsistente: {key}.')
    for section in sections:
        number = section['numero']
        expected = [{'titulo': f"Datos {t['ambito']} — PAQUETE SEGURIDAD, tabla {t['tabla']}",
                     'ambito': t['ambito'], 'tabla_fuente': t['tabla'], 'filas': t['filas']} for t in section['tablas']]
        if result['valores_plantilla'][f'tablas_indicador_{number:02d}'] != expected:
            raise ValueError(f'Tablas diferentes a la evidencia del indicador {number}.')
        scores = [section['evaluaciones'][p]['puntaje'] for p in PERIODOS]
        graphs = result['valores_plantilla'][f'graficas_indicador_{number:02d}']
        if len(graphs) > 1 or (any(s is not None for s in scores) and not graphs):
            raise ValueError('Gráfica de puntajes ausente o duplicada.')
        for graph in graphs:
            if graph.get('tipo') != 'puntajes' or graph.get('categorias') != list(PERIODOS.values()) or graph.get('valores') != scores:
                raise ValueError('La gráfica difiere de las evaluaciones.')
    for period in PERIODOS:
        scores = {s['numero']: s['evaluaciones'][period] for s in sections}
        computed = agregar(scores, rules)
        if computed != result['calculos'][period]:
            raise ValueError(f'Cálculos agregados inconsistentes en {period}.')
        grade = computed['calificacion_final'] or 'PENDIENTE'
        if content['calificaciones'][period] != grade or result['valores_plantilla'][f'calificacion_{period}'] != grade:
            raise ValueError('Calificación editorial inconsistente.')
        for row in content['hoja_computo']:
            value = scores[row['indicador']]['puntaje']
            if row[period] != (str(value) if value is not None else 'Pendiente'):
                raise ValueError('La hoja de cómputo difiere de las evaluaciones.')
        for dimension, numbers in rules['dimensiones'].items():
            values = [scores[i]['puntaje'] for i in numbers]
            mean = None if None in values else decimal_corto(sum(Decimal(v) for v in values) / len(values))
            if content['promedios_dimension'][period][dimension] != mean:
                raise ValueError('Promedio de dimensión inconsistente.')
        if content['promedios_generales'][period] != computed.get('promedio_tres_dimensiones'):
            raise ValueError('Promedio general inconsistente.')
    if mode == 'final':
        if result.get('estado_ejecucion') != 'validado':
            raise ValueError('La versión final exige estado_ejecucion=validado.')
        if any(v.get('nivel') in ('bloqueante', 'revision') for v in result['validaciones']):
            raise ValueError('Existen bloqueos o revisiones pendientes: sólo se permite un borrador.')
        if any(result['calculos'][p].get('estado') != 'calculado' for p in PERIODOS):
            raise ValueError('La versión final exige todos los puntajes y ambas calificaciones.')
    from investigacion import validar_aporte
    research = result.get('investigacion', {})
    lines = research.get('lineas', [])
    research_config = json.loads((ROOT / 'config/investigacion_seguridad.json').read_text(encoding='utf-8'))
    if [l.get('id') for l in lines] != [l['id'] for l in research_config['lineas']]:
        raise ValueError('Líneas de investigación distintas al contrato.')
    for line, definition in zip(lines, research_config['lineas']):
        if line.get('variable') != definition['variable']:
            raise ValueError('Variable de benchmark distinta al contrato.')
    verified = [l for l in lines if l.get('estado') == 'verificado']
    validar_aporte({'version': '1.0', 'lineas': [
        {**l, 'analisis': result['valores_plantilla'][l['variable']]} for l in verified],
        'minimos_indicadores': research.get('minimos_indicadores', {})}, research_config)
    for line in lines:
        if line.get('estado') not in ('pendiente', 'verificado'):
            raise ValueError('Estado de investigación inválido.')
        if line['estado'] == 'pendiente' and result['valores_plantilla'][line['variable']] is not None:
            raise ValueError('Benchmark pendiente presentado como verificado.')
    for i in range(1, 4):
        supplied = research.get('minimos_indicadores', {}).get(f'{i:02d}')
        if result['valores_plantilla'][f'minimos_indicador_{i:02d}'] != (supplied['texto'] if supplied else None):
            raise ValueError('Mínimos normativos distintos a la investigación revisada.')
    if mode == 'final' and (len(verified) != 4 or len(research.get('minimos_indicadores', {})) != 3):
        raise ValueError('La versión final requiere cuatro benchmarks y tres mínimos revisados.')


def seleccionar_documento(root, result, mode, perfil, files):
    body = root.find(W + 'body')
    start = next((i + 1 for i, p in enumerate(body) if p.find(W + 'pPr/' + W + 'sectPr') is not None), 0)
    if mode == 'borrador':
        body.insert(start, parrafo(result['contenido_word']['aviso_borrador'], perfil=perfil, rol='nota'))
    body.insert(start + (1 if mode == 'borrador' else 0), parrafo(result['contenido_word']['periodo'], perfil=perfil, rol='nota'))
    chart_number = 0
    format_config = json.loads((ROOT / 'config/formato_editorial.json').read_text(encoding='utf-8'))
    for p in list(root.iter(W + 'p')):
        matches = list(MARKER.finditer(texto(p)))
        if not matches:
            continue
        if len(matches) == 1 and MARKER.fullmatch(texto(p).strip()):
            key = matches[0][1]; value = result['valores_plantilla'][key]
            replacements = []
            if isinstance(value, list):
                for item in value:
                    replacements.append(parrafo(item['titulo'], perfil=perfil, rol='nota'))
                    if key.startswith('graficas_'):
                        chart_number += 1
                        drawing = configurar(agregar_grafica(files, item, chart_number), perfil, 'cuerpo')
                        drawing.find(W + 'pPr/' + W + 'spacing').set(W + 'lineRule', 'atLeast')
                        replacements.append(drawing)
                        missing = [c for c, v in zip(item['categorias'], item['valores']) if v is None]
                        replacements.append(parrafo(item['fuente'] + (' No representado por dato pendiente: ' + ', '.join(missing) + '.' if missing else ''), perfil=perfil, rol='nota'))
                    else:
                        replacements.append(tabla_evidencia(item['filas'], perfil))
            else:
                value = f'Pendiente de revisión: {key}' if value is None else value
                rol = 'bibliografia' if key == 'bibliografia' else 'cuerpo'
                indent = p.find(W + 'pPr/' + W + 'ind')
                continuation = indent is not None and indent.get(W + 'firstLine') == '283'
                replacements = [parrafo(piece, p, perfil=perfil, rol=rol, inicial=i == 0 and not continuation)
                                for i, piece in enumerate(str(value).split('\n\n'))]
                if rol == 'bibliografia':
                    for i, replacement in enumerate(replacements):
                        value = texto(replacement)
                        if '. SHA-256: ' in value:
                            title, checksum = value.split('. SHA-256: ', 1)
                            for r in list(replacement.iter(W + 'r')):
                                replacement.remove(r)
                            italic = run(title + '. ')
                            ET.SubElement(italic.find(W + 'rPr'), W + 'i')
                            replacement.extend([italic, run('SHA-256: ' + checksum)])
                            configurar(replacement, perfil, 'bibliografia', inicial=i == 0)
            parent = p.getparent(); index = parent.index(p); parent.remove(p)
            for offset, replacement in enumerate(replacements):
                parent.insert(index + offset, replacement)
        else:
            for match in matches:
                value = result['valores_plantilla'][match[1]]
                reemplazar(p, match[0], 'Pendiente' if value is None else str(value))
                if match[1].startswith('calificacion_'):
                    for r in p.iter(W + 'r'):
                        rpr = r.find(W + 'rPr')
                        if rpr is not None:
                            for n in rpr.findall(W + 'color'):
                                rpr.remove(n)
                            ET.SubElement(rpr, W + 'color', {W + 'val': format_config['colores_calificacion'].get(value, '666666')})
    if mode == 'borrador':
        section = body.find(W + 'sectPr')
        index = body.index(section)
        body.insert(index, parrafo('Pendientes de revisión', generated=False, perfil=perfil, rol='subcapitulo'))
        for offset, v in enumerate(result['validaciones'], 1):
            detail = v.get('detalle') or ', '.join(v.get('variables', []))
            detail = detail or f"Indicador {v.get('indicador', '')} {v.get('periodo', '')}"
            body.insert(index + offset, parrafo(f"{v['codigo']}: {detail}", perfil=perfil, rol='nota'))


def auditar(path, expected_generated=None):
    count = 0; characters = 0
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError('DOCX dañado.')
        for name in archive.namelist():
            if not name.startswith('word/') or not name.endswith('.xml'):
                continue
            root = ET.fromstring(archive.read(name), PARSER)
            if name.startswith('word/charts/pipeline_'):
                c = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
                a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
                fill = root.find(c + 'spPr/' + a + 'solidFill/' + a + 'srgbClr')
                if fill is None or fill.get('val') != 'FFFF00':
                    raise ValueError('Gráfica JSON sin marca amarilla.')
            for p in root.iter(W + 'p'):
                if re.search(r'[{}]|\[INSERTAR', texto(p), re.I):
                    raise ValueError(f'Marcador editorial pendiente en {name}.')
            for r in root.iter(W + 'r'):
                style = r.find(W + 'rPr/' + W + 'rStyle')
                if style is None or style.get(W + 'val') != STYLE:
                    continue
                count += 1; characters += len(texto(r))
                props = r.find(W + 'rPr')
                highlight = props.find(W + 'highlight'); shade = props.find(W + 'shd')
                if highlight is None or highlight.get(W + 'val') != 'yellow':
                    raise ValueError('Contenido JSON sin resaltado amarillo.')
                if shade is None or shade.get(W + 'fill') != 'FFFF00':
                    raise ValueError('Contenido JSON sin sombreado amarillo.')
                fonts = props.find(W + 'rFonts')
                if fonts is None or fonts.get(W + 'ascii') not in ('Archivo', 'Archivo Medium', 'Archivo Light'):
                    raise ValueError('Contenido JSON sin fuente editorial Archivo.')
    if not count or (expected_generated is not None and count != expected_generated):
        raise ValueError('Inserciones distintas a la auditoría.')
    return {'segmentos_json': count, 'caracteres_json': characters, 'resaltado_amarillo_verificado': True, 'marcadores_pendientes': 0}


def renderizar(json_path, output_dir, mode='borrador', template=None, perfil='medicion'):
    if mode not in ('borrador', 'final') or perfil != 'medicion':
        raise ValueError('Modo o perfil no reconocido.')
    contract = cargar_contrato()
    template = template or ROOT / contract['plantillas'][perfil]['archivo']
    raw = json_path.read_bytes(); result = json.loads(raw)
    expected = huellas()
    for key, value in expected.items():
        if result['contrato'].get(key) != value:
            raise ValueError(f'El JSON no corresponde al contrato actual: {key}.')
    if sha256(template) != contract['plantillas'][perfil]['sha256']:
        raise ValueError('La plantilla no corresponde al contrato actual.')
    validar_resultado(result, mode)
    with zipfile.ZipFile(template) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    root = ET.fromstring(files['word/document.xml'], PARSER)
    dictionary = json.loads(DICTIONARY.read_text(encoding='utf-8'))
    found = Counter(k for p in root.iter(W + 'p') for k in MARKER.findall(texto(p)))
    target = Counter({k: v['apariciones_por_documento'][perfil] for k, v in dictionary['variables_documento'].items() if v['apariciones_por_documento'][perfil]})
    if found != target:
        raise ValueError('Marcadores distintos al contrato del perfil.')
    for cached in list(root.iter(W + 'lastRenderedPageBreak')):
        cached.getparent().remove(cached)
    seleccionar_documento(root, result, mode, perfil, files)
    generated = len(root.xpath('.//w:r[w:rPr/w:rStyle[@w:val="ContenidoJSON"]]', namespaces=NS))
    files['word/document.xml'] = xml_bytes(root)
    styles = ET.fromstring(files['word/styles.xml'], PARSER)
    for existing in styles.xpath('./w:style[@w:styleId="ContenidoJSON"]', namespaces=NS):
        styles.remove(existing)
    style = ET.SubElement(styles, W + 'style', {W + 'type': 'character', W + 'styleId': STYLE})
    ET.SubElement(style, W + 'name', {W + 'val': 'Contenido procedente del JSON'})
    props = ET.SubElement(style, W + 'rPr')
    ET.SubElement(props, W + 'highlight', {W + 'val': 'yellow'})
    ET.SubElement(props, W + 'shd', {W + 'val': 'clear', W + 'color': 'auto', W + 'fill': 'FFFF00'})
    files['word/styles.xml'] = xml_bytes(styles)
    output_dir.mkdir(parents=True, exist_ok=True)
    municipality = slug(result['municipio'])
    if not municipality:
        raise ValueError('Municipio inválido para nombrar salida.')
    dest = output_dir / f'{municipality}_seguridad_{perfil}_{mode}.docx'
    with tempfile.TemporaryDirectory(prefix='.render-', dir=output_dir) as directory:
        temporary = Path(directory) / 'documento.docx'
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        audit = auditar(temporary, generated)
        os.replace(temporary, dest)
    return {**audit, 'archivo': str(dest), 'sha256': sha256(dest), 'modo': mode, 'perfil': perfil,
            'json_fuente': str(json_path), 'json_sha256': hashlib.sha256(raw).hexdigest(),
            'plantilla_sha256': sha256(template), 'contrato_documental_sha256': sha256(CONTRACT)}


def guardar_recibo(report, receipt):
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=receipt.parent, suffix='.tmp', delete=False) as target:
            temporary = Path(target.name); json.dump(report, target, ensure_ascii=False, indent=2); target.write('\n')
        os.replace(temporary, receipt)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('json', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/word')
    parser.add_argument('--modo', choices=('borrador', 'final'), default='borrador')
    parser.add_argument('--documento', choices=('medicion',), default='medicion')
    args = parser.parse_args()
    words = []; receipts = []
    try:
        for perfil in (args.documento,):
            report = renderizar(args.json, args.output, args.modo, perfil=perfil)
            word = Path(report['archivo']); receipt = args.output.parent / 'json' / (word.stem + '_renderizado.json')
            guardar_recibo(report, receipt); words.append(word); receipts.append(receipt)
            print(f"Word ({perfil}): {word}. Amarillo: {report['segmentos_json']} segmentos.")
        removidos = limpiar_salidas(args.output.parent / 'json', args.output, json_actual=args.json,
                                    word_actual=words[0], recibo_actual=receipts[0])
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(f'Limpieza de salidas: {removidos}')


if __name__ == '__main__':
    main()
