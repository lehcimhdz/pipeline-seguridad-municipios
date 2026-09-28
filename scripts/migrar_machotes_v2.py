"""Deriva el estudio de SEGURIDAD sin alterar los tres documentos de referencia.

El formato de la consultora aporta el orden y la identidad gráfica; la guía
orienta la interpretación, y el benchmark sustenta las reglas de evaluación.
La base sólo recibe texto. Las ilustraciones originales se insertan por su
procedencia documental, sin crear tablas ni gráficas nuevas.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import unicodedata
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
BENCHMARK = ROOT / 'templates/Machote_seguridad_general_con_calificacion.docx'
NORMALIZACIONES = ROOT / 'config/normalizaciones.json'
GUIDE_NAME = 'Machote general medicion version final rzg investigación.docx'


def guia_path():
    matches = [path for path in (ROOT / 'templates').iterdir()
               if unicodedata.normalize('NFC', path.name) == GUIDE_NAME]
    if len(matches) != 1:
        raise ValueError('Se requiere una única guía de interpretación rzg investigación.')
    return matches[0]


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
    """Identifica el capítulo recibido y verifica sus 18 correspondencias."""
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


def parametrizar_capitulo(section, catalog):
    """Conserva el orden del formato y reduce cada indicador a su interpretación."""
    names = {f"Indicador {entry['id']:02d}: {entry['nombre']}": entry['nombre'] for entry in catalog}
    excluded = re.compile(r'^\{(?:graficas|tablas|cierre)_indicador_\d{2}\}$')
    result = []
    for source in section:
        value = text(source).strip()
        if excluded.fullmatch(value):
            continue
        node = paragraph(names[value], source) if value in names else deepcopy(source)
        role = ('capitulo' if value == 'SEGURIDAD' else 'subcapitulo' if value in names
                else 'calificacion' if value.startswith('CALIFICACIÓN') else 'cuerpo')
        if node.tag != W + 'p':
            raise ValueError('El capítulo de seguridad contiene un objeto no previsto por el formato de texto.')
        configurar(node, 'medicion', role)
        result.append(node)
    return result


def portada(root, section_properties):
    """Aplica el manual de medición y reutiliza el logo original."""
    title = configurar(paragraph('Estudio de Seguridad'), 'medicion', 'titulo')
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
        'municipio': 'Nombre del municipio del Paquete Seguridad y, cuando se proporciona, de su Anexo.',
        'estado': 'Entidad federativa confirmada en la evidencia documental.',
        'resumen_general': 'Balance del periodo completo, resultados por dimensión y límites sustantivos de la evidencia.',
        'resumen_ultimo_periodo': 'Balance de las observaciones recientes definidas por la metodología; explicar cambios y límites.',
        'calificacion_general': 'Categoría y justificación del periodo general con la metodología basada en el benchmark.',
        'calificacion_ultimo_periodo': 'Categoría y justificación del periodo reciente con la misma metodología.',
        'bibliografia': 'Referencias legibles de las fuentes efectivamente utilizadas, sin rutas, nombres técnicos ni huellas digitales.',
    }
    prefixes = {
        'analisis': 'Interpretación del indicador en uno o varios párrafos: datos concretos, comparación válida, implicación y acción sustentada; sin fórmulas repetidas.',
    }
    prefix = key.split('_', 1)[0]
    return {
        'marcador': '{' + key + '}', 'apariciones': count,
        'apariciones_por_documento': {'medicion': count}, 'tipo_dato': 'string',
        'tipo_contenido': 'texto',
        'debe_contener': descriptions.get(key, prefixes.get(prefix, 'Texto sustentado en las fuentes autorizadas.')),
        'obligatorio': True,
    }


def depurar_diccionario(previous, found, rules):
    """Describe la única salida activa; descarta productos y modelos históricos."""
    dimensions = deepcopy(previous['catalogos']['dimensiones'])
    for dimension in dimensions:
        dimension['indicadores'] = rules['dimensiones'][dimension['codigo']]
        dimension['peso'] = rules['ponderacion_config']['ponderacion']['esquemas']['dimensiones_ponderadas']['peso_dimension'][dimension['codigo']]
    catalogue = deepcopy(previous['catalogo_indicadores'])
    for item, ficha in zip(catalogue, rules['fichas']):
        item.update(peso=ficha['peso'], prioritario=ficha['prioritario'], datos_especificos=deepcopy(ficha['datos_requeridos']))
        if ficha.get('revision_definiciones'):
            item['revision_definiciones'] = ficha['revision_definiciones']
        if ficha.get('escala_vigente'):
            item['escala_vigente'] = deepcopy(ficha['escala_vigente'])
    return {
        'metadatos': {
            'version': '2.3', 'nombre': 'diccionario_variables_diagnostico_seguridad_municipal',
            'idioma': 'es-MX', 'tipo_documento': 'diccionario_de_datos_y_especificacion_de_contenido',
            'es_json_schema_formal': False,
            'descripcion': 'Contenido del estudio de seguridad municipal, su evidencia y reglas de correspondencia con Word.',
            'fuente': 'Capítulo SEGURIDAD de Machote general medicion version final.docx, conservado sin sobrescribir.',
            'alcance_activo': 'Un Estudio Seguridad: interpretación narrativa y reproducciones pertinentes de gráficas ya existentes.',
            'producto': 'estudio_seguridad',
            'nombre_salida': '{municipio} Estudio Seguridad.docx',
            'cobertura_verificada': {'marcadores_de_variables_unicos': len(found),
                'apariciones_de_variables': sum(found.values()), 'indicadores': 18,
                'dimensiones': 3, 'periodos_de_evaluacion': 2, 'documentos_generados': 1},
            'verificacion_externa_de_fuentes_realizada': False,
        },
        'fuentes_autorizadas': {
            'paquete_seguridad': {'patron': '{municipio} PAQUETE SEGURIDAD.docx', 'obligatorio': True,
                'rol': 'Datos estadísticos e imágenes originales que sustentan la interpretación.'},
            'anexo': {'patron': '{municipio} Anexo.docx',
                'obligatorio': False, 'rol': 'Contraste de seguridad y gráficas originales cuando está disponible.'},
            'complementos': {'patron': 'input/complementos/{slug}.json', 'obligatorio': False,
                'rol': 'Definiciones y denominadores documentados; fuente, año, localizador, SHA-256 y revisión por observación.'},
            'regla': 'No incorporar otros municipios ni búsquedas automáticas. Complementos explícitos y revisados mediante --complemento. La muestra sólo orienta el estilo.',
        },
        'documentos_de_referencia': {
            'formato_consultora': {'archivo': str(SOURCE.relative_to(ROOT)),
                'rol': 'Orden y presentación de la salida; sólo su capítulo SEGURIDAD.'},
            'guia_interpretacion': {'archivo': str(guia_path().relative_to(ROOT)),
                'rol': 'Preguntas de interpretación, relación entre hallazgos y propuestas; no aporta estadísticas municipales.',
                'correspondencia': 'El duplicado de Personal en la guía no crea otro indicador; se conserva el catálogo de 18 indicadores, incluido Certificado Único Policial.'},
            'benchmark': {'archivo': str(BENCHMARK.relative_to(ROOT)),
                'rol': 'Criterios de evaluación e interpretación; su contenido técnico no se inserta en la salida.'},
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
            'periodos': 'Aplicar la definición de reglas_calificacion.json y declarar años observados/evaluados; no inventar observaciones anuales.',
            'años': 'Las etiquetas de las tablas no se identifican automáticamente con el año de referencia del censo.',
            'porcentajes': 'Conservar unidades de la fuente; no convertir conteos a porcentajes sin denominador.',
        },
        'variables_documento': {key: definir_variable(key, count) for key, count in found.items()},
        'catalogos': {'periodos': ['general', 'ultimo_periodo'],
            'dimensiones': dimensions, 'calificaciones': deepcopy(rules['escala']),
            'estados_del_dato': ['reportado', 'pendiente', 'sin_respuesta_municipal',
                'variable_no_existente_en_edicion', 'dato_dudoso', 'no_aplicable', 'en_conflicto']},
        'catalogo_indicadores': catalogue,
        'campos_auxiliares': {
            'identidad_evidencia': 'Párrafo original que identifica municipio y estado.',
            'fuentes': 'Paquete y Anexo si está disponible, con nombre, rol y SHA-256; trazabilidad interna.',
            'evidencia_complementaria': 'Versión 1.0, identidad, fuentes conservadas, poblacion por ámbito/año y observaciones por indicador/año; RECOLECCION_DATOS.md.',
            'evidencia_complementaria_sha256': 'Huella del objeto canónico completo; invalida redacción si cambia.',
            'evaluacion_sha256': 'Huella de puntajes, cálculos y periodos; cambiar modo o esquema exige revisar la redacción.',
            'evidencia_documental': 'Bloques originales de las entradas recibidas, conservados para auditoría.',
            'lecturas_graficas': 'OCR local por imagen: estado, texto, título, idioma y motor, con fuente, indicador, ámbito y huellas. Las cifras se toman de las tablas. Se verifica la lectura antes de publicar.',
            'validaciones': 'Pendientes de revisión, inconsistencias y límites; los códigos no son texto del informe.',
            'contrato': 'Versiones y huellas de los componentes que produjeron el resultado.',
            'contenido_word': 'Perfil estudio_seguridad, 25 variables de texto, ilustraciones originales y controles de publicación.',
            'contenido_word.ilustraciones': 'Referencias a imágenes existentes: fuente, parte del DOCX, huella, indicador y ubicación; nunca datos para generar una gráfica nueva.',
        },
        'modelos_reutilizables': {
            'ficha_indicador': {
                'numero': 'integer 1..18', 'nombre': 'string', 'dimension': 'codigo de dimensión',
                'tablas': 'Tablas originales y localizadores de evidencia.',
                'lecturas_graficas': 'Subconjunto del registro de OCR correspondiente a este indicador; no inferir conceptos de otro ámbito o fuera del periodo explícito del título.',
                'evaluaciones': {'general': 'evaluacion_indicador', 'ultimo_periodo': 'evaluacion_indicador'},
                'control_cruzado_anexo': 'Correspondencia de tablas y calificación reportada entre los dos documentos.'},
            'evaluacion_indicador': {
                'puntaje': 'integer 1..5|null', 'criterio_aplicado': 'string cuando existe puntaje',
                'motivo': 'string que explica por qué no puede asignarse puntaje',
                'años_observados': 'array de integer', 'años_evaluados': 'array de integer',
                'estado_dato': 'reportado|pendiente|no_aplicable|en_conflicto',
                'correspondencias': 'Por año: campos resueltos con valor, tipo (lectura_directa, lectura_grafica, homologacion, complemento_verificado), regla y evidencias; conflictos impiden puntuar. Coordenadas: tabla y fila desde 1, incluido encabezado; fuentes y huellas en el resultado.',
                'requisitos_pendientes': 'Campos o comprobaciones aún necesarios por año; no equivale a inexistencia de la variable en el cuestionario general.',
                'valoracion_provisional': 'Nivel indicativo o null, base, confianza, falta, evidencias y condiciones; indicar años usados. Nunca computa en la agregación.',
                'regla': 'No confundir la calificación reportada en la entrada con una evaluación calculada; justificar toda asignación.'},
            'ilustracion_original': {'indicador': 'integer 1..18', 'archivo_fuente': 'string',
                'parte': 'Ruta de la imagen dentro del DOCX de entrada', 'sha256': 'string',
                'regla': 'Copiar bytes originales y conservar proporción; omitir imágenes inconsistentes o irrelevantes. No reconstruir tablas ni gráficas.'},
        },
        'calculos_derivados': {
            'metodologia': 'reglas_calificacion.json', 'periodos': ['general', 'ultimo_periodo'],
            'promedio_por_dimension': 'Aplicar las reglas de agregación, cobertura y límites documentadas en la metodología vigente.',
            'promedio_tres_dimensiones': 'Media ponderada 25/35/40 por defecto; registrar esquema y coeficientes efectivos. Esquemas alternativos explícitos para comparación.',
            'clasificacion': 'Aplicar escala, redondeo y candados de las reglas conservando sus motivos.',
            'regla_faltantes': 'Distinguir desempeño y suficiencia documental; toda calificación requiere criterio y límites explícitos según la metodología.',
        },
        'tratamiento_datos_faltantes': {
            'fuente_no_disponible': 'Conservar null y explicar el faltante. Admitir complementos revisados, sin búsqueda ni imputación automática.',
            'denominador_no_disponible': 'No estimar tasas, razones o porcentajes sin su base de cálculo.',
            'serie_reciente_incompleta': 'Declarar cobertura y años evaluados según la periodicidad observada; no interpolar años.',
            'dato_dudoso': 'Conservar el valor original y registrar el motivo de revisión.',
        },
        'validaciones_finales': [
            {'id': 'fuentes_unicas', 'regla': 'Un Paquete Seguridad y, opcionalmente, un Anexo del mismo municipio.'},
            {'id': 'contrato_editorial_v2', 'regla': f'{len(found)} variables snake_case del único perfil medicion; comprobar original, base y componentes del contrato.'},
            {'id': 'cobertura_indicadores', 'regla': '18 indicadores en el orden del machote y dos periodos declarados por indicador.'},
            {'id': 'puntajes_consistentes', 'regla': 'Las calificaciones y su explicación utilizan las mismas evaluaciones calculadas.'},
            {'id': 'trazabilidad', 'regla': 'Toda cifra municipal debe sustentarse en las entradas; toda calificación debe identificarse con la metodología.'},
            {'id': 'comparaciones_validas', 'regla': 'No comparar conteos municipales con sumas estatales ni mezclar unidades o años.'},
            {'id': 'objetos_visuales', 'regla': 'Sólo imágenes originales seleccionadas por su pertinencia; verificar procedencia y huella. No generar tablas ni gráficas nuevas.'},
            {'id': 'redaccion_consultiva', 'regla': 'Bloquear referencias técnicas internas y prosa no sustentada en el contenido publicable.'},
            {'id': 'cierre_editorial', 'regla': 'Documento de consultoría sin instrucciones, nombres de archivos internos, variables pendientes ni rótulos de borrador o machote.'},
        ],
    }


def main():
    dictionary_path = ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json'
    previous = json.loads(dictionary_path.read_text(encoding='utf-8'))
    rules_path = ROOT / 'reglas_calificacion.json'
    rules = json.loads(rules_path.read_text(encoding='utf-8'))
    if rules['version'] != '2.3':
        raise ValueError('Regenerar primero reglas_calificacion.json con estructurar_reglas.py para la versión 2.3.')
    if not REDACCION.is_file():
        raise ValueError('Falta la configuración del estilo de redacción consultiva.')
    guide = guia_path()
    source_digests = {path: sha256(path) for path in (SOURCE, guide, BENCHMARK)}
    with zipfile.ZipFile(SOURCE) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(files['word/document.xml'])
    original_section = extraer_capitulo(root, previous['catalogo_indicadores'])
    section = parametrizar_capitulo(original_section, previous['catalogo_indicadores'])
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
    for node in section:
        body.append(node)
    body.append(configurar(paragraph('Fuentes documentales'), 'medicion', 'subcapitulo'))
    body.append(configurar(paragraph('{bibliografia}'), 'medicion', 'bibliografia'))
    body.append(final_section)
    files['word/document.xml'] = ET.tostring(operational, encoding='UTF-8', xml_declaration=True, standalone=True)
    depurar_notas(files, operational)
    incrustar(files)
    found = Counter(MARKER.findall(text(operational)))
    expected = Counter(['municipio', 'estado', 'calificacion_general', 'calificacion_ultimo_periodo',
                        'resumen_general', 'resumen_ultimo_periodo', 'bibliografia'])
    expected.update(f'analisis_indicador_{number:02d}' for number in range(1, 19))
    if found != expected:
        raise ValueError('La base debe contener exactamente las 25 variables de texto del estudio.')
    save(BASE, files)
    dictionary = depurar_diccionario(previous, found, rules)
    dictionary['metodologia_v23'] = {
        'ponderacion': 'config/ponderacion.json', 'definiciones': 'config/definiciones_cngmd.json',
        'referencia_editorial': 'config/textos_narrativos.json',
        'complemento': 'Objeto evidencia_complementaria, versión 1.0: fuentes, poblacion y observaciones por indicador/año; véase RECOLECCION_DATOS.md.',
        'estados': ['reportado', 'pendiente', 'no_aplicable', 'en_conflicto'],
        'correspondencias': 'Resolución automática desde input con reglas generales y trazabilidad por año; sin convertir inferencias en revisiones humanas. El complemento sólo aporta requisitos no resueltos.',
        'puntaje': 'Entero 1–5 o null; la valoración provisional nunca se incorpora al puntaje.',
        'prioritarios': rules['ponderacion_config']['ponderacion']['prioritarios'],
        'pesos_dimension': rules['ponderacion_config']['ponderacion']['esquemas']['dimensiones_ponderadas']['peso_dimension'],
        'publicacion': 'Exige cobertura por dimensión y al menos seis prioritarios; no sustituir evidencia faltante por prosa.'}
    dump(dictionary_path, dictionary)
    if any(sha256(path) != digest for path, digest in source_digests.items()):
        raise ValueError('Un documento de referencia original cambió durante la migración.')
    contract = {
        'version': '2.3', 'alcance': 'seguridad', 'producto': 'estudio_seguridad', 'marcador': '{snake_case}',
        'plantillas': {'medicion': {'archivo': str(BASE.relative_to(ROOT)), 'sha256': sha256(BASE),
            'origen': str(SOURCE.relative_to(ROOT)), 'origen_sha256': source_digests[SOURCE],
            'bloques_capitulo_origen': len(original_section), 'bloques_capitulo_derivado': len(section),
            'derivacion': 'Capítulo SEGURIDAD en el orden del formato de la consultora, encabezados humanos y 25 variables de texto. Portada y fuentes; sin nuevos cuadros o gráficas.'}},
        'fuente_formato': {'archivo': str(SOURCE.relative_to(ROOT)), 'sha256': source_digests[SOURCE],
            'rol': 'Formato de entrega de la consultora; sólo capítulo SEGURIDAD.'},
        'guia': {'archivo': str(guide.relative_to(ROOT)), 'sha256': source_digests[guide],
            'rol': 'Guía de lectura e interpretación; no es el documento de entrega ni aporta estadísticas.'},
        'benchmark': {'archivo': str(BENCHMARK.relative_to(ROOT)), 'sha256': source_digests[BENCHMARK],
            'rol': 'Criterios para construir la metodología de calificación e interpretación.'},
        'diccionario': {'archivo': str(dictionary_path.relative_to(ROOT)), 'sha256': sha256(dictionary_path)},
        'reglas': {'archivo': str(rules_path.relative_to(ROOT)), 'sha256': sha256(rules_path)},
        'metodologia': deepcopy(rules['fuente']),
        'formato': {'archivo': str(FORMATO.relative_to(ROOT)), 'sha256': sha256(FORMATO)},
        'redaccion': {'archivo': str(REDACCION.relative_to(ROOT)), 'sha256': sha256(REDACCION)},
        'normalizaciones': {'archivo': str(NORMALIZACIONES.relative_to(ROOT)), 'sha256': sha256(NORMALIZACIONES)},
        **{key: {'archivo': 'config/' + filename, 'sha256': sha256(ROOT / 'config' / filename)}
           for key, filename in (('ponderacion', 'ponderacion.json'), ('definiciones', 'definiciones_cngmd.json'),
                                 ('textos_narrativos', 'textos_narrativos.json'))},
        'tipografias': [{'archivo': f'assets/fonts/{filename}', 'sha256': sha256(ROOT / 'assets/fonts' / filename)}
                       for _, filename, _ in FONTS],
        'orden_indicadores': list(range(1, 19)),
        'titulos_indicadores': [entry['nombre'] for entry in previous['catalogo_indicadores']],
        'correspondencia_guia': 'La guía repite Personal y no identifica el Certificado Único Policial; se mantienen los 18 indicadores del formato y del Paquete Seguridad.',
        'fuentes_entrada': ['{municipio} PAQUETE SEGURIDAD.docx'],
        'fuentes_opcionales': ['{municipio} Anexo.docx'],
        'fuentes_complementarias': {'opcion': '--complemento', 'version': '1.0',
            'contrato': 'RECOLECCION_DATOS.md', 'validacion': 'Fuentes con huella y observaciones verificadas; no se autocompletan. Se mantienen separadas de las correspondencias automáticas extraídas del paquete.'},
        'documentos_salida': ['medicion'],
        'nombre_salida': '{municipio} Estudio Seguridad.docx',
        'ilustraciones': 'Reproducción de imágenes originales verificadas; sin generar tablas o gráficas nuevas.',
    }
    dump(ROOT / 'config/contrato_documental.json', contract)
    print(f'Migración: {len(found)} variables de texto, {sum(found.values())} apariciones; tres documentos de referencia conservados.')


if __name__ == '__main__':
    main()
