"""Gráficas nativas de Word con caché de valores y fuentes del manual editorial."""
import json
from pathlib import Path
from lxml import etree as ET

FORMATO = Path(__file__).resolve().parents[1] / 'config/formato_editorial.json'

C = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'


def node(parent, name, val=None, ns=C):
    return ET.SubElement(parent, ns + name, {} if val is None else {'val': str(val)})


def rich(parent, definition, text=None):
    font, size, line = definition
    node(parent, 'bodyPr', ns=A)
    node(parent, 'lstStyle', ns=A)
    p = node(parent, 'p', ns=A)
    paragraph_props = node(p, 'pPr', ns=A)
    node(node(paragraph_props, 'lnSpc', ns=A), 'spcPts', int(line * 100), ns=A)
    props = node(paragraph_props, 'defRPr', ns=A)
    props.set('sz', str(size * 100))
    props.set('b', '0')
    props.set('i', '0')
    ET.SubElement(props, A + 'latin', {'typeface': font})
    if text is not None:
        r = node(p, 'r', ns=A)
        rpr = node(r, 'rPr', ns=A); rpr.set('sz', str(size * 100))
        rpr.set('b', '0'); rpr.set('i', '0')
        ET.SubElement(rpr, A + 'latin', {'typeface': font})
        node(r, 't', ns=A).text = text
    return parent


def agregar_grafica(files, spec, number):
    format_config = json.loads(FORMATO.read_text(encoding='utf-8'))['grafica']
    pairs = [(category, value) for category, value in zip(spec['categorias'], spec['valores']) if value is not None]
    if not pairs:
        raise ValueError('Gráfica sin valores calculados.')
    root = ET.Element(C + 'chartSpace', nsmap={'c': C[1:-1], 'a': A[1:-1], 'r': R[1:-1]})
    chart = node(root, 'chart')
    title = node(chart, 'title')
    rich(node(node(title, 'tx'), 'rich'), format_config['titulo'], spec['titulo'])
    plot = node(chart, 'plotArea')
    node(plot, 'layout')
    bar = node(plot, 'barChart')
    node(bar, 'barDir', 'col'); node(bar, 'grouping', 'clustered')
    series = node(bar, 'ser')
    node(series, 'idx', 0); node(series, 'order', 0)
    node(node(series, 'tx'), 'v').text = 'Calificación documental (1–5)'
    fill = node(node(series, 'spPr'), 'solidFill', ns=A)
    ET.SubElement(fill, A + 'srgbClr', {'val': '1F4E78'})
    cat = node(node(series, 'cat'), 'strLit')
    node(cat, 'ptCount', len(pairs))
    vals = node(node(series, 'val'), 'numLit')
    node(vals, 'formatCode').text = '0'
    node(vals, 'ptCount', len(pairs))
    for i, (category, value) in enumerate(pairs):
        p = node(cat, 'pt'); p.set('idx', str(i)); node(p, 'v').text = category
        p = node(vals, 'pt'); p.set('idx', str(i)); node(p, 'v').text = str(value)
    labels = node(bar, 'dLbls')
    rich(node(labels, 'txPr'), format_config['datos'])
    node(labels, 'dLblPos', 'outEnd')
    for field in ('showLegendKey', 'showVal', 'showCatName', 'showSerName', 'showPercent', 'showBubbleSize'):
        node(labels, field, int(field == 'showVal'))
    node(bar, 'axId', 1); node(bar, 'axId', 2)
    for kind, axis_id, cross_id, position in [('catAx', 1, 2, 'b'), ('valAx', 2, 1, 'l')]:
        axis = node(plot, kind)
        node(axis, 'axId', axis_id)
        scaling = node(axis, 'scaling'); node(scaling, 'orientation', 'minMax')
        if kind == 'valAx':
            node(scaling, 'max', 5); node(scaling, 'min', 0)
        node(axis, 'delete', 0); node(axis, 'axPos', position)
        if kind == 'valAx':
            fmt = node(axis, 'numFmt'); fmt.set('formatCode', '0'); fmt.set('sourceLinked', '0')
        node(axis, 'tickLblPos', 'nextTo')
        rich(node(axis, 'txPr'), format_config['categorias' if kind == 'catAx' else 'ejes'])
        node(axis, 'crossAx', cross_id); node(axis, 'crosses', 'autoZero')
        if kind == 'catAx':
            node(axis, 'auto', 1); node(axis, 'lblAlgn', 'ctr'); node(axis, 'lblOffset', 100)
        else:
            node(axis, 'crossBetween', 'between'); node(axis, 'majorUnit', 1)
    node(chart, 'plotVisOnly', 1)
    node(chart, 'dispBlanksAs', 'gap')
    node(node(root, 'spPr'), 'noFill', ns=A)
    rich(node(root, 'txPr'), format_config['ejes'])
    chart_name = f'word/charts/pipeline_{number}.xml'
    files[chart_name] = ET.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
    relations = ET.fromstring(files['word/_rels/document.xml.rels'])
    rid = f'rIdPipelineChart{number}'
    ET.SubElement(relations, REL + 'Relationship', {'Id': rid,
        'Type': R[1:-1] + '/chart', 'Target': f'charts/pipeline_{number}.xml'})
    files['word/_rels/document.xml.rels'] = ET.tostring(relations, encoding='UTF-8', xml_declaration=True)
    types = ET.fromstring(files['[Content_Types].xml'])
    ET.SubElement(types, CT + 'Override', {'PartName': '/' + chart_name,
        'ContentType': 'application/vnd.openxmlformats-officedocument.drawingml.chart+xml'})
    files['[Content_Types].xml'] = ET.tostring(types, encoding='UTF-8', xml_declaration=True)
    p = ET.Element(W + 'p')
    drawing = ET.SubElement(ET.SubElement(p, W + 'r'), W + 'drawing')
    inline = ET.SubElement(drawing, WP + 'inline', {'distT': '0', 'distB': '0', 'distL': '0', 'distR': '0'})
    ET.SubElement(inline, WP + 'extent', {'cx': '5000000', 'cy': '2600000'})
    ET.SubElement(inline, WP + 'docPr', {'id': str(10000 + number), 'name': spec['titulo']})
    graphic = ET.SubElement(inline, A + 'graphic')
    data = ET.SubElement(graphic, A + 'graphicData', {'uri': C[1:-1]})
    ET.SubElement(data, C + 'chart', {R + 'id': rid})
    return p


