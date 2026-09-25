"""Cálculo determinista de criterios explícitos; nunca imputa datos faltantes."""
from decimal import Decimal, ROUND_HALF_UP
import operator
import re
import unicodedata
from documentos import registros

OPS = {'eq': operator.eq, 'ge': operator.ge, 'le': operator.le, 'lt': operator.lt}


def normalizar(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower().strip())
                   if unicodedata.category(c) != 'Mn')


def numero(value):
    # Las tablas fuente usan coma de millares y punto decimal.
    try:
        result = Decimal(value.strip().replace(',', ''))
        return result if result.is_finite() else None
    except Exception:
        return None


def evaluar_reglas(metrics, rules):
    for rule in rules:
        if all(key in metrics and OPS[op](metrics[key], Decimal(str(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else value)
               for key, op, value in rule['todas']):
            return {'puntaje': rule['puntaje'], 'criterio_aplicado': rule['referencia']}
    return {'puntaje': None, 'motivo': 'La combinación observada no tiene un criterio inequívoco en la ficha.'}


def coincide(value, patterns):
    value = normalizar(value)
    return any(re.search(pattern, value) for pattern in patterns)


def filas_por_año(section, scope='municipal'):
    result = {}
    for table in section['tablas']:
        if table['ambito'] != scope:
            continue
        for row in registros(table):
            result.setdefault(row['año'], []).append(row)
    return result


def calificar_temas_proteccion(section, period, mappings):
    rows = filas_por_año(section)
    years = sorted(rows)
    selected = years[-2:] if period == 'ultimo_periodo' else years
    found = set()
    for year in selected:
        for row in rows[year]:
            topic = row['celdas'].get('Tema impartido', '')
            for core, patterns in mappings['proteccion_civil_temas_nucleo'].items():
                if coincide(topic, patterns):
                    found.add(core)
    count = len(found)
    if count >= 5 and 'identificacion_y_analisis_de_riesgos' in found:
        score = 5
    elif count == 4:
        score = 4
    elif count in (2, 3):
        score = 3
    elif count == 1:
        score = 2
    else:
        score = 1
    return {'puntaje': score, 'criterio_aplicado': f'Ficha 3: {count} temas núcleo',
            'años_observados': years, 'años_evaluados': selected,
            'temas_nucleo': sorted(found)}


def calificar_temas_policiales(section, period, mappings):
    rows = filas_por_año(section)
    years = sorted(rows)
    selected = years[-2:] if period == 'ultimo_periodo' else years
    coverage = {}
    for year in selected:
        coverage[year] = {}
        for row in rows[year]:
            topic = row['celdas'].get('Tema', '')
            percentage = numero(row['celdas'].get('Porcentaje', ''))
            total = numero(row['celdas'].get('Total', ''))
            for core, patterns in mappings['capacitacion_policial_nucleo'].items():
                if coincide(topic, patterns) and total is not None and total > 0:
                    coverage[year][core] = max(coverage[year].get(core, Decimal(0)), percentage or Decimal(0))
    with_two_or_more = [year for year, topics in coverage.items()
                         if sum(value >= 50 for value in topics.values()) >= 2]
    with_any = [year for year, topics in coverage.items() if topics]
    if len(with_two_or_more) == len(selected):
        score = 5 if period == 'general' else 4
    elif len(with_any) >= (len(selected) + 1) // 2:
        score = 3
    elif len(with_any) == 1:
        score = 2
    else:
        score = 1
    return {'puntaje': score, 'criterio_aplicado': f'Ficha 10: cobertura de temas núcleo en {len(with_any)}/{len(selected)} ediciones',
            'años_observados': years, 'años_evaluados': selected,
            'cobertura_por_año': {str(year): {key: str(value) for key, value in values.items()}
                                  for year, values in coverage.items()}}


def calificar_llamadas(section, period):
    municipal = filas_por_año(section, 'municipal')
    state = filas_por_año(section, 'estatal')
    years = sorted(set(municipal) | set(state))
    selected = years[-2:] if period == 'ultimo_periodo' else years
    comparisons = {}
    incomplete = False
    for year in selected:
        local = municipal.get(year, [])
        entity = state.get(year, [])
        if len(local) != 1 or len(entity) != 1:
            incomplete = True
            continue
        local_value = numero(local[0]['celdas'].get('Porcentaje', ''))
        state_value = numero(entity[0]['celdas'].get('Porcentaje', ''))
        if local_value is None or state_value is None:
            incomplete = True
            continue
        comparisons[year] = {'municipal': local_value, 'estatal': state_value}
    if not comparisons:
        return {'puntaje': 1, 'criterio_aplicado': 'Ficha 15: no hay dato comparable',
                'años_observados': years, 'años_evaluados': selected}
    all_at_or_above = len(comparisons) == len(selected) and all(
        value['municipal'] >= value['estatal'] for value in comparisons.values())
    any_below = any(value['municipal'] < value['estatal'] for value in comparisons.values())
    if all_at_or_above:
        score = 5 if period == 'general' else 4
    elif incomplete:
        score = 2
    elif any_below:
        score = 3
    else:
        return {'puntaje': None, 'motivo': 'Comparación de llamadas no cubierta por un criterio inequívoco.',
                'años_observados': years, 'años_evaluados': selected}
    return {'puntaje': score, 'criterio_aplicado': f'Ficha 15: comparación municipal-estatal en {len(comparisons)} años',
            'años_observados': years, 'años_evaluados': selected,
            'comparacion': {str(year): {key: str(value) for key, value in values.items()}
                            for year, values in comparisons.items()}}


def calificar_personal(section, period, external):
    rows = filas_por_año(section)
    years = sorted(rows)
    selected = years[-2:] if period == 'ultimo_periodo' else years
    population = external.get('poblacion_municipal', {})
    rates = {}
    for year in selected:
        records = rows.get(year, [])
        if len(records) != 1 or year not in population:
            return {'puntaje': None, 'motivo': 'Falta personal o población municipal comparable.',
                    'años_observados': years, 'años_evaluados': selected}
        staff = numero(records[0]['celdas'].get('Total', ''))
        if staff is None or population[year] <= 0:
            return {'puntaje': None, 'motivo': 'Personal o población no válido.',
                    'años_observados': years, 'años_evaluados': selected}
        rates[year] = staff / population[year] * 1000
    average = sum(rates.values()) / len(rates)
    all_standard = all(value >= Decimal('1.8') for value in rates.values())
    if all_standard:
        score = 5 if period == 'general' else 4
    elif Decimal('1.2') <= average <= Decimal('1.79') or (rates[selected[-1]] >= Decimal('1.8') and sum(value >= Decimal('1.8') for value in rates.values()) == 1):
        score = 3
    elif Decimal('0.8') <= average <= Decimal('1.19'):
        score = 2
    elif average < Decimal('0.8'):
        score = 1
    else:
        return {'puntaje': None, 'motivo': 'Promedio de personal cae en un hueco no definido por la ficha.',
                'años_observados': years, 'años_evaluados': selected}
    return {'puntaje': score, 'criterio_aplicado': f'Ficha 4: promedio {average:.3f} por mil habitantes',
            'años_observados': years, 'años_evaluados': selected,
            'tasas_por_mil': {str(year): str(value) for year, value in rates.items()}}


def calificar_camaras(section, period, external):
    municipal = filas_por_año(section, 'municipal')
    state = filas_por_año(section, 'estatal')
    years = sorted(set(municipal) | set(state))
    selected = years[-2:] if period == 'ultimo_periodo' else years
    local_population = external.get('poblacion_municipal', {})
    state_population = external.get('poblacion_estatal', {})
    rates = {}
    for year in selected:
        local, entity = municipal.get(year, []), state.get(year, [])
        if len(local) != 1 or len(entity) != 1 or year not in local_population or year not in state_population:
            return {'puntaje': None, 'motivo': 'Faltan cámaras o población comparable municipal/estatal.',
                    'años_observados': years, 'años_evaluados': selected}
        local_total, state_total = numero(local[0]['celdas'].get('Total', '')), numero(entity[0]['celdas'].get('Total', ''))
        if local_total is None or state_total is None or local_population[year] <= 0 or state_population[year] <= 0:
            return {'puntaje': None, 'motivo': 'Cámaras o población no válidas.',
                    'años_observados': years, 'años_evaluados': selected}
        rates[year] = {'municipal': local_total / local_population[year] * 1000,
                       'estatal': state_total / state_population[year] * 1000,
                       'camaras': local_total}
    all_at_or_above = all(value['municipal'] >= value['estatal'] for value in rates.values())
    no_setbacks = all(rates[year]['municipal'] >= rates[previous]['municipal']
                      for previous, year in zip(selected, selected[1:]))
    if all(value['camaras'] > 0 for value in rates.values()) and all_at_or_above and no_setbacks:
        score = 5
    elif period == 'ultimo_periodo' and all_at_or_above:
        score = 4
    elif any(value['camaras'] > 0 for value in rates.values()) and any(value['municipal'] < value['estatal'] for value in rates.values()):
        score = 3
    elif sum(value['camaras'] > 0 for value in rates.values()) == 1:
        score = 2
    elif not any(value['camaras'] > 0 for value in rates.values()):
        score = 1
    else:
        return {'puntaje': None, 'motivo': 'Serie de cámaras no cubierta por un criterio inequívoco.',
                'años_observados': years, 'años_evaluados': selected}
    return {'puntaje': score, 'criterio_aplicado': 'Ficha 14: tasas de cámaras municipal y estatal',
            'años_observados': years, 'años_evaluados': selected,
            'tasas_por_mil': {str(year): {key: str(value) for key, value in values.items()} for year, values in rates.items()}}


def calificar_puestas_a_disposicion(section, period, external):
    municipal = filas_por_año(section, 'municipal')
    state = filas_por_año(section, 'estatal')
    years = sorted(set(municipal) | set(state))
    selected = years[-2:] if period == 'ultimo_periodo' else years
    municipal_incidence = external.get('incidencia_municipal', {})
    state_incidence = external.get('incidencia_estatal', {})
    ratios = {}
    for year in selected:
        local, entity = municipal.get(year, []), state.get(year, [])
        if len(local) != 1 or len(entity) != 1 or year not in municipal_incidence or year not in state_incidence:
            return {'puntaje': None, 'motivo': 'Faltan incidencia o puestas a disposición comparables.',
                    'años_observados': years, 'años_evaluados': selected}
        local_total, state_total = numero(local[0]['celdas'].get('Total de personas', '')), numero(entity[0]['celdas'].get('Total', ''))
        if local_total is None or state_total is None or municipal_incidence[year] <= 0 or state_incidence[year] <= 0:
            return {'puntaje': None, 'motivo': 'Incidencia o puestas a disposición no válidas.',
                    'años_observados': years, 'años_evaluados': selected}
        ratios[year] = {'municipal': local_total / municipal_incidence[year],
                        'estatal': state_total / state_incidence[year]}
    relative = [value['municipal'] / value['estatal'] for value in ratios.values()]
    if all(value >= 1 for value in relative):
        score = 4
    elif all(Decimal('0.75') <= value < 1 for value in relative):
        score = 3
    elif any(value < Decimal('0.75') for value in relative):
        score = 2
    else:
        return {'puntaje': None, 'motivo': 'Razón de puestas a disposición no cubierta por un criterio inequívoco.',
                'años_observados': years, 'años_evaluados': selected}
    return {'puntaje': score, 'criterio_aplicado': 'Ficha 18: razón de puestas a disposición frente a incidencia',
            'años_observados': years, 'años_evaluados': selected,
            'razones': {str(year): {key: str(value) for key, value in values.items()} for year, values in ratios.items()},
            'nota': 'El puntaje 5 exige además estabilidad y revisión documentada de recomendaciones de derechos humanos.'}


def calificar_indicador(section, ficha, period, mappings=None, external=None):
    tables = [table for table in section['tablas'] if table['ambito'] == 'municipal']
    rows = [row for table in tables for row in registros(table)]
    years = sorted({row['año'] for row in rows})
    selected = years[-2:] if period == 'ultimo_periodo' else years
    result = {'puntaje': None, 'años_observados': years, 'años_evaluados': selected,
              'cobertura': 'Observaciones documentadas; la ausencia de ediciones anteriores no acredita inaplicabilidad.'}
    if not selected or (period == 'ultimo_periodo' and len(selected) < 2):
        return {**result, 'motivo': 'Cobertura temporal insuficiente.'}
    if mappings and ficha['id'] == 3:
        return calificar_temas_proteccion(section, period, mappings)
    if mappings and ficha['id'] == 10:
        return calificar_temas_policiales(section, period, mappings)
    if ficha['id'] == 15:
        return calificar_llamadas(section, period)
    if external and ficha['id'] == 4:
        return calificar_personal(section, period, external)
    if external and ficha['id'] == 14:
        return calificar_camaras(section, period, external)
    if external and ficha['id'] == 18:
        return calificar_puestas_a_disposicion(section, period, external)
    if ficha['metodo'] == 'revision_contextual':
        return {**result, 'motivo': 'Requiere homologación, denominadores o interpretación de la ficha.',
                'datos_requeridos': list(ficha['datos_requeridos'])}
    selected_rows = [row for row in rows if row['año'] in selected]
    if len(selected_rows) != len(selected):
        return {**result, 'motivo': 'Más de una observación por año; requiere conciliación.'}
    selected_rows.sort(key=lambda row: row['año'])
    result['evidencia'] = selected_rows
    values = []
    staff = []
    for row in selected_rows:
        cells = row['celdas']
        data = [value for key, value in cells.items() if key != 'Año']
        if ficha['metodo'] == 'existencia':
            raw = normalizar(data[0])
            value = True if raw in ('si', 'si existe', 'existe') else False if raw in ('no', 'no existe') else None
        elif ficha['metodo'] == 'porcentaje':
            value = numero(cells.get('Porcentaje', ''))
            if value is not None and not 0 <= value <= 100:
                value = None
        else:
            courses = numero(cells.get('Número de cursos', ''))
            trained = numero(cells.get('Número de servidores capacitados', ''))
            if courses is None or trained is None or courses < 0 or trained < 0:
                value = None
            else:
                value = courses > 0
                staff.append(trained > 0)
        if value is None:
            return {**result, 'motivo': 'Dato vacío, no reconocido o fuera de rango; clasificar su causa antes de puntuar.'}
        values.append(value)
    if ficha['metodo'] == 'porcentaje':
        metrics = {'promedio': sum(values) / len(values), 'minimo': min(values)}
    else:
        metrics = {'todas': all(values), 'alguna': any(values), 'ultima': values[-1],
                   'dos_recientes': len(values) >= 2 and all(values[-2:]),
                   'ninguna_reciente': len(values) >= 2 and not any(values[-2:]),
                   'proporcion': Decimal(sum(values)) / len(values)}
        if ficha['metodo'] == 'cursos':
            metrics['cursos_y_personal_siempre'] = all(values) and all(staff)
    result.update(evaluar_reglas(metrics, ficha['reglas_ejecutables']))
    result['metricas'] = {key: str(value) if isinstance(value, Decimal) else value for key, value in metrics.items()}
    return result


def dependencias(results):
    # Las reglas particulares se aplican antes de promediar dimensiones.
    if results[2]['puntaje'] == 1:
        results[3].update(puntaje=1, criterio_aplicado='Ficha 3: indicador 2 = 1')
        results[3].pop('motivo', None)
    institute = results[6]
    if institute['puntaje'] is not None and institute['puntaje'] < 3:
        training = results[10]['puntaje']
        if training is None:
            institute.update(puntaje=None, motivo='Se requiere indicador 10 para aplicar el mínimo de formación externa.')
        elif training >= 3:
            institute.update(puntaje=3, criterio_aplicado='Ficha 6: formación del indicador 10 >= 3')
    patrol = results[12]
    if patrol['puntaje'] is not None and patrol['puntaje'] > 3:
        geography = results[11]['puntaje']
        if geography is None:
            patrol.update(puntaje=None, motivo='Se requiere indicador 11 para verificar el máximo de patrullajes.')
        elif geography == 1:
            patrol.update(puntaje=3, criterio_aplicado='Ficha 12: máximo 3 si indicador 11 = 1')


def categoria(value, rules):
    rounded = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    for item in rules['escala']:
        if rounded >= Decimal(str(item['minimo'])):
            return item['calificacion']
    raise ValueError('Puntaje fuera de rango')


def agregar(results, rules, sin_respuesta=()):
    expected = set(range(1, 19))
    if set(results) != expected:
        raise ValueError('Se requieren exactamente los indicadores 1–18.')
    pending = [key for key, value in results.items() if value['puntaje'] is None]
    if pending:
        return {'estado': 'pendiente', 'indicadores_pendientes': pending, 'calificacion_final': None}
    scores = {key: value['puntaje'] for key, value in results.items()}
    if any(type(value) is not int or not 1 <= value <= 5 for value in scores.values()):
        raise ValueError('Puntajes inválidos.')
    if any(key not in expected or scores[key] != 1 for key in sin_respuesta):
        raise ValueError('Falta de respuesta sólo puede registrarse para indicadores con puntaje 1.')
    dims = {name: sum(Decimal(scores[i]) for i in ids) / len(ids) for name, ids in rules['dimensiones'].items()}
    mean = sum(dims.values()) / len(dims)
    preliminary = categoria(mean, rules)
    order = ['CATASTRÓFICO', 'MAL', 'REGULAR', 'MUY BIEN', 'EXCELENTE']
    final = order.index(preliminary)
    applied = []

    def cap(rule, limit):
        nonlocal final
        old = final
        final = min(final, limit)
        applied.append({'regla_id': rule, 'modifica_calificacion': old != final})

    if min(dims.values()) < Decimal('1.5'):
        cap(1, 2)
    if final == 4 and (min(dims.values()) < 4 or min(scores.values()) == 1):
        cap(2, 3)
    if final == 3 and min(dims.values()) < Decimal('2.5'):
        cap(3, 2)
    if len(set(sin_respuesta)) >= 10:
        cap(4, 0)
    return {'estado': 'calculado', 'promedios_dimension': {key: str(value) for key, value in dims.items()},
            'promedio_tres_dimensiones': str(mean), 'calificacion_preliminar': preliminary,
            'calificacion_final': order[final], 'candados_aplicados': applied,
            'redondeo': 'ROUND_HALF_UP a dos decimales sólo para clasificación; criterio operativo explícito.'}
