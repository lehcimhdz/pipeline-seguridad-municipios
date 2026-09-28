"""Correspondencias reproducibles entre el paquete y las definiciones generales.

No modifica el complemento ni marca inferencias como revisión humana. Las
coordenadas son las de documentos.registros: tabla y fila comienzan en uno,
incluido el encabezado. Las fuentes y sus huellas se conservan en el resultado.
"""
from copy import deepcopy
from calificar import filas_por_año, normalizar, numero, coincide
from evidencia_complementaria import poblacion, tasas_comparables


def equivalentes(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    x, y = numero(str(a)), numero(str(b))
    return x == y if x is not None and y is not None else a == b


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

            supplied = manual.get(str(year), {})
            if supplied:
                if supplied.get('revision') != 'verificada':
                    entry['_conflictos'].append({'campo': 'revision', 'detalle': 'Complemento sin revisión acreditada.'})
                else:
                    for field, value in supplied.items():
                        if field.startswith('_'):
                            continue
                        if field in entry and not equivalentes(entry[field], value):
                            entry['_conflictos'].append({'campo': field, 'paquete': entry[field], 'complemento': value})
                            continue
                        if field not in ('revision', 'fuente', 'localizador'):
                            entry['_trazabilidad'].setdefault(field, {
                                'valor': deepcopy(value), 'tipo': 'complemento_verificado',
                                'regla': 'evidencia_complementaria', 'evidencias': [{
                                    'fuente': supplied.get('fuente'), 'localizador': supplied.get('localizador'),
                                    'anio': year, 'indicador': n}]})
                        entry[field] = deepcopy(value)
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
