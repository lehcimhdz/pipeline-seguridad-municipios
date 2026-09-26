"""Parametriza el machote de investigación conservando sus bloques y formato."""
from collections import Counter
from copy import deepcopy
import argparse
import json
from pathlib import Path
import re
import tempfile
import unicodedata
import zipfile
from lxml import etree as ET
from calificar import normalizar
from documentos import sha256
from editorial import FORMATO
from fuentes_word import incrustar, FONTS
from fidelidad_machote import envolver, validar as validar_fidelidad
from estructurar_reglas import construir

ROOT = Path(__file__).resolve().parents[1]
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MARKER = re.compile(r'(?<!\{)\{([a-z][a-z0-9_]*)\}(?!\})')
GROUPS = [
    (27, 'proteccion_civil', [1, 2, 3], [(28, 'tratados_leyes'), (29, 'recomendaciones_onu')]),
    (43, 'condiciones_personal', list(range(4, 11)), [(44, 'leyes_nacionales'), (45, 'reportes_unodc'), (46, 'revisiones_laborales')]),
    (64, 'inteligencia_policial', list(range(11, 17)), [(65, 'patrullaje'), (66, 'hotspots'), (67, 'policia_comunitaria'),
        (68, 'evaluacion_policial'), (69, 'derechos_humanos'), (70, 'cctv'), (71, 'mediacion')]),
    (89, 'eficiencia_policial', [17, 18], [(90, 'derechos_humanos'), (91, 'letalidad'), (92, 'detenciones_seguridad')]),
]
TEXT_FIELDS = {
    5: ('Resumir de forma general', 'introduccion_periodo_general'),
    6: ('Un párrafo de los bienes', 'bienes_a_proteger'),
    7: ('Un párrafo sobre la condición', 'comparacion_estatal_municipal'),
    8: ('Un párrafo sobre los avances', 'avances_municipales'),
    9: ('[INSERTAR DE DOS A TRES PÁRRAFOS]', 'resumen_general'),
    10: ('Resumir de forma general', 'introduccion_ultimo_periodo'),
    11: ('[INSERTAR DE DOS A TRES PÁRRAFOS]', 'resumen_ultimo_periodo'),
    12: ('Un párrafo de protección civil', 'resumen_proteccion_civil'),
    13: ('Uno de condiciones laborales', 'resumen_condiciones_personal'),
    14: ('Uno de inteligencia policial', 'resumen_inteligencia_eficiencia'),
    16: ('Cuando se trata del producto de gobierno', 'enfoque_gobierno'),
    17: ('Tendencia general', 'tendencia_general'),
    18: ('Qué hacer:', 'recomendaciones_gobierno'),
    21: ('Cuando se trata del producto electoral', 'justificacion_prioridades'),
    22: ('Qué está bien.', 'fortalezas_seguridad'),
    23: ('Qué está mal.', 'areas_mejora_seguridad'),
    25: ('Las gráficas y las tablas', 'criterio_lectura_graficas'),
    34: ('Ver en leyes y tratados', 'minimos_indicador_01'),
    37: ('Ver en leyes y tratados', 'minimos_indicador_02'),
    41: ('Ver en leyes y tratados', 'minimos_indicador_03'),
}
SLOTS = {33: 1, 36: 2, 40: 3, 49: 4, 51: 7, 53: 5, 55: 6, 57: 8, 60: 9,
         62: 10, 75: 11, 78: 12, 81: 13, 83: 14, 86: 15, 88: 16, 95: 17, 98: 18}
METHOD_FIELDS = ['metodologia_calificacion', 'cobertura_general', 'cobertura_ultimo_periodo',
                 'sensibilidad_general', 'sensibilidad_ultimo_periodo']
ALIASES_ENCABEZADOS = {
    3: ('Temas de la capacitación (Protección Civil)',),
    5: ('Evaluaciones de control de confianza (policía)',),
    6: ('Instituto de formación, capacitación y/o profesionalización policial municipal',),
    10: ('Temas de capacitación',),
    17: ('Cambio en el estado de fuerza, egresos y fallecimientos',),
}


def texto(node):
    return ''.join(t.text or '' for t in node.iter(W + 't'))


