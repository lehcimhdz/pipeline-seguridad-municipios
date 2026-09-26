"""Trazabilidad estructural entre cada bloque del original y el Word rellenado."""
from copy import deepcopy
from lxml import etree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def firma(node):
    if node is None:
        return None
    return (node.tag, tuple(sorted(node.attrib.items())), node.text,
            tuple(firma(child) for child in node))


def envolver(block, index):
    control = ET.Element(W + 'sdt')
    props = ET.SubElement(control, W + 'sdtPr')
    ET.SubElement(props, W + 'tag', {W + 'val': f'origen_{index:03d}'})
    ET.SubElement(props, W + 'alias', {W + 'val': f'Bloque {index} del machote original'})
    ET.SubElement(control, W + 'sdtContent').append(deepcopy(block))
    return control


def controles(root):
    result = {}
    for control in root.findall(W + 'body/' + W + 'sdt'):
        tag = control.find(W + 'sdtPr/' + W + 'tag')
        if tag is None or tag.get(W + 'val') in result:
            raise ValueError('Control documental sin origen único.')
        result[tag.get(W + 'val')] = control.find(W + 'sdtContent')
    return result


def validar_estilos(original_files, actual_files, salida=False):
    source = ET.fromstring(original_files['word/styles.xml'])
    current = ET.fromstring(actual_files['word/styles.xml'])
    if source.attrib != current.attrib or [firma(n) for n in source if n.tag != W + 'style'] != [
            firma(n) for n in current if n.tag != W + 'style']:
        raise ValueError('Cambió la configuración global de estilos del machote original.')
    original_styles = {node.get(W + 'styleId'): node for node in source.findall(W + 'style')}
    current_styles = {node.get(W + 'styleId'): node for node in current.findall(W + 'style')}
    if len(current_styles) != len(current.findall(W + 'style')) or None in current_styles:
        raise ValueError('Estilos sin identificador único.')
    for style_id, node in original_styles.items():
        if firma(node) != firma(current_styles.get(style_id)):
            raise ValueError(f'Cambió el estilo original del machote: {style_id}.')
    allowed = {'ContenidoJSON'} if salida else set()
    if set(current_styles) - set(original_styles) - allowed:
        raise ValueError('Se añadieron estilos ajenos al contenido JSON.')


def validar(original_files, actual_files, manifest, salida=False):
    original = ET.fromstring(original_files['word/document.xml'])
    actual = ET.fromstring(actual_files['word/document.xml'])
    original_body = original.find(W + 'body')
    actual_body = actual.find(W + 'body')
    controls = controles(actual)
    expected = [f'origen_{i:03d}' for i in manifest['orden_bloques']]
    if list(controls) != expected + ['adicional_fuentes']:
        raise ValueError('El Word cambió el orden o perdió bloques del machote original.')
    if any(n.tag not in (W + 'sdt', W + 'sectPr') for n in actual_body):
        raise ValueError('Contenido agregado fuera de las posiciones del machote.')
    if firma(original_body.find(W + 'sectPr')) != firma(actual_body.find(W + 'sectPr')):
        raise ValueError('Cambió la configuración de página del machote original.')
    validar_estilos(original_files, actual_files, salida)
    for name, data in original_files.items():
        if name == 'word/numbering.xml' or name.startswith(('word/header', 'word/footer')):
            if actual_files.get(name) != data:
                raise ValueError(f'Cambió el formato de origen: {name}.')
    for item in manifest['bloques']:
        index = item['indice']
        source = original_body[index]
        content = controls[f'origen_{index:03d}']
        if len(content) == 0:
            raise ValueError(f'Bloque del machote vacío: {index}.')
        first = content[0]
        if item['accion'] in ('conservar', 'ampliar'):
            if firma(source) != firma(first):
                raise ValueError(f'Contenido fijo del machote alterado: bloque {index}.')
        elif firma(source.find(W + 'pPr')) != firma(first.find(W + 'pPr')):
            raise ValueError(f'Formato o numeración original alterados: bloque {index}.')
        if not salida and item['accion'] == 'conservar' and len(content) != 1:
            raise ValueError(f'Contenido inesperado en bloque original {index}.')
    return {'bloques_origen_verificados': len(manifest['bloques']),
            'fidelidad_machote_verificada': True}
