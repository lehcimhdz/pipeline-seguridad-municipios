"""Aplica el manual al texto visible; conserva contenido, listas y colores."""
from copy import deepcopy
import json
from pathlib import Path
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
FORMATO = ROOT / 'config/formato_editorial.json'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def cargar_formato():
    return json.loads(FORMATO.read_text(encoding='utf-8'))


def estilo_id(rol, inicial=True):
    return f'Editorial_{rol}_{"inicial" if inicial else "continuacion"}'


def especificacion(rol, perfil='medicion', config=None):
    config = config or cargar_formato()
    if rol == 'separador':
        return ['Archivo Light', 1, 1, 'left']
    if rol == 'identidad':
        return ['Archivo Light', 12, 16, 'center']
    if rol == 'figura':
        return ['Archivo Light', 12, 16, 'center']
    return config[perfil][rol]


def estilos_permitidos(config=None):
    config = config or cargar_formato()
    return {estilo_id(role, initial) for role in set(config['medicion']) | {'separador', 'identidad', 'figura'}
            for initial in (True, False)}


def rol_estilo(p):
    node = p.find(W + 'pPr/' + W + 'pStyle')
    value = node.get(W + 'val', '') if node is not None else ''
    if value.startswith('Editorial_') and value.endswith(('_inicial', '_continuacion')):
        role, position = value[len('Editorial_'):].rsplit('_', 1)
        return role, position == 'inicial'
    return None


def configurar(p, perfil='medicion', rol='cuerpo', inicial=True, config=None):
    config = config or cargar_formato()
    font, size, line, align = especificacion(rol, perfil, config)
    props = p.find(W + 'pPr')
    if props is None:
        props = ET.Element(W + 'pPr')
        p.insert(0, props)
    listed = props.find(W + 'numPr') is not None
    for key in ('pStyle', 'spacing', 'ind', 'jc', 'tabs', 'contextualSpacing', 'keepNext', 'keepLines',
                'widowControl', 'snapToGrid'):
        for node in props.findall(W + key):
            props.remove(node)
    ET.SubElement(props, W + 'pStyle', {W + 'val': estilo_id(rol, inicial)})
    rule = 'atLeast' if rol == 'figura' or (rol in ('capitulo', 'subcapitulo') and line < size) else 'exact'
    ET.SubElement(props, W + 'spacing', {W + 'before': '0', W + 'after': '0',
                                        W + 'line': str(line * 20), W + 'lineRule': rule})
    ET.SubElement(props, W + 'jc', {W + 'val': align})
    indent = str(round(config['sangria_mm'] * 1440 / 25.4))
    ind = {'left': '0', 'right': '0', 'firstLine': indent if not inicial and rol in ('cuerpo', 'bibliografia') else '0'}
    if listed:
        ind = {'left': indent, 'right': '0', 'hanging': indent}
    ET.SubElement(props, W + 'ind', {W + key: value for key, value in ind.items()})
    for key, value in (('keepNext', int(rol in ('capitulo', 'subcapitulo'))),
                       ('keepLines', 0), ('widowControl', 1), ('snapToGrid', 0)):
        ET.SubElement(props, W + key, {W + 'val': str(value)})
    # La marca de párrafo también debe usar Archivo, incluso en los vacíos.
    for parent in [props, *p.iter(W + 'r')]:
        rpr = parent.find(W + 'rPr')
        if rpr is None:
            rpr = ET.Element(W + 'rPr')
            parent.append(rpr) if parent is props else parent.insert(0, rpr)
        italic = rol == 'bibliografia' and any(n.get(W + 'val', '1') not in ('0', 'false', 'off') for n in rpr.findall(W + 'i'))
        for key in ('rFonts', 'sz', 'szCs', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'vanish', 'snapToGrid'):
            for node in rpr.findall(W + key):
                rpr.remove(node)
        ET.SubElement(rpr, W + 'rFonts', {W + key: font for key in ('ascii', 'hAnsi', 'eastAsia', 'cs')})
        for key, value in (('sz', size * 2), ('szCs', size * 2), ('b', 0), ('bCs', 0),
                           ('i', int(italic)), ('iCs', int(italic)), ('smallCaps', 0),
                           ('caps', int(rol in ('capitulo', 'calificacion'))),
                           ('vanish', int(rol == 'separador')), ('snapToGrid', 0)):
            ET.SubElement(rpr, W + key, {W + 'val': str(value)})
        order = ['rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike', 'dstrike',
                 'outline', 'shadow', 'emboss', 'imprint', 'noProof', 'snapToGrid', 'vanish', 'webHidden',
                 'color', 'spacing', 'w', 'kern', 'position', 'sz', 'szCs', 'highlight', 'u', 'effect',
                 'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs', 'em', 'lang', 'eastAsianLayout', 'specVanish']
        rpr[:] = sorted(rpr, key=lambda n: order.index(ET.QName(n).localname) if ET.QName(n).localname in order else len(order))
    order = ['pStyle', 'keepNext', 'keepLines', 'pageBreakBefore', 'framePr', 'widowControl', 'numPr',
             'suppressLineNumbers', 'pBdr', 'shd', 'tabs', 'suppressAutoHyphens', 'kinsoku', 'wordWrap',
             'overflowPunct', 'topLinePunct', 'autoSpaceDE', 'autoSpaceDN', 'bidi', 'adjustRightInd',
             'snapToGrid', 'spacing', 'ind', 'contextualSpacing', 'mirrorIndents', 'suppressOverlap',
             'jc', 'textDirection', 'textAlignment', 'textboxTightWrap', 'outlineLvl', 'divId', 'cnfStyle', 'rPr', 'sectPr']
    props[:] = sorted(props, key=lambda n: order.index(ET.QName(n).localname) if ET.QName(n).localname in order else len(order))
    return p


def incorporar_estilos(files):
    """Añade estilos del manual; no reescribe estilos históricos sin usar."""
    config = cargar_formato()
    styles = ET.fromstring(files['word/styles.xml'])
    allowed = estilos_permitidos(config)
    for old in list(styles):
        if old.tag == W + 'style' and old.get(W + 'styleId') in allowed:
            styles.remove(old)
    for role in sorted(set(config['medicion']) | {'separador', 'identidad', 'figura'}):
        for initial in (True, False):
            example = configurar(ET.Element(W + 'p'), rol=role, inicial=initial, config=config)
            props = example.find(W + 'pPr')
            props.remove(props.find(W + 'pStyle'))
            rprops = props.find(W + 'rPr')
            props.remove(rprops)
            style = ET.SubElement(styles, W + 'style', {W + 'type': 'paragraph', W + 'styleId': estilo_id(role, initial)})
            ET.SubElement(style, W + 'name', {W + 'val': 'Manual editorial: ' + role + (' inicial' if initial else ' continuación')})
            style.extend([deepcopy(props), deepcopy(rprops)])
    files['word/styles.xml'] = ET.tostring(styles, encoding='UTF-8', xml_declaration=True, standalone=True)


def normalizar_seccion(sect):
    """Cuerpo tras portada: una columna, sin heredar centrado vertical."""
    for tag in ('type', 'vAlign', 'cols'):
        for node in sect.findall(W + tag):
            sect.remove(node)
    sect.insert(0, ET.Element(W + 'type', {W + 'val': 'nextPage'}))
    cols = ET.Element(W + 'cols', {W + 'num': '1', W + 'space': '708'})
    grid = sect.find(W + 'docGrid')
    idx = sect.index(grid) if grid is not None else len(sect)
    sect.insert(idx, cols)
    sect.insert(idx + 1, ET.Element(W + 'vAlign', {W + 'val': 'top'}))
    return sect