def validar_encabezados(blocks, catalog):
    """Evita asociar datos a otro indicador si cambian títulos sin mover slots."""
    names = {item['id']: item['nombre'] for item in catalog}
    canonical = lambda value: normalizar(re.sub(r'\s+', ' ', value).strip())
    for slot, number in SLOTS.items():
        # La copia de personal en 50/51 es la única excepción documentada:
        # debe seguir siendo personal antes de transformarse en CUP.
        source_number = 4 if slot == 51 else number
        expected = {canonical(names[source_number]),
                    *(canonical(name) for name in ALIASES_ENCABEZADOS.get(source_number, ()))}
        if canonical(texto(blocks[slot - 1])) not in expected:
            raise ValueError(f'Encabezado de indicador inesperado en bloque {slot - 1}; revisar asignación del indicador {number}.')


def copiar_texto(model, value):
    """Conserva pPr, listas y estilo del primer run; cambia sólo el contenido."""
    p = deepcopy(model)
    first_run = model.find('.//' + W + 'r')
    props = first_run.find(W + 'rPr') if first_run is not None else None
    for node in list(p):
        if node.tag != W + 'pPr':
            p.remove(node)
    r = ET.SubElement(p, W + 'r')
    if props is not None:
        r.append(deepcopy(props))
    ET.SubElement(r, W + 't').text = value
    return p


