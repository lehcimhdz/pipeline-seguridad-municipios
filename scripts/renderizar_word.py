#!/usr/bin/env python3
"""Publica el Estudio Seguridad en el formato de la consultora."""
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
from calificar import definir_periodos
from evaluacion_v23 import evaluar
from ponderacion import agregar_ponderado
from evidencia_complementaria import validar as validar_complemento, huella_objeto
from componer_documento import componer, etiqueta_calificacion
from contrato import ROOT, CONTRACT, cargar_contrato, huellas
from documentos import sha256
from editorial import configurar
from ilustraciones_word import importar_grafica, seleccionar_graficas, catalogar_graficas
from lectura_graficas import validar_lecturas
from salidas import limpiar_salidas
from redaccion_consultoria import comprobar_texto, validar_publicacion

TEMPLATE = ROOT / 'templates/seguridad_medicion.docx'
DICTIONARY = ROOT / 'config/diccionario_datos_diagnostico_seguridad_municipal.json'
RULES = ROOT / 'config/reglas_calificacion.json'
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


def nombre_documento(municipio):
    if (not isinstance(municipio, str) or not municipio.strip()
            or re.search(r'[/\\:\x00-\x1f]', municipio) or municipio in ('.', '..')):
        raise ValueError('Municipio inválido para nombrar la entrega.')
    return unicodedata.normalize('NFC', municipio.strip()) + ' Estudio Seguridad.docx'


def fuentes_corresponden(municipio, fuentes):
    municipio = unicodedata.normalize('NFC', municipio)
    fuentes = [unicodedata.normalize('NFC', nombre) for nombre in fuentes]
    admitidas = {municipio + sufijo for sufijo in (' PAQUETE SEGURIDAD.docx', ' Anexo.docx')}
    return (municipio + ' PAQUETE SEGURIDAD.docx' in fuentes
            and len(fuentes) == len(set(fuentes)) and set(fuentes) <= admitidas)


def validar_resultado(result, mode='final'):
    if mode != 'final':
        raise ValueError('El estudio se publica en presentación final.')
    content = result.get('contenido_word', {})
    if content.get('perfil') != 'estudio_seguridad':
        raise ValueError('La composición no corresponde al Estudio Seguridad vigente.')
    municipality = result['municipio']
    nombre_documento(municipality)
    sources = [item['archivo'] for item in result['fuentes']]
    if not fuentes_corresponden(municipality, sources):
        raise ValueError('Las fuentes deben corresponder al Paquete Seguridad y, opcionalmente, su Anexo.')
    sections = result['indicadores']
    if [s['numero'] for s in sections] != list(range(1, 19)):
        raise ValueError('Se requieren los dieciocho indicadores en orden.')
    if result.get('periodos_evaluacion') != definir_periodos(sections):
        raise ValueError('Los periodos no corresponden a las ediciones y años de las fuentes.')
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    mappings = json.loads((ROOT / 'config/normalizaciones.json').read_text(encoding='utf-8'))
    dictionary = json.loads(DICTIONARY.read_text(encoding='utf-8'))
    values = result['valores_plantilla']
    if set(values) != set(dictionary['variables_documento']):
        raise ValueError('Las variables de texto difieren del contrato documental.')
    if set(content.get('variables_activas', [])) != set(values):
        raise ValueError('La composición no declara todas las variables vigentes.')
    if any(not isinstance(v, str) or not v.strip() for v in values.values()):
        raise ValueError('Todos los apartados de la entrega deben contener texto editorial.')
    if values['municipio'] != municipality or values['estado'] != result['estado']:
        raise ValueError('La identidad editorial no corresponde al municipio.')
    supplemental = validar_complemento(result['evidencia_complementaria'], municipality, result['estado'])
    if huella_objeto(supplemental) != result.get('evidencia_complementaria_sha256'):
        raise ValueError('Cambió la evidencia complementaria.')
    catalogue = result.get('catalogo_ilustraciones', [])
    if ('lecturas_graficas' in result or any('lecturas_graficas' in s for s in sections)
            or any(i['indicador'] in (2, 4, 5, 14) for i in catalogue)):
        canonical = [i for name in sources for i in catalogar_graficas(result['rutas_fuentes'][name])]
        if catalogue != canonical:
            raise ValueError('El catálogo de gráficas difiere de los documentos de entrada.')
        readings = result.get('lecturas_graficas')
        if not isinstance(readings, list):
            raise ValueError('Falta la lectura de las gráficas de entrada; volver a preparar.')
        validar_lecturas(readings, catalogue, result['rutas_fuentes'])
        if any(s.get('lecturas_graficas') != [i for i in readings if i['indicador'] == s['numero']] for s in sections):
            raise ValueError('La evidencia gráfica de un indicador difiere de su fuente.')
    evaluations = evaluar(sections, rules, mappings, result['periodos_evaluacion'], supplemental)
    for period in ('general', 'ultimo_periodo'):
        computed = evaluations[period]
        if any(section['evaluaciones'][period] != computed[section['numero']] for section in sections):
            raise ValueError('Una evaluación difiere de la evidencia y de los criterios vigentes.')
        grade = agregar_ponderado(computed, rules, modo=result['metodo_calificacion'], esquema=result['esquema_ponderacion'])
        if grade != result['calculos'][period]:
            raise ValueError('La calificación agregada difiere de su metodología.')
        published_grade = etiqueta_calificacion(grade)
        if values[f'calificacion_{period}'] != published_grade:
            raise ValueError('La calificación publicada no corresponde a la evaluación.')
    catalogue = result.get('catalogo_ilustraciones', [])
    selected = content.get('ilustraciones', [])
    if seleccionar_graficas(catalogue, selected) != selected:
        raise ValueError('Las ilustraciones no corresponden al catálogo documental.')
    for image in selected:
        paragraphs = values[f'analisis_indicador_{image["indicador"]:02d}'].split('\n\n')
        if image['despues_parrafo'] >= len(paragraphs):
            raise ValueError('La ilustración no tiene un párrafo de interpretación asociado.')
    if any(item.get('nivel') == 'bloqueante' for item in result.get('validaciones', [])):
        raise ValueError('La entrega conserva una inconsistencia documental bloqueante.')
    editorial = result.get('redaccion_editorial')
    if not editorial:
        raise ValueError('Falta el vínculo con la interpretación editorial.')
    editorial_path = Path(editorial['archivo'])
    if sha256(editorial_path) != editorial['sha256']:
        raise ValueError('Cambió la interpretación editorial: vuelva a componer el estudio.')
    copy = deepcopy(result)
    componer(copy, dictionary, rules, redaccion=json.loads(editorial_path.read_text(encoding='utf-8')))
    if copy['valores_plantilla'] != values:
        raise ValueError('El texto publicado difiere de la interpretación verificada.')
    validar_publicacion(result)


