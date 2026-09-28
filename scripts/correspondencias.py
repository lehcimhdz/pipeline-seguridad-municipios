"""Correspondencias reproducibles entre el paquete y las definiciones generales.

No modifica el complemento ni marca inferencias como revisión humana. Las
coordenadas son las de documentos.registros: tabla y fila comienzan en uno,
incluido el encabezado. Las fuentes y sus huellas se conservan en el resultado.
"""
from copy import deepcopy
import re
from calificar import filas_por_año, normalizar, numero, coincide
from evidencia_complementaria import poblacion, tasas_comparables


def equivalentes(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    x, y = numero(str(a)), numero(str(b))
    return x == y if x is not None and y is not None else a == b


def conceptos_graficos(section, year, policy, estado=None):
    """Reconoce títulos completos; las cifras se siguen tomando de las tablas."""
    config = policy.get('titulos_graficas', {})
    if config.get('habilitada') is not True:
        return []
    rules = config.get('por_indicador', {}).get(str(section['numero']), [])
    found = []
    for item in section.get('lecturas_graficas', []):
        reading = item.get('lectura', {})
        if reading.get('estado') != 'leida' or item.get('indicador') != section['numero']:
            continue
        title = ' '.join(normalizar(reading.get('titulo', '')).split())
        match = re.fullmatch(r'(.+?):\s*(.+?)\s*\((\d{4})\s*[-–—]\s*(\d{4})\)\.?', title)
        if not match or not int(match[3]) <= year <= int(match[4]):
            continue
        if item['ambito'] == 'municipal':
            municipality = item['fuente'].removesuffix(' PAQUETE SEGURIDAD.docx').removesuffix(' Anexo.docx')
            if match[1].strip() != normalizar(municipality):
                continue
        elif item['ambito'] == 'estatal' and estado and match[1].strip() != normalizar(estado):
            continue
        description = match[2].strip(' ,.')
        for rule in rules:
            if description != normalizar(rule['descripcion']):
                continue
            found.append({'campo': rule['campo'], 'valor': rule['valor'], 'ambito': item['ambito'],
                'evidencia': {'fuente': item['fuente'], 'fuente_sha256': item['fuente_sha256'],
                    'parte': item['parte'], 'sha256': item['sha256'], 'bloque': item['bloque'],
                    'ambito': item['ambito'], 'anio': year, 'titulo': reading['titulo'],
                    'metodo': 'ocr_local', 'motor': reading['motor'], 'idioma': reading['idioma']}})
    return found


def resolver(sections, mappings, definitions, complemento):
    observations = {}
    policy = definitions.get('correspondencias_automaticas', {})
    for section in sections:
        n = section['numero']
        title = normalizar(section.get('nombre', ''))
        manual = complemento.get('observaciones', {}).get(str(n), {})
        rows_by_year = filas_por_año(section)
        years = sorted(set(rows_by_year) | {int(y) for y in manual})
        observations[str(n)] = {}
        for year in years:
            entry = {'_trazabilidad': {}, '_conflictos': []}
            rows = rows_by_year.get(year, [])

            def assign(field, value, evidence, rule, kind='lectura_directa'):
                entry[field] = value
                entry['_trazabilidad'][field] = {
                    'valor': value, 'tipo': kind, 'regla': rule, 'evidencias': evidence}

            def extract(field, column, selected=None, percentage=False):
                selected = rows if selected is None else selected
                candidates = [r for r in selected if column in r['celdas']]
                if len(candidates) != 1:
                    return None
                row = candidates[0]
                value = numero(str(row['celdas'][column]))
                if value is None or value < 0 or (percentage and value > 100):
                    return None
                evidence = [{'ambito': 'municipal', 'anio': year, 'tabla': row['tabla'],
                             'fila': row['fila'], 'columna': column, 'valor': row['celdas'][column]}]
                assign(field, str(value), evidence, f'lectura_columna:{column}')
                return evidence

            title_evidence = [{'ambito': 'municipal', 'anio': year,
                               'indicador': n, 'campo': 'nombre', 'valor': section.get('nombre', '')}]
            if n == 2:
                extract('cursos_reportados', 'Número de cursos')
                extract('servidores_capacitados_reportados', 'Número de servidores capacitados')
                # «Servidores» no demuestra exclusividad de unidad ni conteo único.
            if n in (5, 7):
                evidence = extract('porcentaje_reportado', 'Porcentaje', percentage=True)
                cup = policy.get('cup_vigente', {})
                if (n == 7 and evidence and cup.get('habilitada') is True
                        and title == normalizar(cup['titulo'])):
                    for field, value in (('definicion', 'cup_vigente'), ('universo', 'corporaciones_policiales')):
                        assign(field, value, title_evidence + evidence,
                               'correspondencias_automaticas.cup_vigente', 'homologacion')
                # No se equipara evaluación con aprobación vigente en la ficha 5.
            if n == 4:
                extract('total_personal_reportado', 'Total')
                # Una columna explícita sí permite leer el numerador policial.
                for column in ('Personal de corporaciones policiales', 'Personal policial'):
                    if any(column in row['celdas'] for row in rows):
                        previous = deepcopy(entry['_trazabilidad'].get('personal_policial'))
                        evidence = extract('personal_policial', column)
                        if previous and evidence:
                            if not equivalentes(previous['valor'], entry['personal_policial']):
                                entry['_conflictos'].append({'campo': 'personal_policial',
                                    'detalle': 'Columnas policiales equivalentes con cantidades distintas.',
                                    'evidencias': previous['evidencias'] + evidence})
                            else:
                                previous['evidencias'].extend(evidence)
                            entry['personal_policial'] = previous['valor']
                            entry['_trazabilidad']['personal_policial'] = previous
            if n == 9:
                fields = {'chaleco_balistico': 'chalecos', 'radio': 'radios', 'menos_letal': 'menos_letal'}
                for category, field in fields.items():
                    patterns = mappings.get('equipamiento', {}).get(category, [])
                    selected = [r for r in rows if coincide(r['celdas'].get('Equipamiento', ''), patterns)]
                    extract(field, 'Total', selected)
            if n == 14:
                extract('camaras_reportadas', 'Total')
            if n == 15:
                extract('llamadas_procedentes_reportadas', 'Llamadas procedentes')
                extract('porcentaje_reportado', 'Porcentaje', percentage=True)
            if n == 18:
                columns = {key for row in rows for key in row['celdas'] if key in ('Total', 'Total de personas')}
                if len(columns) == 1:
                    extract('personas_reportadas', next(iter(columns)))

            concepts = conceptos_graficos(section, year, policy, complemento.get('estado'))
            fields = {}
            for concept in concepts:
                key = concept['campo'], concept['ambito']
                fields.setdefault(key, []).append(concept)
            for (field, scope), facts in fields.items():
                values = {fact['valor'] for fact in facts}
                evidence = [fact['evidencia'] for fact in facts]
                if len(values) != 1:
                    entry['_conflictos'].append({'campo': field, 'ambito': scope,
                        'detalle': 'Los títulos de las gráficas discrepan.', 'evidencias': evidence})
                    continue
                if scope == 'municipal' or field == 'universo_camaras':
                    target = f'universo_{scope}' if field == 'universo_camaras' else field
                    assign(target, facts[0]['valor'], evidence,
                           'correspondencias_automaticas.titulos_graficas', 'lectura_grafica')
            if n == 14 and all(entry.get(f'universo_{scope}') == 'camaras_en_servicio' for scope in ('municipal', 'estatal')):
                assign('universo', 'camaras_en_servicio',
                       entry['_trazabilidad']['universo_municipal']['evidencias'] + entry['_trazabilidad']['universo_estatal']['evidencias'],
                       'correspondencias_automaticas.titulos_graficas', 'lectura_grafica')

            supplied = manual.get(str(year), {})
            if supplied:
                if supplied.get('revision') != 'verificada':
                    entry['_conflictos'].append({'campo': 'revision', 'detalle': 'Complemento sin revisión acreditada.'})
                else:
                    for field, value in supplied.items():
                        if field.startswith('_') or field == 'evidencias_campos':
                            continue
                        if field in entry and not equivalentes(entry[field], value):
                            entry['_conflictos'].append({'campo': field, 'paquete': entry[field], 'complemento': value})
                            continue
                        if field not in ('revision', 'fuente', 'localizador'):
                            field_source = supplied.get('evidencias_campos', {}).get(field, supplied)
                            entry['_trazabilidad'].setdefault(field, {
                                'valor': deepcopy(value), 'tipo': 'complemento_verificado',
                                'regla': 'evidencia_complementaria', 'evidencias': [{
                                    'fuente': field_source.get('fuente'), 'localizador': field_source.get('localizador'),
                                    'anio': year, 'indicador': n}]})
                        entry[field] = deepcopy(value)
            if (n == 14 and entry.get('universo') == 'camaras_en_servicio'
                    and any(entry.get(f'universo_{scope}') == 'camaras_fuera_de_servicio' for scope in ('municipal', 'estatal'))):
                entry['_conflictos'].append({'campo': 'universo',
                    'detalle': 'El complemento declara cámaras en servicio y una gráfica declara equipos fuera de servicio.'})
            if (n == 5 and entry.get('definicion') == 'aprobatorias_vigentes'
                    and entry.get('estatus_evaluaciones') == 'no_aprobadas'):
                entry['_conflictos'].append({'campo': 'definicion',
                    'detalle': 'El complemento declara aprobación vigente y la gráfica identifica evaluaciones no aprobadas.'})
            observations[str(n)][str(year)] = entry

    # La dotación usa el mismo personal policial del año, nunca el Total general.
    for year, entry in observations.get('9', {}).items():
        staff = observations.get('4', {}).get(year, {})
        if 'personal_policial' not in staff or staff.get('_conflictos'):
            continue
        value = staff['personal_policial']
        if 'personal_policial' in entry and not equivalentes(entry['personal_policial'], value):
            entry['_conflictos'].append({'campo': 'personal_policial', 'ficha_4': value,
                                         'ficha_9': entry['personal_policial']})
        else:
            entry['personal_policial'] = value
            entry['_trazabilidad']['personal_policial'] = deepcopy(staff['_trazabilidad']['personal_policial'])
    return observations


def auditoria(obs, years):
    """La evaluación guarda sólo evidencias del periodo; el render las recalcula."""
    return {str(y): {'campos': deepcopy(obs.get(str(y), {}).get('_trazabilidad', {})),
                     'conflictos': deepcopy(obs.get(str(y), {}).get('_conflictos', []))}
            for y in years}


def requisitos_pendientes(n, years, obs, data):
    """Diagnóstico de campos faltantes, no un sustituto de revisar_ficha."""
    definitions = {2: {'universo': 'personal_unidad_pc', 'conteo_personas': 'unico'},
                   5: {'universo': 'corporaciones_policiales', 'definicion': 'aprobatorias_vigentes'},
                   7: {'universo': 'corporaciones_policiales', 'definicion': 'cup_vigente'},
                   10: {'universo': 'corporaciones_policiales', 'definicion': 'capacitacion_sin_profesionalizacion'},
                   9: {'naturaleza_del_dato': 'asignado_al_cierre'},
                   14: {'universo': 'camaras_en_servicio'},
                   15: {'registro_municipal': True}, 18: {'incidencia_comparable': True}}
    quantities = {4: ('personal_policial',), 9: ('personal_policial', 'chalecos', 'radios', 'menos_letal'),
                  18: ('personas_mp', 'delitos_municipales', 'personas_mp_estatal', 'delitos_estatales')}
    result = {}
    for year in years:
        entry = obs.get(str(year), {})
        needed = [f'{key}={value}' for key, value in definitions.get(n, {}).items() if entry.get(key) != value]
        if n == 5 and entry.get('estatus_evaluaciones') == 'aprobadas' and 'definicion=aprobatorias_vigentes' in needed:
            needed.remove('definicion=aprobatorias_vigentes')
            needed.append('vigencia_de_las_evaluaciones_aprobadas')
        for key in quantities.get(n, ()):
            value = numero(str(entry.get(key, '')))
            if value is None or value < 0 or (key in ('delitos_municipales', 'delitos_estatales') and value == 0):
                needed.append(key)
        if n == 3 and (not entry.get('grupos_captados') or entry.get('catalogo_completo') is not True):
            needed.append('catalogo_completo_y_grupos_captados_de_la_edicion')
        if n in (4, 15) and not poblacion(data, year):
            needed.append('poblacion_municipal_documentada')
        if n == 14 and tasas_comparables(data, year, 1, 1) is None:
            needed.append('poblaciones_municipal_y_estatal_comparables')
        if entry.get('_conflictos'):
            needed.append('conciliar_contradicciones_documentales')
        if needed:
            result[str(year)] = needed
    return result