def guardar_docx(path, files):
    with tempfile.NamedTemporaryFile(suffix='.docx', dir=path.parent, delete=False) as f:
        temp = Path(f.name)
    try:
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def dump(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if not path.exists() or path.read_text(encoding='utf-8') != data:
        path.write_text(data, encoding='utf-8')


def origen_default():
    expected = unicodedata.normalize('NFC', 'Machote general medicion version final rzg investigación.docx')
    matches = [p for p in (ROOT / 'templates').glob('*.docx') if unicodedata.normalize('NFC', p.name) == expected]
    if len(matches) != 1:
        raise ValueError('Se requiere un único machote rzg investigación; usa --template para indicar otro.')
    return matches[0]


def migrar(source):
    source = source.resolve()
    source.relative_to(ROOT)
    with zipfile.ZipFile(source) as z:
        original_files = {n: z.read(n) for n in z.namelist()}
    files = dict(original_files)
    root = ET.fromstring(files['word/document.xml'])
    body = root.find(W + 'body')
    blocks = list(body)
    if len(blocks) != 102 or texto(blocks[0]).strip() != 'SEGURIDAD' or blocks[-1].tag != W + 'sectPr':
        raise ValueError('Cambió la estructura del machote; revisar el mapa de bloques antes de parametrizar.')
    for index, (prefix, key) in TEXT_FIELDS.items():
        if not texto(blocks[index]).strip().startswith(prefix):
            raise ValueError(f'Instrucción inesperada en el bloque {index}: revisar su variable.')
    for index in SLOTS:
        if texto(blocks[index]).strip() != '[INSERTAR ANÁLISIS E INTERCALAR GRÁFICAS Y/O TABLAS]':
            raise ValueError(f'Cambió la posición del indicador en el bloque {index}.')
    if texto(blocks[48]).strip() != texto(blocks[50]).strip():
        raise ValueError('Revisar corrección documentada del personal duplicado/CUP.')
    notes = [{'bloque': i, 'texto': texto(b).strip()} for i, b in enumerate(blocks) if texto(b).strip()]
    dictionary_path = ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json'
    dictionary = json.loads(dictionary_path.read_text(encoding='utf-8'))
    rules_path = ROOT / 'reglas_calificacion.json'
    methodology = ROOT / 'config/metodologia_seguridad.json'
    rules = construir()
    catalog = dictionary['catalogo_indicadores']
    if [item['id'] for item in catalog] != list(range(1, 19)):
        raise ValueError('Se requieren los 18 indicadores del catálogo.')
    validar_encabezados(blocks, catalog)
    research = {'version': '1.1', 'origen': str(source.relative_to(ROOT)), 'origen_sha256': sha256(source),
                'instrucciones_originales': notes, 'lineas': [],
                'regla': 'Cada tema conserva su posición y requiere evidencia citada. Los benchmarks no modifican puntajes.'}
    append_fields = {0: ['municipio', 'estado'], 3: METHOD_FIELDS}
    for index, code, ids, topics in GROUPS:
        append_fields[index] = ['benchmark_' + code]
        parts = []
        for topic_index, key in topics:
            variable = f'investigacion_{code}_{key}'
            append_fields[topic_index] = [variable]
            parts.append({'id': key, 'variable': variable, 'bloque_origen': topic_index,
                          'instruccion': texto(blocks[topic_index]).strip()})
        research['lineas'].append({'id': code, 'variable': 'benchmark_' + code, 'indicadores': ids,
            'temas_requeridos': [p['instruccion'] for p in parts], 'apartados': parts,
            'estado_inicial': 'pendiente', 'fuentes_iniciales': []})
    # Mantener todos los bloques, salvo el traslado explícito de la copia de
    # personal después del instituto para restaurar CUP en su posición canónica.
    order = [i for i in range(len(blocks) - 1) if i not in (50, 51)]
    insertion = order.index(55) + 1
    order[insertion:insertion] = [50, 51]
    manifest = {'version': '1.0', 'orden_bloques': order, 'bloques': [],
        'adaptaciones_explicitas': [
            'Trasladar bloques 50/51 (personal duplicado) después de 55; título cambia a CUP.',
            'Identidad municipal bajo SEGURIDAD y bibliografía al final; sin portada añadida.',
            'Instrucciones de redacción sustituidas por variables en la misma posición.',
            'Metodología, cobertura y sensibilidad en el bloque inicial; dos calificaciones documentales explícitas por indicador.',
            'Temas de investigación y encabezados conservados con su desarrollo inmediatamente después.']}
    controls = {}
    for i in order:
        source_block = blocks[i]
        control = envolver(source_block, i)
        content = control.find(W + 'sdtContent')
        action = 'conservar'
        keys = []
        if i in TEXT_FIELDS:
            keys = [TEXT_FIELDS[i][1]]
            content[0] = copiar_texto(source_block, '{' + keys[0] + '}')
            action = 'parametrizar'
        elif i in (1, 2):
            key = 'calificacion_general' if i == 1 else 'calificacion_ultimo_periodo'
            prefix = texto(source_block).split(':', 1)[0] + ': '
            keys = [key]
            content[0] = copiar_texto(source_block, prefix + '{' + key + '}')
            action = 'parametrizar'
        elif i in SLOTS:
            number = SLOTS[i]
            keys = [f'calificacion_indicador_{number:02d}_{period}' for period in ('general', 'ultimo_periodo')]
            keys += [f'{kind}_indicador_{number:02d}' for kind in ('analisis', 'graficas', 'tablas', 'cierre')]
            content.remove(content[0])
            for key in keys:
                content.append(copiar_texto(source_block, '{' + key + '}'))
            action = 'parametrizar'
        elif i == 50:
            content[0] = copiar_texto(source_block, catalog[6]['nombre'])
            action = 'corregir_catalogo'
        if i in append_fields:
            keys = append_fields[i]
            if i == 0:
                identity = copiar_texto(blocks[3], '{municipio}, {estado}')
                content.append(identity)
            else:
                for key in keys:
                    content.append(copiar_texto(blocks[33], '{' + key + '}'))
            action = 'ampliar'
        controls[i] = control
        manifest['bloques'].append({'indice': i, 'accion': action, 'variables': keys})
    # Reemplazar cada nodo por su control de procedencia: no reconstruir títulos,
    # listas, márgenes ni secciones. La excepción CUP queda descrita arriba.
    for i in range(len(blocks) - 1):
        body.replace(blocks[i], controls[i])
    for i in (50, 51):
        body.remove(controls[i])
    anchor = body.index(controls[55]) + 1
    body.insert(anchor, controls[50])
    body.insert(anchor + 1, controls[51])
    sources = envolver(blocks[100], 100)
    sources.find(W + 'sdtPr/' + W + 'tag').set(W + 'val', 'adicional_fuentes')
    source_content = sources.find(W + 'sdtContent')
    source_content[0] = copiar_texto(blocks[33], 'Fuentes documentales y referencias')
    source_content.append(copiar_texto(blocks[33], '{bibliografia}'))
    body.insert(body.index(body.find(W + 'sectPr')), sources)
    files['word/document.xml'] = ET.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
    incrustar(files)
    validar_fidelidad(original_files, files, manifest)
    target = ROOT / 'templates/seguridad_medicion_v3.docx'
    guardar_docx(target, files)
    counts = Counter(MARKER.findall(texto(root)))
    research_keys = {line['variable'] for line in research['lineas']}
    research_keys.update(p['variable'] for line in research['lineas'] for p in line['apartados'])
    research_keys.update(f'minimos_indicador_{i:02d}' for i in range(1, 4))
    variables = {}
    for key, count in counts.items():
        tipo = 'array' if key.startswith(('graficas_', 'tablas_')) else 'string'
        variables[key] = {'marcador': '{' + key + '}', 'apariciones': count, 'tipo_dato': tipo,
            'apariciones_por_documento': {'medicion': count},
            'tipo_contenido': 'graficas' if key.startswith('graficas_') else 'tablas' if tipo == 'array' else 'texto',
            'origen_contenido': 'investigacion_verificada' if key in research_keys else 'evidencia_documental',
            'bloques_origen': [b['indice'] for b in manifest['bloques'] if key in b['variables']],
            'obligatorio': not key.startswith('graficas_')}
        if key in METHOD_FIELDS or key.startswith('calificacion_'):
            variables[key]['origen_contenido'] = 'metodologia_documental_calculada'
            variables[key]['reglas'] = 'reglas_calificacion.json#/calificacion_documental'
            variables[key]['descripcion'] = (
                'Nota documental, fundamento y/o cobertura; no sustituye el puntaje observado ni implica desempeño comprobado.')
    dictionary['variables_documento'] = variables
    dictionary['metadatos'].update(version='3.2', fuente=str(source.relative_to(ROOT)), documento_modificado=False,
        alcance_activo='SEGURIDAD parametrizada sobre el original: estructura conservada y cada instrucción trazable.')
    dictionary['metadatos']['cobertura_verificada'] = {'marcadores_de_variables_unicos': len(variables),
        'apariciones_de_variables': sum(counts.values()), 'indicadores': 18, 'dimensiones': 3,
        'lineas_de_investigacion': 4, 'apartados_de_investigacion': 15, 'periodos_de_evaluacion': 2}
    dictionary['convenciones']['marcadores'] = {'formato_en_word': '{nombre_variable}',
        'formato_de_clave_json': 'nombre_variable', 'regla': 'Llaves simples, snake_case ASCII y posición del original.'}
    dictionary['marcadores_no_tratados_como_variables'] = {}
    dictionary['modelos_reutilizables']['investigacion_v3']['apartados'] = 'object por línea, claves del contrato y textos con URL citada'
    dictionary['modelos_reutilizables']['calificacion_documental'] = {
        'puntaje': 'integer 1–5 o null; sólo evidencia observable y criterio inequívoco',
        'puntaje_asignado': 'integer 1–5 siempre; puntaje observado o base documental no acreditada',
        'base_calificacion': 'observado | no_acreditado',
        'motivo_asignacion': 'string; criterio o faltante que justifica la nota',
        'cobertura': 'Indicadores observados y porcentaje simple/ponderado; no probabilidad de certeza',
        'sensibilidad': 'Rango de promedios con pendientes en 1/5; no intervalo de confianza',
    }
    dictionary['convenciones']['valores_pendientes']['regla'] = (
        'No sustituir el dato ni el puntaje observado null. La política documental asigna por separado '
        'puntaje_asignado=1 con base_calificacion=no_acreditado y motivo; no implica desempeño deficiente.')
    dictionary['catalogos']['calificaciones_documentales'] = deepcopy(rules['calificacion_documental']['escala_documental'])
    dictionary['modelos_reutilizables']['grafica_word_v3']['valores'] = 'array de integer 1–5: puntaje_asignado de cada periodo'
    dictionary['modelos_reutilizables']['grafica_word_v3']['fuente'] = (
        'string; identifica la metodología documental y los periodos con asignación por no acreditación')
    dictionary['modelos_reutilizables']['evaluacion_indicador']['alcance'] = (
        'Esquema histórico de referencia; la ejecución v3.2 utiliza calificacion_documental con puntaje y puntaje_asignado separados. '
        'No se aplican ajustes discrecionales ni se infiere falta de respuesta de un vacío.')
    dictionary['calculos_derivados']['estructura'].update(
        modelo_comun='resultado_documental',
        regla='Ambos periodos tienen nota documental, cobertura y sensibilidad; la evidencia faltante permanece null.')
    dictionary['calculos_derivados']['resultado_evaluacion']['alcance'] = (
        'Referencia histórica no operativa de la agregación anterior; ver resultado_documental y reglas activas.')
    dictionary['calculos_derivados']['resultado_documental'] = {
        'promedios_dimension': 'Promedio de puntaje_asignado de todos los indicadores de cada dimensión',
        'promedio_tres_dimensiones': 'sum(promedio_dimension * peso_dimension) / sum(pesos_dimension)',
        'calificacion_final': 'Categoría de escala_documental después de candados; siempre emitida',
        'categoria_desempeno': 'Categoría histórica sólo con 18 puntajes observados; null si existe algún faltante',
        'cobertura': 'observados, asignados, total, no_acreditados, porcentaje y ponderada_porcentaje',
        'sensibilidad': 'minimo y maximo del promedio antes de candados con no acreditados en 1 y 5',
        'indicadores_pendientes': 'IDs sin puntaje observado; cada uno sí tiene puntaje_asignado',
        'referencia_parametros': 'reglas_calificacion.json#/calificacion_documental',
    }
    dictionary['tratamiento_datos_faltantes']['pendiente_de_captura']['accion'] = (
        'Conservar dato y puntaje observado null; asignar la base documental con motivo explícito.')
    dictionary['tratamiento_datos_faltantes']['sin_respuesta_municipal']['accion_documental'] = (
        'No inferir esta condición de vacíos. El candado requiere clasificación explícita; no se activa automáticamente.')
    dictionary['tratamiento_datos_faltantes']['variable_no_existente_en_edicion']['accion_documental'] = (
        'Conservar null y documentar la ausencia. No sustituir ni excluir años del intervalo reciente común; '
        'asignar la base documental si impide comprobar el criterio.')
    dictionary['tratamiento_datos_faltantes']['no_aplicable']['accion'] = (
        'Conservar explicación y puntaje observado null, con nota documental de no acreditación hasta resolver la aplicabilidad; '
        'no excluir indicadores ni cambiar denominadores.')
    dictionary['tratamiento_datos_faltantes']['serie_sin_observaciones_evaluables']['accion'] = (
        'Conservar puntaje observado null y motivo; emitir puntaje_asignado conforme a la política documental.')
    for decision in dictionary['decisiones_metodologicas_por_confirmar']:
        decision['alcance'] = 'Antecedente histórico; prevalecen las decisiones activas versionadas en reglas_calificacion.json.'
    for validation in dictionary['validaciones_finales']:
        if validation['id'] == 'cobertura_periodos':
            validation['regla'] = '18 notas documentales por periodo, conservando null y motivo en todo puntaje observado no acreditado.'
        elif validation['id'] == 'puntajes_consistentes':
            validation['regla'] = 'Variables, hoja y gráficas usan el mismo puntaje_asignado; nunca lo presentan como observado si falta evidencia.'
    dump(dictionary_path, dictionary)
    dump(rules_path, rules)
    research_path = ROOT / 'config/investigacion_seguridad.json'
    dump(research_path, research)
    contract = {'version': '3.2', 'alcance': 'seguridad_investigacion', 'marcador': '{snake_case}',
        'politica_calificacion': {'archivo': 'reglas_calificacion.json', 'seccion': 'calificacion_documental',
                                 'puntajes_documentales_siempre': True, 'puntajes_observados_admiten_null': True},
        'contenido_generado': {'resaltado_amarillo': False, 'trazabilidad_estilo': 'ContenidoJSON',
                              'excepcion_fidelidad_salida': 'Eliminar exclusivamente resaltado/sombreado amarillo, también heredado del original; no modificar el DOCX de origen.'},
        'plantillas': {'medicion': {'archivo': str(target.relative_to(ROOT)), 'sha256': sha256(target),
                                  'origen': str(source.relative_to(ROOT)), 'origen_sha256': sha256(source)}},
        'diccionario': {'archivo': str(dictionary_path.relative_to(ROOT)), 'sha256': sha256(dictionary_path)},
        'reglas': {'archivo': str(rules_path.relative_to(ROOT)), 'sha256': sha256(rules_path)},
        'formato': {'archivo': str(FORMATO.relative_to(ROOT)), 'sha256': sha256(FORMATO)},
        'investigacion': {'archivo': str(research_path.relative_to(ROOT)), 'sha256': sha256(research_path)},
        'metodologia': {'archivo': str(methodology.relative_to(ROOT)), 'sha256': sha256(methodology)},
        'tipografias': [{'archivo': f'assets/fonts/{filename}', 'sha256': sha256(ROOT / 'assets/fonts' / filename)} for _, filename, _ in FONTS],
        'fidelidad': manifest, 'orden_indicadores': list(range(1, 19)),
        'verificar_origen_en_cada_ejecucion': True,
        'correcciones': ['La segunda aparición de personal se traslada después del instituto y se convierte en CUP.'],
        'observaciones': ['Se conservan títulos, listas, estilos, párrafos vacíos y sección del machote; no se añade portada ni logo ausentes.']}
    dump(ROOT / 'config/contrato_documental.json', contract)
    print(f'Parametrización fiel: {len(variables)} variables, {sum(counts.values())} apariciones, {len(manifest["bloques"])} bloques de origen.')
    return contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path)
    args = parser.parse_args()
    try:
        migrar(args.template or origen_default())
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
