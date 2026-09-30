"""Reproduce imágenes del documento fuente, sin dibujar ni alterar sus píxeles."""
from copy import deepcopy
import hashlib
from pathlib import Path, PurePosixPath
import posixpath
import zipfile

from lxml import etree as ET
from documentos import sha256

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
PARSER = ET.XMLParser(resolve_entities=False, no_network=True)


def texto(node):
    return ''.join(t.text or '' for t in node.iter(W + 't'))


def catalogar_graficas(path):
    """Asocia cada imagen de SEGURIDAD con su indicador y ámbito documental."""
    path = Path(path)
    checksum = sha256(path)
    result = []
    with zipfile.ZipFile(path) as archive:
        body = ET.fromstring(archive.read('word/document.xml'), PARSER).find(W + 'body')
        relations = ET.fromstring(archive.read('word/_rels/document.xml.rels'), PARSER)
        rels = {r.get('Id'): r for r in relations}
        active = False
        indicator = 0
        scope = None
        for position, block in enumerate(body, 1):
            label = texto(block).strip()
            if label == 'SEGURIDAD':
                active = True
            elif active and label.startswith('DESARROLLO URBANO SOSTENIBLE'):
                break
            elif active and label.startswith('Indicador:'):
                indicator += 1
                scope = None
            elif active and label in ('Datos Estatales', 'Datos Municipales'):
                scope = 'estatal' if label == 'Datos Estatales' else 'municipal'
            if not active or not 1 <= indicator <= 18:
                continue
            for blip in block.iter(A + 'blip'):
                relation = rels.get(blip.get(R + 'embed'))
                if relation is None or relation.get('TargetMode') == 'External':
                    continue
                part = posixpath.normpath(posixpath.join('word', relation.get('Target', '')))
                if not part.startswith('word/media/') or PurePosixPath(part).suffix.lower() not in ('.png', '.jpg', '.jpeg'):
                    continue
                raw = archive.read(part)
                result.append({'fuente': path.name, 'fuente_sha256': checksum,
                               'parte': part, 'sha256': hashlib.sha256(raw).hexdigest(),
                               'indicador': indicator, 'ambito': scope, 'bloque': position,
                               'relacion': relation.get('Id')})
    return result


def seleccionar_graficas(catalogue, choices):
    """La selección editorial debe identificar imágenes realmente presentes."""
    selected = []
    seen = set()
    for choice in choices:
        key = (choice.get('fuente'), choice.get('parte'))
        matches = [item for item in catalogue if (item['fuente'], item['parte']) == key
                   and item['indicador'] == choice.get('indicador')]
        if len(matches) != 1 or key in seen:
            raise ValueError(f'Ilustración ausente, ambigua o repetida: {key}.')
        after = choice.get('despues_parrafo', 0)
        if type(after) is not int or after < 0:
            raise ValueError('La posición de una ilustración debe ser un párrafo válido.')
        selected.append({**matches[0], 'despues_parrafo': after})
        seen.add(key)
    return selected


def importar_grafica(files, source, spec, index, max_width):
    """Copia los bytes y remapea únicamente relaciones, tamaño y nombre interno."""
    source = Path(source)
    if source.name != spec['fuente'] or sha256(source) != spec['fuente_sha256']:
        raise ValueError('Cambió la fuente de una ilustración seleccionada.')
    with zipfile.ZipFile(source) as archive:
        raw = archive.read(spec['parte'])
        if hashlib.sha256(raw).hexdigest() != spec['sha256']:
            raise ValueError('La imagen seleccionada no coincide con su huella documental.')
        body = ET.fromstring(archive.read('word/document.xml'), PARSER).find(W + 'body')
        block = body[spec['bloque'] - 1]
        source_drawing = next((drawing for drawing in block.iter(W + 'drawing')
                               if any(b.get(R + 'embed') == spec['relacion'] for b in drawing.iter(A + 'blip'))), None)
        if source_drawing is None:
            raise ValueError('No se encontró la ilustración en su posición documental.')
        drawing = deepcopy(source_drawing)
    inline = drawing.find(WP + 'inline')
    if inline is None:
        raise ValueError('La ilustración necesita una disposición compatible para reproducirse.')
    extension = PurePosixPath(spec['parte']).suffix.lower()
    destination = f'word/media/evidencia_{spec["sha256"]}{extension}'
    files[destination] = raw
    relationships = ET.fromstring(files['word/_rels/document.xml.rels'], PARSER)
    rid = f'rIdEvidencia{index}'
    if any(r.get('Id') == rid for r in relationships):
        raise ValueError('Identificador de ilustración repetido.')
    ET.SubElement(relationships, REL + 'Relationship', {
        'Id': rid, 'Type': R[1:-1] + '/image', 'Target': destination.removeprefix('word/')})
    files['word/_rels/document.xml.rels'] = ET.tostring(relationships, xml_declaration=True, encoding='UTF-8', standalone=True)
    for blip in drawing.iter(A + 'blip'):
        blip.set(R + 'embed', rid)
    extent = inline.find(WP + 'extent')
    width, height = int(extent.get('cx')), int(extent.get('cy'))
    scale = min(1, max_width / width)
    width, height = round(width * scale), round(height * scale)
    extent.set('cx', str(width)); extent.set('cy', str(height))
    for size in drawing.iter(A + 'ext'):
        size.set('cx', str(width)); size.set('cy', str(height))
    for props in drawing.iter(WP + 'docPr'):
        props.set('id', str(1000 + index))
        props.set('name', f'Gráfica documental {index}')
        props.set('descr', f'Información {spec["ambito"]} del indicador {spec["indicador"]}.')
    types = ET.fromstring(files['[Content_Types].xml'], PARSER)
    ext = extension.lstrip('.')
    if not any(item.get('Extension') == ext for item in types):
        ET.SubElement(types, CT + 'Default', {'Extension': ext, 'ContentType': 'image/png' if ext == 'png' else 'image/jpeg'})
    files['[Content_Types].xml'] = ET.tostring(types, xml_declaration=True, encoding='UTF-8', standalone=True)
    paragraph = ET.Element(W + 'p')
    props = ET.SubElement(paragraph, W + 'pPr')
    ET.SubElement(props, W + 'keepNext')
    ET.SubElement(props, W + 'spacing', {W + 'before': '0', W + 'after': '0', W + 'lineRule': 'atLeast', W + 'line': '320'})
    ET.SubElement(props, W + 'jc', {W + 'val': 'center'})
    ET.SubElement(paragraph, W + 'r').append(drawing)
    return paragraph, {'parte_salida': destination, 'sha256': spec['sha256'],
                       'fuente': spec['fuente'], 'parte_fuente': spec['parte'],
                       'indicador': spec['indicador']}
