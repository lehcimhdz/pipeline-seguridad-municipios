"""Deriva SEGURIDAD v3 del machote de investigación sin modificar el original."""
from collections import Counter
from copy import deepcopy
import argparse
import hashlib
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
from logo_editorial import insertar, LOGO, LAYOUT

ROOT = Path(__file__).resolve().parents[1]
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MARKER = re.compile(r'(?<!\{)\{([a-z][a-z0-9_]*)\}(?!\})')
GROUPS = {
    1: ('proteccion_civil', 'Protección civil', [1, 2, 3],
        ['Tratados y leyes en materia de protección civil y prevención de desastres',
         'Recomendaciones de Naciones Unidas', 'Mínimos necesarios para los indicadores 1, 2 y 3']),
    4: ('condiciones_personal', 'Condiciones del personal', list(range(4, 11)),
        ['Leyes nacionales y condiciones laborales mínimas', 'Reportes de UNODC (UNDOC en el original)',
         'Revisiones sistemáticas: condiciones laborales de la policía y seguridad pública']),
    11: ('inteligencia_policial', 'Información e inteligencia policial', list(range(11, 17)),
         ['Revisiones sistemáticas de patrullaje policial', 'Hotspots', 'Policía comunitaria',
          'Evaluación policial', 'Policía y derechos humanos', 'CCTV', 'Mediación de conflictos']),
    17: ('eficiencia_policial', 'Eficiencia policial', [17, 18],
         ['Estándares de derechos humanos: México, Naciones Unidas y sistema interamericano',
          'Letalidad policial', 'Detenciones, seguridad, cifra negra, eficiencia y abuso policial'])
}


def texto(node):
    return ''.join(t.text or '' for t in node.iter(W + 't'))


