"""Deriva una sola base de SEGURIDAD y registra su contrato documental.

El machote general es de sólo lectura. Su capítulo parametrizado se copia en
el orden original; la base técnica añade portada, introducción y conclusiones.
Las reglas se regeneran por separado con estructurar_reglas.py.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import zipfile
from lxml import etree as ET
from documentos import sha256
from editorial import configurar, FORMATO
from fuentes_word import incrustar, FONTS

ROOT = Path(__file__).resolve().parents[1]
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MARKER = re.compile(r'(?<!\{)\{([a-z][a-z0-9_]*)\}(?!\})')
SOURCE = ROOT / 'templates/Machote general medicion version final.docx'
BASE = ROOT / 'templates/seguridad_medicion.docx'
REDACCION = ROOT / 'config/redaccion_consultoria.json'


def text(node):
    return ''.join(t.text or '' for t in node.iter(W + 't'))


def paragraph(value, model=None):
    p = ET.Element(W + 'p')
    if model is not None and model.find(W + 'pPr') is not None:
        p.append(deepcopy(model.find(W + 'pPr')))
    ET.SubElement(ET.SubElement(p, W + 'r'), W + 't').text = value
    return p


def save(path, files):
    with tempfile.NamedTemporaryFile(suffix='.docx', dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                # Fecha ZIP fija: mismos insumos producen la misma huella de la base.
                z.writestr(zipfile.ZipInfo(name), data, compress_type=zipfile.ZIP_DEFLATED)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def depurar_notas(files, document):
    """No transportar las notas de los capítulos excluidos de la salida."""
    for kind in ('footnote', 'endnote'):
        filename = f'word/{kind}s.xml'
        if filename not in files:
            continue
        references = {node.get(W + 'id') for node in document.iter(W + kind + 'Reference')}
        notes = ET.fromstring(files[filename])
        for node in list(notes):
            if node.tag == W + kind and int(node.get(W + 'id')) > 0 and node.get(W + 'id') not in references:
                notes.remove(node)
        files[filename] = ET.tostring(notes, encoding='UTF-8', xml_declaration=True, standalone=True)


def extraer_capitulo(root, catalog):
    """Conserva todos los bloques originales; no reconstruye los indicadores."""
    blocks = list(root.find(W + 'body'))
    starts = [i for i, block in enumerate(blocks) if text(block).strip() == 'SEGURIDAD']
    if len(starts) != 1:
        raise ValueError('El machote debe tener un capítulo SEGURIDAD único.')
    start = starts[0]
    end = next((i for i in range(start + 1, len(blocks))
                if text(blocks[i]).strip().startswith('DESARROLLO URBANO SOSTENIBLE')), None)
    if end is None:
        raise ValueError('No se encontró el límite del capítulo SEGURIDAD en el machote.')
    section = [deepcopy(block) for block in blocks[start:end]]
    headings = [text(block).strip() for block in section
                if text(block).strip().startswith('Indicador ')]
    expected_headings = [f"Indicador {entry['id']:02d}: {entry['nombre']}" for entry in catalog]
    if headings != expected_headings:
        raise ValueError('Los 18 indicadores del machote cambiaron: revisar su correspondencia con el diccionario.')
    markers = Counter(MARKER.findall(''.join(text(block) for block in section)))
    expected = Counter(['calificacion_general', 'calificacion_ultimo_periodo',
                        'resumen_general', 'resumen_ultimo_periodo'])
    expected.update(f'{prefix}_indicador_{number:02d}' for number in range(1, 19)
                    for prefix in ('analisis', 'graficas', 'tablas', 'cierre'))
    if markers != expected:
        raise ValueError('Los marcadores del capítulo original cambiaron; revisar la parametrización antes de migrar.')
    return section


def portada(root, section_properties):
    """Aplica el manual de medición y reutiliza el logo original."""
    title = configurar(paragraph('Mediciones de Funcionamiento Municipal — SEGURIDAD'), 'medicion', 'titulo')
    layout = json.loads(FORMATO.read_text(encoding='utf-8'))
    page = section_properties.find(W + 'pgSz')
    margins = section_properties.find(W + 'pgMar')
    usable = int(page.get(W + 'h')) - int(margins.get(W + 'top')) - int(margins.get(W + 'bottom'))
    line = layout['medicion']['titulo'][2] * 20
    title.find(W + 'pPr/' + W + 'spacing').set(W + 'before', str(max(0, (usable - 2 * line) // 2)))
    identity = configurar(paragraph('{municipio}, {estado}'), 'medicion', 'cuerpo')
    identity.find(W + 'pPr/' + W + 'jc').set(W + 'val', 'center')
    cover = [title, identity]
    logo = next((deepcopy(p) for p in root.iter(W + 'p')
                 if p.find('.//' + W + 'drawing') is not None), None)
    if logo is None:
        raise ValueError('No se encontró el logo original de la portada.')
    configurar(logo, 'medicion', 'cuerpo')
    logo.find(W + 'pPr/' + W + 'jc').set(W + 'val', 'center')
    wp = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
    a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
    for ext in logo.iter(wp + 'extent'):
        old_x, old_y = int(ext.get('cx')), int(ext.get('cy'))
        x, y = 1800000, round(old_y * 1800000 / old_x)
        ext.set('cx', str(x)); ext.set('cy', str(y))
        for size in logo.iter(a + 'ext'):
            size.set('cx', str(x)); size.set('cy', str(y))
    inline = logo.find('.//' + wp + 'inline')
    if inline is not None:
        anchor = ET.Element(wp + 'anchor', {'distT': '0', 'distB': '0', 'distL': '0', 'distR': '0',
            'simplePos': '0', 'relativeHeight': '0', 'behindDoc': '0', 'locked': '0',
            'layoutInCell': '1', 'allowOverlap': '1'})
        ET.SubElement(anchor, wp + 'simplePos', {'x': '0', 'y': '0'})
        ET.SubElement(ET.SubElement(anchor, wp + 'positionH', {'relativeFrom': 'page'}), wp + 'align').text = 'center'
        ET.SubElement(ET.SubElement(anchor, wp + 'positionV', {'relativeFrom': 'margin'}), wp + 'align').text = 'bottom'
        for tag in ('extent', 'effectExtent'):
            node = inline.find(wp + tag)
            if node is not None:
                anchor.append(deepcopy(node))
        ET.SubElement(anchor, wp + 'wrapNone')
        for tag in ('docPr', 'cNvGraphicFramePr'):
            node = inline.find(wp + tag)
            if node is not None:
                anchor.append(deepcopy(node))
        anchor.append(deepcopy(inline.find(a + 'graphic')))
        inline.getparent().replace(inline, anchor)
    cover.append(logo)
    cover_section = deepcopy(section_properties)
    for node in cover_section.findall(W + 'vAlign'):
        cover_section.remove(node)
    valign = ET.Element(W + 'vAlign', {W + 'val': 'top'})
    grid = cover_section.find(W + 'docGrid')
    cover_section.insert(cover_section.index(grid) if grid is not None else len(cover_section), valign)
    break_p = paragraph('')
    props = ET.Element(W + 'pPr'); break_p.insert(0, props)
    props.append(cover_section)
    cover.append(break_p)
    return cover


def definir_variable(key, count):
    descriptions = {
        'municipio': 'Nombre del municipio común a las dos entradas documentales.',
        'estado': 'Entidad federativa identificada en el Anexo y consistente con el municipio.',
        'introduccion_seguridad': 'Objeto del estudio, tres dimensiones y alcance temporal de los documentos recibidos.',
        'conclusiones_seguridad': 'Síntesis de fortalezas, carencias y prioridades sustentadas en los hallazgos de seguridad.',
        'resumen_general': 'Balance del periodo completo, resultados por dimensión y límites sustantivos de la evidencia.',
        'resumen_ultimo_periodo': 'Balance del intervalo reciente común; distinguir ausencia de datos de desempeño desfavorable.',
        'calificacion_general': 'Categoría del periodo general calculada con las reglas; PENDIENTE si falta evidencia necesaria.',
        'calificacion_ultimo_periodo': 'Categoría del periodo reciente calculada con las reglas; PENDIENTE si falta evidencia necesaria.',
        'bibliografia': 'Títulos legibles de los dos documentos efectivamente utilizados, sin rutas ni huellas digitales.',
    }
    prefixes = {
        'analisis': 'Lectura de los datos del indicador: evolución, alcance y comparación válida; lenguaje consultivo.',
        'cierre': 'Implicación concreta de los hallazgos del indicador, sin causas ni efectos no acreditados.',
        'tablas': 'Tablas municipales y estatales del paquete de seguridad; conservar valores y referencias de origen.',
        'graficas': 'Comparación de puntajes efectivamente calculados; no dibujar valores faltantes como cero.',
    }
    prefix = key.split('_', 1)[0]
    kind = 'array' if prefix in ('graficas', 'tablas') else 'string'
    return {
        'marcador': '{' + key + '}', 'apariciones': count,
        'apariciones_por_documento': {'medicion': count}, 'tipo_dato': kind,
        'tipo_contenido': prefix if kind == 'array' else 'texto',
        'debe_contener': descriptions.get(key, prefixes.get(prefix, 'Texto sustentado en las dos fuentes autorizadas.')),
        'obligatorio': prefix != 'graficas',
    }


def depurar_diccionario(previous, found, rules):
    """Describe la única salida activa; descarta productos y modelos históricos."""
    dimensions = deepcopy(previous['catalogos']['dimensiones'])
    for dimension in dimensions:
        dimension['indicadores'] = rules['dimensiones'][dimension['codigo']]
    return {
        'metadatos': {
            'version': '2.1', 'nombre': 'diccionario_variables_diagnostico_seguridad_municipal',
            'idioma': 'es-MX', 'tipo_documento': 'diccionario_de_datos_y_especificacion_de_contenido',
            'es_json_schema_formal': False,
            'descripcion': 'Contenido del estudio de seguridad municipal, su evidencia y reglas de correspondencia con Word.',
            'fuente': 'Capítulo SEGURIDAD de Machote general medicion version final.docx, conservado sin sobrescribir.',
            'alcance_activo': 'Un documento de medición de seguridad y dos documentos de entrada: paquete de seguridad y Anexo.',
            'cobertura_verificada': {'marcadores_de_variables_unicos': len(found),
                'apariciones_de_variables': sum(found.values()), 'indicadores': 18,
                'dimensiones': 3, 'periodos_de_evaluacion': 2, 'documentos_generados': 1},
            'verificacion_externa_de_fuentes_realizada': False,
        },
        'fuentes_autorizadas': {
            'paquete_seguridad': {'patron': '{municipio} PAQUETE SEGURIDAD.docx',
                'rol': 'Evidencia primaria para tablas y evaluación.'},
            'anexo': {'patron': '{municipio} Anexo.docx',
                'rol': 'Identidad territorial y contraste del capítulo de seguridad; no es un producto de salida.'},
            'regla': 'No consultar ni incorporar API, CSV, otros paquetes, investigaciones o documentos de ejemplo como evidencia.',
        },
        'convenciones': {
            'nombres_de_variables': {'formato': 'snake_case', 'mayusculas': False,
                'separador': '_', 'caracteres': 'ASCII', 'ejemplos': ['municipio', 'analisis_indicador_01']},
            'marcadores': {'formato_en_word': '{nombre_variable}', 'formato_de_clave_json': 'nombre_variable',
                'regla': 'Llaves simples; una variable por función e indicador, sin selección de variantes.'},
            'valores_pendientes': {'valor': None,
                'regla': 'No sustituir información desconocida por cero ni imputar puntajes sin una regla explícita.'},
            'redaccion_publicable': {'configuracion': 'config/redaccion_consultoria.json',
                'regla': 'Prosa diagnóstica consultiva; hallazgos y sus límites, sin archivos, rutas, códigos ni mensajes del sistema.'},
            'trazabilidad': 'Conservar localizadores, huellas y validaciones en metadatos; publicar títulos de fuentes y notas sustantivas.',
            'periodos': 'Periodo general con cobertura declarada e intervalo reciente común de dos años; no reemplazar años ausentes por observaciones antiguas.',
            'años': 'Las etiquetas de las tablas no se identifican automáticamente con el año de referencia del censo.',
            'porcentajes': 'Conservar unidades de la fuente; no convertir conteos a porcentajes sin denominador.',
        },
        'variables_documento': {key: definir_variable(key, count) for key, count in found.items()},
        'catalogos': {'periodos': ['general', 'ultimo_periodo'],
            'dimensiones': dimensions, 'calificaciones': deepcopy(rules['escala']),
            'estados_del_dato': ['reportado', 'pendiente', 'sin_respuesta_municipal',
                'variable_no_existente_en_edicion', 'dato_dudoso', 'no_aplicable']},
        'catalogo_indicadores': deepcopy(previous['catalogo_indicadores']),
        'campos_auxiliares': {
            'identidad_evidencia': 'Párrafo original que identifica municipio y estado.',
            'fuentes': 'Lista de exactamente dos documentos con nombre, rol y SHA-256; trazabilidad interna.',
            'evidencia_documental': 'Bloques originales de las dos entradas, conservados para auditoría.',
            'validaciones': 'Pendientes de revisión, inconsistencias y límites; los códigos no son texto del informe.',
            'contrato': 'Versiones y huellas de los componentes que produjeron el resultado.',
            'contenido_word': 'Contenido compuesto, variables activas y controles de publicación.',
        },
        'modelos_reutilizables': {
            'ficha_indicador': {
                'numero': 'integer 1..18', 'nombre': 'string', 'dimension': 'codigo de dimensión',
                'tablas': 'Tablas originales y localizadores de evidencia.',
                'evaluaciones': {'general': 'evaluacion_indicador', 'ultimo_periodo': 'evaluacion_indicador'},
                'control_cruzado_anexo': 'Correspondencia de tablas y calificación reportada entre los dos documentos.'},
            'evaluacion_indicador': {
                'puntaje': 'integer 1..5|null', 'criterio_aplicado': 'string cuando existe puntaje',
                'motivo': 'string que explica por qué no puede asignarse puntaje',
                'años_observados': 'array de integer', 'años_evaluados': 'array de integer',
                'regla': 'No confundir la calificación reportada en la entrada con una evaluación calculada; justificar toda asignación.'},
            'tabla_word_v2': {'titulo': 'string', 'ambito': 'municipal|estatal',
                'filas': 'array de arrays de strings', 'tabla_fuente': 'integer'},
            'grafica_word_v2': {'tipo': 'puntajes', 'titulo': 'string',
                'categorias': 'array de strings', 'valores': 'array de number|null', 'fuente': 'string',
                'regla': 'Representar únicamente puntajes calculados; null no es cero.'},
        },
        'calculos_derivados': {
            'metodologia': 'reglas_calificacion.json', 'periodos': ['general', 'ultimo_periodo'],
            'promedio_por_dimension': 'Media de todos los puntajes de la dimensión; null si alguno está pendiente.',
            'promedio_tres_dimensiones': 'Media de las tres dimensiones; no sustituir por la media simple de 18 indicadores.',
            'clasificacion': 'Aplicar escala, redondeo y candados de las reglas conservando sus motivos.',
            'regla_faltantes': 'Un pendiente metodológico impide cerrar el agregado; la falta de respuesta sólo se puntúa si la ficha y la evidencia lo justifican.',
        },
        'tratamiento_datos_faltantes': {
            'fuente_no_disponible': 'Explicar el dato ausente y mantener pendiente; este flujo no lo busca fuera de los dos documentos.',
            'denominador_no_disponible': 'No estimar tasas, razones o porcentajes sin su base de cálculo.',
            'serie_reciente_incompleta': 'Declarar los años faltantes y no sustituirlos por años anteriores.',
            'dato_dudoso': 'Conservar el valor original y registrar el motivo de revisión.',
        },
        'validaciones_finales': [
            {'id': 'fuentes_unicas', 'regla': 'Exactamente un paquete de seguridad y un Anexo del mismo municipio.'},
            {'id': 'contrato_editorial_v2', 'regla': f'{len(found)} variables snake_case del único perfil medicion; comprobar original, base y componentes del contrato.'},
            {'id': 'cobertura_indicadores', 'regla': '18 indicadores en el orden del machote y dos periodos declarados por indicador.'},
            {'id': 'puntajes_consistentes', 'regla': 'Los textos, gráficas y agregados reutilizan las mismas evaluaciones calculadas.'},
            {'id': 'trazabilidad', 'regla': 'Toda cifra y afirmación debe sustentarse en los dos documentos recibidos.'},
            {'id': 'comparaciones_validas', 'regla': 'No comparar conteos municipales con sumas estatales ni mezclar unidades o años.'},
            {'id': 'objetos_visuales', 'regla': 'Tablas y gráficas coincidentes con evidencia y puntajes; null no es cero.'},
            {'id': 'redaccion_consultiva', 'regla': 'Bloquear referencias técnicas internas y prosa no sustentada en el contenido publicable.'},
            {'id': 'cierre_editorial', 'regla': 'Resolver los bloqueos y completar la revisión humana antes de emitir una versión final.'},
        ],
    }


def main():
    dictionary_path = ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json'
    previous = json.loads(dictionary_path.read_text(encoding='utf-8'))
    rules_path = ROOT / 'reglas_calificacion.json'
    rules = json.loads(rules_path.read_text(encoding='utf-8'))
    if rules['version'] != '2.1':
        raise ValueError('Regenerar primero reglas_calificacion.json con estructurar_reglas.py para la versión 2.1.')
    if not REDACCION.is_file():
        raise ValueError('Falta la configuración del estilo de redacción consultiva.')
    source_digest = sha256(SOURCE)
    with zipfile.ZipFile(SOURCE) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(files['word/document.xml'])
    section = extraer_capitulo(root, previous['catalogo_indicadores'])
    operational = deepcopy(root)
    body = operational.find(W + 'body')
    final_section = deepcopy(body.find(W + 'sectPr'))
    for node in final_section.findall(W + 'type'):
        node.set(W + 'val', 'nextPage')
    for node in final_section.findall(W + 'cols'):
        node.set(W + 'num', '1')
    for node in list(body):
        body.remove(node)
    for node in portada(root, final_section):
        body.append(node)
    for index, node in enumerate(section):
        value = text(node).strip()
        role = ('capitulo' if value == 'SEGURIDAD' else 'subcapitulo' if value.startswith('Indicador ')
                else 'calificacion' if value.startswith('CALIFICACIÓN') else 'cuerpo')
        # Configurar sólo párrafos: las tablas u otros objetos del original no se reconstruyen.
        if node.tag == W + 'p':
            configurar(node, 'medicion', role)
        body.append(node)
        if index == 0:
            body.append(configurar(paragraph('{introduccion_seguridad}'), 'medicion', 'cuerpo'))
    body.append(configurar(paragraph('Conclusiones'), 'medicion', 'subcapitulo'))
    body.append(configurar(paragraph('{conclusiones_seguridad}'), 'medicion', 'cuerpo'))
    body.append(configurar(paragraph('Fuentes documentales'), 'medicion', 'subcapitulo'))
    body.append(configurar(paragraph('{bibliografia}'), 'medicion', 'bibliografia'))
    body.append(final_section)
    files['word/document.xml'] = ET.tostring(operational, encoding='UTF-8', xml_declaration=True, standalone=True)
    depurar_notas(files, operational)
    incrustar(files)
    save(BASE, files)
    found = Counter(MARKER.findall(text(operational)))
    dictionary = depurar_diccionario(previous, found, rules)
    dump(dictionary_path, dictionary)
    if sha256(SOURCE) != source_digest:
        raise ValueError('El machote original cambió durante la migración.')
    contract = {
        'version': '2.1', 'alcance': 'seguridad', 'marcador': '{snake_case}',
        'plantillas': {'medicion': {'archivo': str(BASE.relative_to(ROOT)), 'sha256': sha256(BASE),
            'origen': str(SOURCE.relative_to(ROOT)), 'origen_sha256': source_digest,
            'bloques_capitulo_origen': len(section),
            'derivacion': 'Copia del capítulo SEGURIDAD en su orden original; portada, introducción, conclusiones y fuentes.'}},
        'diccionario': {'archivo': str(dictionary_path.relative_to(ROOT)), 'sha256': sha256(dictionary_path)},
        'reglas': {'archivo': str(rules_path.relative_to(ROOT)), 'sha256': sha256(rules_path)},
        'metodologia': deepcopy(rules['fuente']),
        'formato': {'archivo': str(FORMATO.relative_to(ROOT)), 'sha256': sha256(FORMATO)},
        'redaccion': {'archivo': str(REDACCION.relative_to(ROOT)), 'sha256': sha256(REDACCION)},
        'tipografias': [{'archivo': f'assets/fonts/{filename}', 'sha256': sha256(ROOT / 'assets/fonts' / filename)}
                       for _, filename, _ in FONTS],
        'orden_indicadores': list(range(1, 19)),
        'fuentes_entrada': ['{municipio} PAQUETE SEGURIDAD.docx', '{municipio} Anexo.docx'],
        'documentos_salida': ['medicion'],
    }
    dump(ROOT / 'config/contrato_documental.json', contract)
    print(f'Migración: {len(found)} variables, {sum(found.values())} apariciones, una base de SEGURIDAD; original conservado.')


if __name__ == '__main__':
    main()
