"""Portada editorial con el logotipo institucional aprobado, sin recrearlo."""
from copy import deepcopy
import hashlib
import io
from pathlib import Path
import subprocess
import zipfile
from lxml import etree as ET

from editorial import configurar, normalizar_seccion, rol_estilo

ROOT = Path(__file__).resolve().parents[1]
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
PIC = '{http://schemas.openxmlformats.org/drawingml/2006/picture}'
LOGO = ROOT / 'assets/institutionworks.jpeg'
LAYOUT = ROOT / 'assets/institutionworks_logo.xml'
LOGO_WIDTH = 1800000  # 5 cm en EMU.
LOGO_HEIGHT = round(LOGO_WIDTH * 332 / 407)  # Proporción del original, 407 × 332 px.
LOGO_RID = 'rIdInstitutionworksLogo'
TITLE = 'Mediciones de Funcionamiento Municipal'


def preparar():
    if LOGO.exists() and LAYOUT.exists():
        return
    historical = subprocess.run(['git', 'show', 'pipeline-v2:templates/seguridad_medicion.docx'],
                                cwd=ROOT, check=True, capture_output=True).stdout
    with zipfile.ZipFile(io.BytesIO(historical)) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
        p = next(p for p in root.iter(W + 'p') if p.find('.//' + W + 'drawing') is not None)
        blip = p.find('.//' + A + 'blip')
        rid = blip.get(R + 'embed')
        rels = ET.fromstring(archive.read('word/_rels/document.xml.rels'))
        target = next(r.get('Target') for r in rels if r.get('Id') == rid)
        LOGO.write_bytes(archive.read('word/' + target))
        blip.set(R + 'embed', 'rIdInstitutionworksLogo')
        LAYOUT.write_bytes(ET.tostring(p, encoding='UTF-8', xml_declaration=True))


def insertar(files):
    preparar()
    files['word/media/institutionworks.jpeg'] = LOGO.read_bytes()
    rels = ET.fromstring(files['word/_rels/document.xml.rels'])
    matching = [r for r in rels if r.get('Id') == LOGO_RID]
    if matching and (len(matching) != 1 or matching[0].get('Target') != 'media/institutionworks.jpeg'
                     or matching[0].get('Type') != R[1:-1] + '/image'):
        raise ValueError('La relación del logotipo institucional está ocupada por otro recurso.')
    if not matching:
        ET.SubElement(rels, REL + 'Relationship', {'Id': LOGO_RID,
            'Type': R[1:-1] + '/image', 'Target': 'media/institutionworks.jpeg'})
    files['word/_rels/document.xml.rels'] = ET.tostring(rels, encoding='UTF-8', xml_declaration=True)
    types = ET.fromstring(files['[Content_Types].xml'])
    if not any(n.get('Extension') == 'jpeg' for n in types):
        ET.SubElement(types, CT + 'Default', {'Extension': 'jpeg', 'ContentType': 'image/jpeg'})
    files['[Content_Types].xml'] = ET.tostring(types, encoding='UTF-8', xml_declaration=True)
    return deepcopy(ET.fromstring(LAYOUT.read_bytes()))


def _geometria_pagina(section):
    size = section.find(W + 'pgSz')
    margins = section.find(W + 'pgMar')
    if size is None or margins is None:
        raise ValueError('La portada necesita las dimensiones y márgenes de la página original.')
    try:
        width, height = int(size.get(W + 'w')), int(size.get(W + 'h'))
        bottom = int(margins.get(W + 'bottom'))
    except (TypeError, ValueError) as exc:
        raise ValueError('Dimensiones de página no válidas para la portada.') from exc
    y = (height - bottom) * 635 - LOGO_HEIGHT  # 1 twip = 635 EMU.
    if width * 635 <= LOGO_WIDTH or y < height * 635 / 2:
        raise ValueError('La página no admite el logotipo en su parte inferior.')
    return width, height, y


def _firma(node):
    """Compara propiedades y contenido, independientemente de prefijos XML heredados."""
    return (node.tag, tuple(sorted(node.attrib.items())), node.text,
            tuple(_firma(child) for child in node))


def _marco_titulo(section):
    """Un marco de altura automática centra el bloque también fuera de Word.

    Los párrafos adyacentes con framePr idénticos pertenecen al mismo marco
    (ISO/IEC 29500). No usa espacios, saltos ni párrafos vacíos para posicionarse.
    """
    width, _, _ = _geometria_pagina(section)
    margins = section.find(W + 'pgMar')
    try:
        available = width - int(margins.get(W + 'left', '0')) - int(margins.get(W + 'right', '0'))
    except ValueError as exc:
        raise ValueError('Márgenes horizontales no válidos para la portada.') from exc
    if available <= 0:
        raise ValueError('La portada necesita un ancho útil positivo.')
    return {W + key: value for key, value in {
        'w': str(available), 'hAnchor': 'page', 'vAnchor': 'page',
        'xAlign': 'center', 'yAlign': 'center', 'hRule': 'auto', 'wrap': 'none'}.items()}


