"""Roles por posición y comprobación del formato efectivamente escrito en OOXML."""
from collections import Counter
from copy import deepcopy
import re
from lxml import etree as ET
from editorial import W, cargar_formato, configurar, estilos_permitidos, rol_estilo

MARKER = re.compile(r'(?<!\{)\{([a-z][a-z0-9_]*)\}(?!\})')


def texto(node):
    return ''.join(n.text or '' for n in node.iter(W + 't'))


def rol_variable(key):
    if key.startswith('calificacion_'):
        return 'calificacion'
    return 'bibliografia' if key == 'bibliografia' else 'cuerpo'


def preparar_base(root, manifest):
    """Normaliza posiciones originales y marcadores antes de sustituirlos."""
    config = cargar_formato()
    roles = {f'origen_{b["indice"]:03d}': b['rol_editorial'] for b in manifest['bloques']}
    for control in root.findall(W + 'body/' + W + 'sdt'):
        tag = control.find(W + 'sdtPr/' + W + 'tag').get(W + 'val')
        for i, p in enumerate(control.findall(W + 'sdtContent/' + W + 'p')):
            keys = MARKER.findall(texto(p))
            if tag == 'origen_000' and i > 0:
                role = 'identidad'
            elif keys:
                role = rol_variable(keys[0])
            elif tag == 'adicional_fuentes':
                role = 'subcapitulo'
            else:
                role = roles[tag] if i == 0 else 'cuerpo'
            configurar(p, rol=role, config=config)


def normalizar_notas(files):
    """Da formato a notas existentes; no crea llamadas ni referencias ficticias."""
    for name in ('word/footnotes.xml', 'word/endnotes.xml'):
        if name not in files:
            continue
        root = ET.fromstring(files[name])
        for note in root:
            if note.get(W + 'type') in ('separator', 'continuationSeparator') or note.get(W + 'id') in ('-1', '0'):
                continue
            for p in note.iter(W + 'p'):
                configurar(p, rol='nota')
        files[name] = ET.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)


def _firma(node):
    if node is None:
        return None
    return (node.tag, tuple(sorted(node.attrib.items())), node.text, tuple(_firma(c) for c in node))


def validar_parrafo(p, expected_role=None, initial=None, config=None):
    config = config or cargar_formato()
    role = rol_estilo(p)
    if role is None:
        raise ValueError('Párrafo sin rol editorial: ' + texto(p)[:65])
    if expected_role is not None and role[0] != expected_role:
        raise ValueError(f'Rol editorial incorrecto: se requiere {expected_role}, no {role[0]}.')
    if initial is not None and role[1] != initial:
        raise ValueError('Sangría inicial/de continuación distinta a la posición del bloque.')
    if p.find(W + 'pPr/' + W + 'pStyle').get(W + 'val') not in estilos_permitidos(config):
        raise ValueError('Rol editorial desconocido.')
    expected = configurar(deepcopy(p), rol=role[0], inicial=role[1], config=config)
    if _firma(p) != _firma(expected):
        raise ValueError(f'Formato editorial incorrecto ({role[0]}): ' + texto(p)[:70])
    return role[0]


def validar_editorial(files, manifest):
    """Rechaza salida fuera del manual; se ejecuta tras abrir de nuevo el DOCX."""
    config = cargar_formato()
    root = ET.fromstring(files['word/document.xml'])
    counts = Counter()
    controls = {c.find(W + 'sdtPr/' + W + 'tag').get(W + 'val'): c.find(W + 'sdtContent')
                for c in root.findall(W + 'body/' + W + 'sdt')}
    for block in manifest['bloques']:
        content = controls[f'origen_{block["indice"]:03d}']
        first = content[0]
        validar_parrafo(first, expected_role=block['rol_editorial'], initial=True, config=config)
    for p in root.iter(W + 'p'):
        if any(a.tag == W + 'sdtContent' and a.getparent().find(W + 'sdtPr/' + W + 'tag').get(W + 'val') == 'adicional_portada'
               for a in p.iterancestors() if a.getparent() is not None and a.getparent().tag == W + 'sdt'):
            continue  # La portada tiene su auditoría de título, sección y logo.
        counts[validar_parrafo(p, config=config)] += 1
    # El rol no puede ocultar cambios de tamaño en tablas ni en referencias.
    for table in root.iter(W + 'tbl'):
        for i, row in enumerate(table.findall(W + 'tr')):
            for p in row.iter(W + 'p'):
                validar_parrafo(p, expected_role='tabla_titulo' if i == 0 else 'tabla_cuerpo', config=config)
    refs = controls['adicional_fuentes'].findall(W + 'p')
    validar_parrafo(refs[0], 'subcapitulo', config=config)
    biblio = [p for p in refs[1:] if rol_estilo(p) and rol_estilo(p)[0] == 'bibliografia']
    if not biblio:
        raise ValueError('Bibliografía editorial ausente.')
    for i, p in enumerate(biblio):
        validar_parrafo(p, 'bibliografia', initial=i == 0, config=config)
    styles = ET.fromstring(files['word/styles.xml'])
    defined = {s.get(W + 'styleId') for s in styles.findall(W + 'style')}
    if not estilos_permitidos(config).issubset(defined):
        raise ValueError('Faltan estilos editoriales del manual.')
    footnotes = 0
    for name in ('word/footnotes.xml', 'word/endnotes.xml'):
        if name not in files:
            continue
        notes = ET.fromstring(files[name])
        for note in notes:
            if note.get(W + 'type') in ('separator', 'continuationSeparator') or note.get(W + 'id') in ('-1', '0'):
                continue
            footnotes += 1
            for p in note.iter(W + 'p'):
                validar_parrafo(p, 'nota', config=config)
    from graficas_word import validar_graficas
    from logo_editorial import validar_portada
    charts = validar_graficas(files)
    expected_charts = sum(key.startswith('graficas_') for block in manifest['bloques'] for key in block['variables'])
    c = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
    r = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    drawings = root.findall('.//' + c + 'chart')
    relations = {node.get('Id'): node for node in ET.fromstring(files['word/_rels/document.xml.rels'])}
    if len(drawings) != expected_charts or charts['graficas_editoriales_verificadas'] != expected_charts:
        raise ValueError('Faltan gráficas editoriales requeridas por el contrato.')
    targets = []
    for drawing in drawings:
        relation = relations.get(drawing.get(r + 'id'))
        if relation is None or relation.get('TargetMode') == 'External':
            raise ValueError('Gráfica editorial sin relación interna válida.')
        target = 'word/' + relation.get('Target', '')
        if relation.get('Type') != r[1:-1] + '/chart' or target not in files:
            raise ValueError('Gráfica editorial sin archivo vinculado.')
        targets.append(target)
    if len(set(targets)) != expected_charts:
        raise ValueError('Gráficas editoriales duplicadas en lugar de indicadores distintos.')
    return {'formato_editorial_verificado': True, 'formato_editorial_version': config['version'],
            'parrafos_editoriales_por_rol': dict(counts), 'notas_al_pie_o_finales': footnotes,
            **charts, **validar_portada(files, root)}