def seleccionar_documento(root, result, mode, perfil, files):
    body = root.find(W + 'body')
    section = body.find(W + 'sectPr')
    page = section.find(W + 'pgSz')
    margins = section.find(W + 'pgMar')
    max_width = (int(page.get(W + 'w')) - int(margins.get(W + 'left')) - int(margins.get(W + 'right'))) * 635
    format_config = json.loads((ROOT / 'config/formato_editorial.json').read_text(encoding='utf-8'))
    originals = []
    for p in list(root.iter(W + 'p')):
        matches = list(MARKER.finditer(texto(p)))
        if not matches:
            continue
        if len(matches) == 1 and MARKER.fullmatch(texto(p).strip()):
            key = matches[0][1]
            value = result['valores_plantilla'][key]
            role = 'bibliografia' if key == 'bibliografia' else 'cuerpo'
            replacements = []
            for index, piece in enumerate(value.split('\n\n')):
                replacement = parrafo(piece, p, perfil=perfil, rol=role, inicial=index == 0)
                if role == 'bibliografia':
                    for r in replacement.iter(W + 'r'):
                        ET.SubElement(r.find(W + 'rPr'), W + 'i')
                    configurar(replacement, perfil, role, inicial=index == 0)
                replacements.append(replacement)
                if key.startswith('analisis_indicador_'):
                    indicator = int(key.rsplit('_', 1)[1])
                    illustrations = [i for i in result['contenido_word'].get('ilustraciones', [])
                                     if i['indicador'] == indicator and i['despues_parrafo'] == index]
                    for image in illustrations:
                        source = Path(result['rutas_fuentes'][image['fuente']])
                        drawing, proof = importar_grafica(files, source, image, len(originals) + 1, max_width)
                        replacements.append(drawing)
                        originals.append(proof)
            parent = p.getparent()
            index = parent.index(p)
            parent.remove(p)
            for offset, replacement in enumerate(replacements):
                parent.insert(index + offset, replacement)
        else:
            for match in matches:
                value = result['valores_plantilla'][match[1]]
                reemplazar(p, match[0], value)
                if match[1].startswith('calificacion_'):
                    category = value.removesuffix(' (COBERTURA PARCIAL)')
                    color_value = ('666666' if category == 'SIN VALORACIÓN CONJUNTA'
                                   else format_config['colores_calificacion'][category])
                    for r in p.iter(W + 'r'):
                        props = r.find(W + 'rPr')
                        if props is not None:
                            for color in props.findall(W + 'color'):
                                props.remove(color)
                            ET.SubElement(props, W + 'color', {W + 'val': color_value})
    return originals