def construir_portada(files, municipio, estado, sect_original):
    """Devuelve un control de portada; no modifica el machote ni crea pies heredables."""
    if not LOGO.is_file() or not LAYOUT.is_file():
        raise ValueError('Faltan los recursos institucionales versionados de la portada.')
    if any(not isinstance(value, str) or not value.strip() for value in (municipio, estado)):
        raise ValueError('La portada necesita municipio y estado.')
    section = normalizar_seccion(deepcopy(sect_original))
    for tag in ('headerReference', 'footerReference', 'titlePg', 'pgNumType'):
        for child in section.findall(W + tag):
            section.remove(child)
    section.find(W + 'vAlign').set(W + 'val', 'center')
    _, _, y = _geometria_pagina(section)

    source_logo = insertar(files)
    graphic = deepcopy(source_logo.find('.//' + A + 'graphic'))
    if graphic is None:
        raise ValueError('El recurso institucional no contiene una imagen DrawingML.')
    for extra in list(graphic.iter(A + 'extLst')):
        extra.getparent().remove(extra)
    transform = graphic.find('.//' + PIC + 'spPr/' + A + 'xfrm')
    if transform is None or transform.find(A + 'ext') is None:
        raise ValueError('El recurso institucional no contiene la geometría de su imagen.')
    transform.find(A + 'ext').attrib.update({'cx': str(LOGO_WIDTH), 'cy': str(LOGO_HEIGHT)})
    blip = graphic.find('.//' + A + 'blip')
    blip.set(R + 'embed', LOGO_RID)

    control = ET.Element(W + 'sdt')
    props = ET.SubElement(control, W + 'sdtPr')
    ET.SubElement(props, W + 'alias', {W + 'val': 'Portada editorial'})
    ET.SubElement(props, W + 'tag', {W + 'val': 'adicional_portada'})
    content = ET.SubElement(control, W + 'sdtContent')
    paragraphs = []
    for value, generated in ((TITLE, False), ('Seguridad', False),
                             (f'{municipio}, {estado}', True)):
        paragraph = ET.SubElement(content, W + 'p')
        run = ET.SubElement(paragraph, W + 'r')
        if generated:
            ET.SubElement(ET.SubElement(run, W + 'rPr'), W + 'rStyle', {W + 'val': 'ContenidoJSON'})
        ET.SubElement(run, W + 't').text = value
        paragraphs.append(paragraph)

    drawing = ET.SubElement(ET.SubElement(paragraphs[0], W + 'r'), W + 'drawing')
    anchor = ET.SubElement(drawing, WP + 'anchor', {
        'distT': '0', 'distB': '0', 'distL': '0', 'distR': '0', 'simplePos': '0',
        'relativeHeight': '0', 'behindDoc': '0', 'locked': '0', 'layoutInCell': '1', 'allowOverlap': '1'})
    ET.SubElement(anchor, WP + 'simplePos', {'x': '0', 'y': '0'})
    ET.SubElement(ET.SubElement(anchor, WP + 'positionH', {'relativeFrom': 'page'}), WP + 'align').text = 'center'
    ET.SubElement(ET.SubElement(anchor, WP + 'positionV', {'relativeFrom': 'page'}), WP + 'posOffset').text = str(y)
    ET.SubElement(anchor, WP + 'extent', {'cx': str(LOGO_WIDTH), 'cy': str(LOGO_HEIGHT)})
    ET.SubElement(anchor, WP + 'effectExtent', {'l': '0', 't': '0', 'r': '0', 'b': '0'})
    ET.SubElement(anchor, WP + 'wrapNone')
    ET.SubElement(anchor, WP + 'docPr', {'id': '9000', 'name': 'InstitutionWorks',
                                       'descr': 'Logotipo de InstitutionWorks'})
    ET.SubElement(ET.SubElement(anchor, WP + 'cNvGraphicFramePr'), A + 'graphicFrameLocks', {'noChangeAspect': '1'})
    anchor.append(graphic)
    for paragraph in paragraphs:
        props = ET.Element(W + 'pPr')
        paragraph.insert(0, props)
        ET.SubElement(props, W + 'framePr', _marco_titulo(section))
        configurar(paragraph, rol='titulo')
    paragraphs[-1].find(W + 'pPr').append(section)
    return control