def validar_graficas(files):
    """Comprueba el XML efectivo, no sólo la existencia de la configuración."""
    config = json.loads(FORMATO.read_text(encoding='utf-8'))['grafica']
    count = 0
    for name, data in files.items():
        if not name.startswith('word/charts/pipeline_') or not name.endswith('.xml'):
            continue
        root = ET.fromstring(data)
        paths = (
            ('titulo', './' + C + 'chart/' + C + 'title/' + C + 'tx/' + C + 'rich'),
            ('ejes', './/' + C + 'valAx/' + C + 'txPr'),
            ('categorias', './/' + C + 'catAx/' + C + 'txPr'),
            ('datos', './/' + C + 'dLbls/' + C + 'txPr'),
            ('ejes', './' + C + 'txPr'),
        )
        for role, path in paths:
            boxes = root.findall(path)
            if len(boxes) != 1:
                raise ValueError(f'Gráfica {name}: falta formato único de {role}.')
            paragraphs = boxes[0].findall(A + 'p')
            if not paragraphs:
                raise ValueError(f'Gráfica {name}: texto de {role} sin párrafo.')
            font, size, line = config[role]
            for paragraph in paragraphs:
                props = paragraph.find(A + 'pPr')
                spacing = None if props is None else props.find(A + 'lnSpc/' + A + 'spcPts')
                if spacing is None or spacing.get('val') != str(int(line * 100)):
                    raise ValueError(f'Gráfica {name}: interlineado de {role} distinto al manual.')
                char_props = [None if props is None else props.find(A + 'defRPr')]
                char_props.extend(r.find(A + 'rPr') for r in paragraph.findall(A + 'r'))
                for properties in char_props:
                    family = None if properties is None else properties.find(A + 'latin')
                    if (properties is None or properties.get('sz') != str(int(size * 100))
                            or properties.get('b') != '0' or properties.get('i') != '0'
                            or family is None or family.get('typeface') != font):
                        raise ValueError(f'Gráfica {name}: fuente o tamaño de {role} distinto al manual.')
        if root.find('.//' + A + 'highlight') is not None or any(
                n.get('val', '').upper() == 'FFFF00' for n in root.iter(A + 'srgbClr')):
            raise ValueError(f'Gráfica {name}: conserva resaltado amarillo.')
        count += 1
    return {'graficas_editoriales_verificadas': count, 'formato_graficas_verificado': True}