def auditar(path, expected_generated=None, imagenes_esperadas=()):
    count = 0; characters = 0
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError('DOCX dañado.')
        if any(n.startswith('word/charts/') for n in archive.namelist()):
            raise ValueError('El estudio no debe contener gráficas nuevas.')
        document = ET.fromstring(archive.read('word/document.xml'), PARSER)
        if document.find('.//' + W + 'tbl') is not None:
            raise ValueError('El estudio no debe contener tablas añadidas.')
        for expected in imagenes_esperadas:
            if hashlib.sha256(archive.read(expected['parte_salida'])).hexdigest() != expected['sha256']:
                raise ValueError('La ilustración dejó de ser una reproducción fiel de la fuente.')
        for name in archive.namelist():
            if not name.startswith('word/') or not name.endswith('.xml'):
                continue
            root = ET.fromstring(archive.read(name), PARSER)
            for node in root.iter():
                if ((node.tag == W + 'highlight' and node.get(W + 'val') == 'yellow')
                        or (node.tag == W + 'shd' and node.get(W + 'fill', '').upper() == 'FFFF00')):
                    raise ValueError('El documento conserva resaltado amarillo.')
            for p in root.iter(W + 'p'):
                if re.search(r'[{}]|\[INSERTAR', texto(p), re.I):
                    raise ValueError(f'Marcador editorial pendiente en {name}.')
                comprobar_texto(texto(p), name)
            for r in root.iter(W + 'r'):
                style = r.find(W + 'rPr/' + W + 'rStyle')
                if style is None or style.get(W + 'val') != STYLE:
                    continue
                count += 1; characters += len(texto(r))
                props = r.find(W + 'rPr')
                fonts = props.find(W + 'rFonts')
                if fonts is None or fonts.get(W + 'ascii') not in ('Archivo', 'Archivo Medium', 'Archivo Light'):
                    raise ValueError('Contenido JSON sin fuente editorial Archivo.')
    if not count or (expected_generated is not None and count != expected_generated):
        raise ValueError('Inserciones distintas a la auditoría.')
    return {'segmentos_json': count, 'caracteres_json': characters,
            'sin_resaltado_amarillo_verificado': True,
            'redaccion_publicable_verificada': True, 'marcadores_pendientes': 0,
            'tablas_creadas': 0, 'graficas_creadas': 0, 'graficas_reutilizadas': len(imagenes_esperadas)}


def renderizar(json_path, output_dir, mode='final', template=None, perfil='medicion'):
    if mode != 'final' or perfil != 'medicion':
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
    originals = seleccionar_documento(root, result, mode, perfil, files)
    generated = len(root.xpath('.//w:r[w:rPr/w:rStyle[@w:val="ContenidoJSON"]]', namespaces=NS))
    files['word/document.xml'] = xml_bytes(root)
    styles = ET.fromstring(files['word/styles.xml'], PARSER)
    for existing in styles.xpath('./w:style[@w:styleId="ContenidoJSON"]', namespaces=NS):
        styles.remove(existing)
    style = ET.SubElement(styles, W + 'style', {W + 'type': 'character', W + 'styleId': STYLE})
    ET.SubElement(style, W + 'name', {W + 'val': 'Contenido procedente del JSON'})
    files['word/styles.xml'] = xml_bytes(styles)
    # Retirar también marcas heredadas de los estilos y partes del machote.
    for name, data in list(files.items()):
        if name.startswith('word/') and name.endswith('.xml'):
            part = ET.fromstring(data, PARSER)
            changed = False
            for node in list(part.iter()):
                if ((node.tag == W + 'highlight' and node.get(W + 'val') == 'yellow')
                        or (node.tag == W + 'shd' and node.get(W + 'fill', '').upper() == 'FFFF00')):
                    node.getparent().remove(node)
                    changed = True
            if changed:
                files[name] = xml_bytes(part)
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / nombre_documento(result['municipio'])
    with tempfile.TemporaryDirectory(prefix='.render-', dir=output_dir) as directory:
        temporary = Path(directory) / 'documento.docx'
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        audit = auditar(temporary, generated, originals)
        os.replace(temporary, dest)
    return {**audit, 'archivo': str(dest), 'sha256': sha256(dest), 'modo': mode, 'perfil': perfil,
            'json_fuente': str(json_path), 'json_sha256': hashlib.sha256(raw).hexdigest(),
            'plantilla_sha256': sha256(template), 'contrato_documental_sha256': sha256(CONTRACT),
            'ilustraciones': originals,
            'formato_ilustraciones': 'Reproducción fiel; tipografía de origen incrustada en los píxeles.' if originals else 'Sin ilustraciones.'}


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
    parser.add_argument('--modo', choices=('final',), default='final')
    parser.add_argument('--documento', choices=('medicion',), default='medicion')
    args = parser.parse_args()
    try:
        report = renderizar(args.json, args.output, args.modo, perfil=args.documento)
        word = Path(report['archivo']); receipt = args.output.parent / 'json' / (slug(word.stem) + '_renderizado.json')
        guardar_recibo(report, receipt)
        print(f"Word (medicion): {word}. Inserciones verificadas: {report['segmentos_json']} segmentos.")
        removidos = limpiar_salidas(args.output.parent / 'json', args.output, json_actual=args.json,
                                    word_actual=word, recibo_actual=receipt)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(f'Limpieza de salidas: {removidos}')


if __name__ == '__main__':
    main()