def paragraph(value, role='cuerpo', initial=True):
    p = ET.Element(W + 'p')
    ET.SubElement(ET.SubElement(p, W + 'r'), W + 't').text = value
    return configurar(p, 'medicion', role, initial)


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
    source.relative_to(ROOT)  # El origen contratado pertenece a este repositorio.
    with zipfile.ZipFile(source) as z:
        files = {n: z.read(n) for n in z.namelist()}
    root = ET.fromstring(files['word/document.xml'])
    body = root.find(W + 'body')
    blocks = list(body)
    notes = [{'bloque': i, 'texto': texto(b).strip()} for i, b in enumerate(blocks) if texto(b).strip()]
    if not notes or notes[0]['texto'] != 'SEGURIDAD':
        raise ValueError('El machote de investigación debe contener exclusivamente el capítulo SEGURIDAD.')
    slots = [i for i, b in enumerate(blocks) if texto(b).strip() == '[INSERTAR ANÁLISIS E INTERCALAR GRÁFICAS Y/O TABLAS]']
    if len(slots) != 18:
        raise ValueError(f'Se requieren 18 bloques de indicador; encontrados: {len(slots)}. Revisar catálogo antes de migrar.')
    dictionary_path = ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json'
    dictionary = json.loads(dictionary_path.read_text(encoding='utf-8'))
    rules_path = ROOT / 'reglas_calificacion.json'
    methodology = ROOT / 'config/metodologia_seguridad.json'
    if not methodology.exists():
        dump(methodology, json.loads(rules_path.read_text(encoding='utf-8')))
    historical = json.loads(methodology.read_text(encoding='utf-8'))
    catalog = dictionary['catalogo_indicadores']
    if [item['id'] for item in catalog] != list(range(1, 19)):
        raise ValueError('Catálogo de seguridad distinto de 18 indicadores.')
    original_names = [texto(blocks[i - 1]).strip() for i in slots]
    # Aceptar el orden correcto o la duplicación editorial ya identificada.
    def norm(t):
        return re.sub(r'[^a-z0-9]', '', ''.join(c for c in unicodedata.normalize('NFD', t.lower())
                                              if unicodedata.category(c) != 'Mn'))
    expected_names = [norm(item['nombre']) for item in catalog]
    names = [norm(t) for t in original_names]
    aliases = {2: norm('Temas de la capacitación (Protección Civil)'), 4: norm('Evaluaciones de control de confianza (policía)'),
               5: norm('Instituto de formación, capacitación y/o profesionalización policial municipal'),
               9: norm('Temas de capacitación'), 16: norm('Cambio en el estado de fuerza, egresos y fallecimientos')}
    canonical = [names[i] == expected_names[i] or names[i] == aliases.get(i) for i in range(18)]
    duplicate_layout = names[3] == names[4] == norm('Personal destinado a funciones de seguridad pública')
    if duplicate_layout:
        # La segunda copia no demuestra un nuevo indicador: CUP sigue siendo el 7.
        repaired = names[:4] + names[5:7] + [expected_names[6]] + names[7:]
        canonical = [repaired[i] == expected_names[i] or repaired[i] == aliases.get(i) for i in range(18)]
    if not all(canonical):
        raise ValueError('Cambió el inventario o el orden de indicadores del origen; revisar la correspondencia antes de migrar.')
    final_section = deepcopy(body.find(W + 'sectPr'))
    if final_section is None:
        raise ValueError('Machote sin configuración de página.')
    for node in final_section.findall(W + 'cols'):
        node.set(W + 'num', '1')
    for node in final_section.findall(W + 'type'):
        node.set(W + 'val', 'nextPage')
    for b in list(body):
        body.remove(b)
    title = paragraph('Mediciones de Funcionamiento Municipal — SEGURIDAD', 'titulo')
    page = final_section.find(W + 'pgSz'); margins = final_section.find(W + 'pgMar')
    usable = int(page.get(W + 'h')) - int(margins.get(W + 'top')) - int(margins.get(W + 'bottom'))
    title.find(W + 'pPr/' + W + 'spacing').set(W + 'before', str(max(0, (usable - 1600) // 2)))
    body.append(title)
    identity = paragraph('{municipio}, {estado}')
    identity.find(W + 'pPr/' + W + 'jc').set(W + 'val', 'center')
    body.append(identity)
    body.append(insertar(files))
    cover_end = ET.Element(W + 'p')
    ET.SubElement(cover_end, W + 'pPr').append(deepcopy(final_section))
    body.append(cover_end)
    body.append(paragraph('SEGURIDAD', 'capitulo'))
    body.append(paragraph('CALIFICACIÓN GENERAL: {calificacion_general}', 'calificacion'))
    body.append(paragraph('CALIFICACIÓN DEL ÚLTIMO PERIODO: {calificacion_ultimo_periodo}', 'calificacion'))
    for heading, keys in [
        ('Interpretación del periodo general', ['bienes_a_proteger', 'comparacion_estatal_municipal', 'avances_municipales', 'resumen_general']),
        ('Interpretación del último periodo', ['resumen_ultimo_periodo', 'resumen_proteccion_civil', 'resumen_condiciones_personal', 'resumen_inteligencia_eficiencia']),
        ('Orientación para el gobierno municipal', ['tendencia_general', 'recomendaciones_gobierno']),
        ('Prioridades de seguridad', ['fortalezas_seguridad', 'areas_mejora_seguridad', 'justificacion_prioridades'])]:
        body.append(paragraph(heading, 'subcapitulo'))
        for index, key in enumerate(keys):
            body.append(paragraph('{' + key + '}', initial=index == 0))
    research = {'version': '1.0', 'origen': str(source.relative_to(ROOT)), 'origen_sha256': sha256(source),
                'instrucciones_originales': notes, 'lineas': [],
                'regla': 'Los benchmarks deben sustentarse con referencias verificadas; no modifican los puntajes ni los candados.'}
    for entry in catalog:
        number = entry['id']
        if number in GROUPS:
            code, heading, ids, topics = GROUPS[number]
            body.append(paragraph(heading.upper(), 'capitulo'))
            key = 'benchmark_' + code
            body.append(paragraph('{' + key + '}'))
            research['lineas'].append({'id': code, 'variable': key, 'indicadores': ids, 'temas_requeridos': topics,
                                       'estado_inicial': 'pendiente', 'fuentes_iniciales': []})
        body.append(paragraph(f"Indicador {number:02d}: {entry['nombre']}", 'subcapitulo'))
        keys = [f'analisis_indicador_{number:02d}']
        if number in (1, 2, 3):
            keys.append(f'minimos_indicador_{number:02d}')
        keys.extend([f'graficas_indicador_{number:02d}', f'tablas_indicador_{number:02d}', f'cierre_indicador_{number:02d}'])
        for key in keys:
            body.append(paragraph('{' + key + '}'))
    body.append(paragraph('Fuentes documentales y referencias', 'subcapitulo'))
    body.append(paragraph('{bibliografia}', 'bibliografia'))
    body.append(final_section)
    files['word/document.xml'] = ET.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
    incrustar(files)
    target = ROOT / 'templates/seguridad_medicion_v3.docx'
    guardar_docx(target, files)
    counts = Counter(MARKER.findall(texto(root)))
    variables = {}
    research_keys = {line['variable'] for line in research['lineas']} | {f'minimos_indicador_{i:02d}' for i in range(1, 4)}
    for key, count in counts.items():
        tipo = 'array' if key.startswith(('graficas_', 'tablas_')) else 'string'
        variables[key] = {'marcador': '{' + key + '}', 'apariciones': count, 'tipo_dato': tipo,
                          'apariciones_por_documento': {'medicion': count},
                          'tipo_contenido': 'graficas' if key.startswith('graficas_') else 'tablas' if tipo == 'array' else 'texto',
                          'origen_contenido': 'investigacion_verificada' if key in research_keys else 'evidencia_documental',
                          'debe_contener': 'Contenido de seguridad sustentado; nunca convertir notas de investigación en afirmaciones verificadas.',
                          'obligatorio': not key.startswith('graficas_')}
    dictionary['variables_documento'] = variables
    dictionary['metadatos'].update(version='3.0', fuente=str(source.relative_to(ROOT)), documento_modificado=False,
                                  alcance_activo='Sólo medición de SEGURIDAD, con investigación explícita y separada de la puntuación.')
    dictionary['metadatos']['cobertura_verificada'] = {'marcadores_de_variables_unicos': len(variables),
        'apariciones_de_variables': sum(counts.values()), 'indicadores': 18, 'dimensiones': 3,
        'lineas_de_investigacion': 4, 'periodos_de_evaluacion': 2}
    dictionary['convenciones']['marcadores'] = {'formato_en_word': '{nombre_variable}',
        'formato_de_clave_json': 'nombre_variable', 'regla': 'Llaves simples y snake_case ASCII; identificar indicador y contexto.'}
    dictionary['convenciones']['nombres_de_variables'].update(conservar_nombres_existentes=False, conservar_letra_ñ=False,
        ejemplos=['municipio', 'benchmark_proteccion_civil', 'analisis_indicador_01'])
    dictionary['marcadores_no_tratados_como_variables'] = {}
    dictionary['modelos_reutilizables']['tabla_word_v3'] = {'titulo': 'string', 'ambito': 'municipal|estatal',
                                                         'filas': 'array de arrays de strings', 'tabla_fuente': 'integer'}
    dictionary['modelos_reutilizables']['grafica_word_v3'] = {'tipo': 'puntajes', 'titulo': 'string',
        'categorias': 'array de strings', 'valores': 'array de number|null', 'fuente': 'string'}
    dictionary['modelos_reutilizables']['investigacion_v3'] = {
        'version': '1.0', 'lineas': 'array de {id, estado: verificado, analisis, referencias}',
        'referencia': {'titulo': 'string', 'url': 'https URL primaria', 'fecha_consulta': 'YYYY-MM-DD',
                       'localizador': 'artículo, sección o página', 'aplicabilidad': 'string', 'revisado_por': 'string'},
        'minimos_indicadores': 'object con claves 01, 02 y 03 y valores {texto, referencias: [urls declaradas]}'}
    dump(dictionary_path, dictionary)
    rules = deepcopy(historical)
    rules['version'] = '3.0'
    rules['fuente_historica'] = historical['fuente']
    rules['fuente'] = {'archivo': str(methodology.relative_to(ROOT)), 'sha256': sha256(methodology)}
    rules['alcance'] = 'Metodología histórica de seguridad preservada. El machote rzg aporta instrucciones editoriales y de investigación, no nuevos umbrales.'
    rules['investigacion_modifica_puntajes'] = False
    dump(rules_path, rules)
    research_path = ROOT / 'config/investigacion_seguridad.json'
    dump(research_path, research)
    contract = {'version': '3.0', 'alcance': 'seguridad_investigacion', 'marcador': '{snake_case}',
        'plantillas': {'medicion': {'archivo': str(target.relative_to(ROOT)), 'sha256': sha256(target),
                                 'origen': str(source.relative_to(ROOT)), 'origen_sha256': sha256(source)}},
        'diccionario': {'archivo': str(dictionary_path.relative_to(ROOT)), 'sha256': sha256(dictionary_path)},
        'reglas': {'archivo': str(rules_path.relative_to(ROOT)), 'sha256': sha256(rules_path)},
        'formato': {'archivo': str(FORMATO.relative_to(ROOT)), 'sha256': sha256(FORMATO)},
        'investigacion': {'archivo': str(research_path.relative_to(ROOT)), 'sha256': sha256(research_path)},
        'metodologia': {'archivo': str(methodology.relative_to(ROOT)), 'sha256': sha256(methodology)},
        'tipografias': [{'archivo': f'assets/fonts/{filename}', 'sha256': sha256(ROOT / 'assets/fonts' / filename)} for _, filename, _ in FONTS],
        'logotipo': [{'archivo': str(p.relative_to(ROOT)), 'sha256': sha256(p)} for p in (LOGO, LAYOUT)],
        'orden_indicadores': list(range(1, 19)), 'verificar_origen_en_cada_ejecucion': True,
        'correcciones': ['Duplicado de personal sustituido por el indicador 7 CUP, conservando orden 1–18.'] if duplicate_layout else [],
        'observaciones': ['El machote nuevo no incluye logo; la base reutiliza el logo de InstitutionWorks aprobado en pipeline-v2, a 5 cm y altura proporcional.']}
    dump(ROOT / 'config/contrato_documental.json', contract)
    print(f'Migración v3: {len(variables)} variables, {sum(counts.values())} apariciones, 4 líneas de investigación. Original intacto.')
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