def validar_portada(files, root):
    """Verifica portada, posición absoluta y proporción del recurso institucional."""
    body = root.find(W + 'body')
    covers = [n for n in root.iter(W + 'sdt')
              if n.find(W + 'sdtPr/' + W + 'tag') is not None
              and n.find(W + 'sdtPr/' + W + 'tag').get(W + 'val') == 'adicional_portada']
    if body is None or len(covers) != 1 or len(body) == 0 or body[0] is not covers[0]:
        raise ValueError('Debe existir una única portada editorial al principio del documento.')
    cover = covers[0]
    content = cover.find(W + 'sdtContent')
    paragraphs = [] if content is None else content.findall(W + 'p')
    if len(paragraphs) != 3 or len(content) != 3:
        raise ValueError('La portada debe contener título, rubro e identidad municipal.')
    texts = [''.join(p.itertext(W + 't')) for p in paragraphs]
    if texts[:2] != [TITLE, 'Seguridad'] or not texts[2].strip() or ',' not in texts[2]:
        raise ValueError('El texto de la portada editorial no corresponde a Medición de Seguridad.')
    origin = [n for n in body.findall(W + 'sdt')
              if n.find(W + 'sdtPr/' + W + 'tag') is not None
              and n.find(W + 'sdtPr/' + W + 'tag').get(W + 'val') == 'origen_000']
    if origin:
        identities = [p for p in origin[0].iter(W + 'p') if rol_estilo(p) == ('identidad', True)]
        if len(identities) != 1 or ''.join(identities[0].itertext(W + 't')) != texts[2]:
            raise ValueError('La identidad municipal de portada no coincide con el cuerpo del diagnóstico.')
    for paragraph in paragraphs:
        if rol_estilo(paragraph) != ('titulo', True):
            raise ValueError('El título de portada no usa el estilo editorial principal.')
        expected = configurar(deepcopy(paragraph), rol='titulo')
        if _firma(paragraph) != _firma(expected):
            raise ValueError('La tipografía, interlineado o alineación de la portada no cumple el manual.')
    cover_sections = cover.findall('.//' + W + 'sectPr')
    sections = root.findall('.//' + W + 'sectPr')
    body_section = body.find(W + 'sectPr')
    if len(cover_sections) != 1 or len(sections) != 2 or body_section is None:
        raise ValueError('La portada debe tener sección propia, separada del cuerpo.')
    cover_section = cover_sections[0]
    if cover_section.getparent() is not paragraphs[-1].find(W + 'pPr'):
        raise ValueError('El salto de sección debe cerrar la portada.')
    for paragraph in paragraphs:
        frames = paragraph.findall(W + 'pPr/' + W + 'framePr')
        if len(frames) != 1 or dict(frames[0].attrib) != _marco_titulo(cover_section):
            raise ValueError('El bloque de título debe centrarse en la página con un marco de altura automática.')
    for tag in ('pgSz', 'pgMar'):
        cover_geometry, body_geometry = cover_section.find(W + tag), body_section.find(W + tag)
        if cover_geometry is None or body_geometry is None or _firma(cover_geometry) != _firma(body_geometry):
            raise ValueError('La portada debe conservar dimensiones y márgenes del cuerpo original.')
    for section, align in ((cover_section, 'center'), (body_section, 'top')):
        for tag, attribute, value in (('type', 'val', 'nextPage'), ('vAlign', 'val', align), ('cols', 'num', '1')):
            prop = section.find(W + tag)
            if prop is None or prop.get(W + attribute) != value:
                raise ValueError('Las secciones de portada y cuerpo no cumplen el formato editorial.')
    if any(cover_section.find(W + tag) is not None for tag in ('headerReference', 'footerReference')):
        raise ValueError('El logotipo de portada no debe implementarse como encabezado o pie heredable.')
    _, _, y = _geometria_pagina(cover_section)
    anchors = cover.findall('.//' + WP + 'anchor')
    if len(anchors) != 1 or cover.find('.//' + WP + 'inline') is not None:
        raise ValueError('La portada necesita un único logotipo anclado a la página.')
    anchor = anchors[0]
    horizontal, vertical = anchor.find(WP + 'positionH'), anchor.find(WP + 'positionV')
    if (horizontal is None or horizontal.get('relativeFrom') != 'page'
            or horizontal.findtext(WP + 'align') != 'center'
            or vertical is None or vertical.get('relativeFrom') != 'page'
            or vertical.findtext(WP + 'posOffset') != str(y)
            or anchor.get('behindDoc') != '0' or anchor.find(WP + 'wrapNone') is None):
        raise ValueError('El logotipo debe quedar centrado en la parte inferior de la portada.')
    extents = [anchor.find(WP + 'extent'), anchor.find('.//' + PIC + 'spPr/' + A + 'xfrm/' + A + 'ext')]
    if any(n is None or n.get('cx') != str(LOGO_WIDTH) or n.get('cy') != str(LOGO_HEIGHT) for n in extents):
        raise ValueError('El logotipo debe medir 5 cm de ancho y conservar su proporción original.')
    blips = anchor.findall('.//' + A + 'blip')
    rels = ET.fromstring(files['word/_rels/document.xml.rels'])
    logo_rels = [n for n in rels if n.get('Id') == LOGO_RID]
    if (len(blips) != 1 or blips[0].get(R + 'embed') != LOGO_RID or len(logo_rels) != 1
            or logo_rels[0].get('Type') != R[1:-1] + '/image'
            or logo_rels[0].get('Target') != 'media/institutionworks.jpeg'
            or logo_rels[0].get('TargetMode') == 'External'
            or files.get('word/media/institutionworks.jpeg') != LOGO.read_bytes()):
        raise ValueError('El logotipo de portada no coincide con el recurso institucional aprobado.')
    return {'portada_editorial_verificada': True, 'logotipo_editorial_verificado': True,
            'logotipo_ancho_cm': 5, 'logotipo_sha256': hashlib.sha256(LOGO.read_bytes()).hexdigest()}
