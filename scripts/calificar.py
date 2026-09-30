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


def tema_sin_informacion(value):
    """Distingue un tema desconocido de una ausencia explícita como «Ninguno»."""
    normalized = re.sub(r'\s+', ' ', normalizar(value)).rstrip('.')
    abbreviation = re.sub(r'[.\s/]', '', normalized)
    return abbreviation in ('nd', 'sd') or normalized in {
        '', 'sin informacion', 'no disponible', 'no especificado',
        'no identificado', 'sin dato', 'sin datos', 'no se reporta', 'no aplica',
    }


def filas_por_año(section, scope='municipal'):
    result = {}
    for table in section['tablas']:
        if table['ambito'] != scope:
            continue
        for row in registros(table):
            result.setdefault(row['año'], []).append(row)
    return result


def definir_periodos(sections):
    years = sorted({year for section in sections for year in filas_por_año(section)})
    editions = sorted({year for section in sections if section['numero'] <= 16
                       for year in filas_por_año(section)})[-2:]
    annual = sorted({year for section in sections if section['numero'] >= 17
                     for year in filas_por_año(section)})
    annual = [annual[-1] - 1, annual[-1]] if annual else []
    recent = sorted(set(editions + annual))
    return {
        'general': {'años_objetivo': years, 'año_inicial': years[0] if years else None,
                    'año_final': years[-1] if years else None},
        'ultimo_periodo': {
            'por_indicador': {str(i): editions if i <= 16 else annual for i in range(1, 19)},
            'ediciones_censales': editions, 'años_anuales': annual,
            'año_inicial': recent[0] if recent else None,
            'año_final': recent[-1] if recent else None,
            'criterio': 'Dos ediciones censales recientes para 1–16; dos años calendario recientes para 17–18.'}}


def cobertura_periodo(section, target_years):
    scopes = ('municipal', 'estatal') if section['numero'] == 15 else ('municipal',)
    missing = {scope: sorted(set(target_years) - set(filas_por_año(section, scope))) for scope in scopes}
    missing = {scope: years for scope, years in missing.items() if years}
    valid = (len(target_years) == 2 and target_years[1] > target_years[0]
             and (section['numero'] <= 16 or target_years[1] == target_years[0] + 1))
    return {'cobertura_temporal_insuficiente': bool(missing) or not valid,
            'años_faltantes': sorted({year for years in missing.values() for year in years}),
            'años_faltantes_por_ambito': missing}


def calificar_temas_proteccion(section, period, mappings, años_objetivo=None):
    rows = filas_por_año(section)
    years = sorted(rows)
    selected = años_objetivo if años_objetivo is not None else years
    found = set()
    for year in selected:
        for row in rows.get(year, []):
            topic = row['celdas'].get('Tema impartido', '')
            if tema_sin_informacion(topic):
                return {'puntaje': None, 'motivo': 'Falta identificar el tema de capacitación.',
                        'años_observados': years, 'años_evaluados': selected}
            for core, patterns in mappings['proteccion_civil_temas_nucleo'].items():
                if coincide(topic, patterns):
                    found.add(core)
    count = len(found)
    if count >= 5 and 'identificacion_y_analisis_de_riesgos' in found:
        score = 5
    elif count >= 5:
        return {'puntaje': None, 'motivo': 'La ficha no define un puntaje para cinco temas núcleo sin análisis de riesgos.',
                'años_observados': years, 'años_evaluados': selected, 'temas_nucleo': sorted(found)}
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


def calificar_temas_policiales(section, period, mappings, años_objetivo=None):
    rows = filas_por_año(section)
    years = sorted(rows)
    selected = años_objetivo if años_objetivo is not None else years
    coverage = {}
    for year in selected:
        coverage[year] = {}
        for row in rows.get(year, []):
            topic = row['celdas'].get('Tema', '')
            if tema_sin_informacion(topic):
                return {'puntaje': None, 'motivo': 'Falta identificar el tema de capacitación policial.',
                        'años_observados': years, 'años_evaluados': selected}
            percentage = numero(row['celdas'].get('Porcentaje', ''))
            total = numero(row['celdas'].get('Total', ''))
            for core, patterns in mappings['capacitacion_policial_nucleo'].items():
                if coincide(topic, patterns):
                    if total is None or total < 0 or percentage is None or not 0 <= percentage <= 100:
                        return {'puntaje': None, 'motivo': 'Falta precisar la cantidad o el porcentaje de personal capacitado.',
                                'años_observados': years, 'años_evaluados': selected}
                    if total > 0:
                        coverage[year][core] = max(coverage[year].get(core, Decimal(0)), percentage)
    with_two_or_more = [year for year, topics in coverage.items()
                         if sum(value >= 50 for value in topics.values()) >= 2]
    with_any = [year for year, topics in coverage.items() if topics]
    if len(with_two_or_more) == len(selected):
        score = 5
    elif len(selected) >= 2 and all(year in with_two_or_more for year in selected[-2:]):
        score = 4
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


def calificar_llamadas(section, period, años_objetivo=None):
    municipal = filas_por_año(section, 'municipal')
    state = filas_por_año(section, 'estatal')
    years = sorted(set(municipal) | set(state))
    selected = años_objetivo if años_objetivo is not None else years
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
        if (local_value is None or state_value is None
                or not 0 <= local_value <= 100 or not 0 <= state_value <= 100):
            incomplete = True
            continue
        comparisons[year] = {'municipal': local_value, 'estatal': state_value}
    if not comparisons or incomplete:
        return {'puntaje': None, 'motivo': 'Faltan porcentajes comparables de llamadas municipales y estatales para completar el periodo.',
                'años_observados': years, 'años_evaluados': selected}
    all_at_or_above = len(comparisons) == len(selected) and all(
        value['municipal'] >= value['estatal'] for value in comparisons.values())
    any_below = any(value['municipal'] < value['estatal'] for value in comparisons.values())
    if all_at_or_above:
        score = 5
    elif len(selected) >= 2 and all(comparisons[year]['municipal'] >= comparisons[year]['estatal']
                                   for year in selected[-2:]):
        score = 4
    elif any_below:
        score = 3
    else:
        return {'puntaje': None, 'motivo': 'Comparación de llamadas no cubierta por un criterio inequívoco.',
                'años_observados': years, 'años_evaluados': selected}
    return {'puntaje': score, 'criterio_aplicado': f'Ficha 15: comparación municipal-estatal en {len(comparisons)} años',
            'años_observados': years, 'años_evaluados': selected,
            'comparacion': {str(year): {key: str(value) for key, value in values.items()}
                            for year, values in comparisons.items()}}

def calificar_uniformes(section, mappings, selected):
    rows = filas_por_año(section)
    evidence = {}
    for year in selected:
        basic, annual, supplied = set(), set(), False
        for row in rows.get(year, []):
            cells = row['celdas']
            item = cells.get('Elementos del uniforme', '')
            provided = normalizar(cells.get('Otorgado', ''))
            if not item.strip() or provided not in ('si', 'no'):
                return {'puntaje': None, 'motivo': 'Falta precisar la prenda o su condición de entrega.'}
            if provided == 'no':
                continue
            supplied = True
            frequency = normalizar(cells.get('Frecuencia', '')).replace(' ', '_')
            for core, patterns in mappings['uniformes_basicos'].items():
                if coincide(item, patterns):
                    basic.add(core)
                    normalized = mappings['regla_periodo']['frecuencia'].get(frequency)
                    if normalized is None:
                        return {'puntaje': None, 'motivo': 'Falta identificar la periodicidad de entrega de las prendas básicas.'}
                    if normalized == 'al_menos_anual':
                        annual.add(core)
        evidence[str(year)] = {'prendas_basicas': sorted(basic),
                               'prendas_al_menos_anuales': sorted(annual), 'hubo_dotacion': supplied}
    complete = [year for year in selected if len(evidence[str(year)]['prendas_al_menos_anuales']) >= 5]
    supplied = [year for year in selected if evidence[str(year)]['hubo_dotacion']]
    if not supplied:
        score = 1
    elif len(supplied) == 1 and len(selected) > 1:
        score = 2
    elif len(complete) == len(selected):
        score = 5
    elif len(selected) >= 2 and all(year in complete for year in selected[-2:]):
        score = 4
    else:
        score = 3
    return {'puntaje': score, 'criterio_aplicado': f'Ficha 8, criterio {score}',
            'dotacion_por_edicion': evidence,
            'alcance': 'Prendas y frecuencia declaradas; no acredita entrega a cada integrante.'}


def calificar_fallecimientos(section, selected):
    tables = [table for table in section['tablas'] if table['ambito'] == 'municipal'
              and table['filas'] and table['filas'][0] == ['Año', 'Total']]
    if len(tables) != 1:
        return {'puntaje': None, 'motivo': 'Se requiere identificar una sola serie de fallecimientos municipales.'}
    counts = {}
    for row in registros(tables[0]):
        if row['año'] not in selected:
            continue
        if row['año'] in counts:
            return {'puntaje': None, 'motivo': 'Hay más de un conteo de fallecimientos para un mismo año.'}
        value = numero(row['celdas']['Total'])
        if value is not None and (value < 0 or value != value.to_integral_value()):
            return {'puntaje': None, 'motivo': 'El conteo de fallecimientos debe ser un entero no negativo.'}
        counts[row['año']] = int(value) if value is not None else None
    positive = [year for year, value in counts.items() if value is not None and value > 0]
    missing = [year for year in selected if counts.get(year) is None]
    result = {'fallecimientos_por_año': {str(year): counts.get(year) for year in selected},
              'años_con_fallecimientos': sorted(positive), 'años_sin_conteo': missing}
    # La mayoría puede acreditarse aun cuando otros años sigan desconocidos.
    # No se atribuye el puntaje a falta de respuesta ni se rellenan los vacíos.
    if len(positive) > len(selected) / 2:
        return {**result, 'puntaje': 1, 'criterio_aplicado': 'Ficha 17: fallecimientos en la mayoría de los años',
                'sin_respuesta_municipal': False}
    if missing:
        return {**result, 'puntaje': None, 'motivo': 'Faltan conteos de fallecimientos para aplicar los restantes criterios.'}
    if not positive:
        return {**result, 'puntaje': 5, 'criterio_aplicado': 'Ficha 17: sin fallecimientos en todo el periodo evaluado'}
    if len(selected) >= 2 and all(counts[year] == 0 for year in selected[-2:]):
        return {**result, 'puntaje': 4, 'criterio_aplicado': 'Ficha 17: sin fallecimientos recientes, con casos anteriores'}
    return {**result, 'puntaje': None,
            'motivo': 'Los casos observados requieren tasas comparables o evidencia de enfrentamientos para distinguir los criterios 2 y 3.'}


def calificar_indicador(section, ficha, period, mappings=None, *, años_objetivo=None):
    tables = [table for table in section['tablas'] if table['ambito'] == 'municipal']
    rows = [row for table in tables for row in registros(table)]
    years = sorted({row['año'] for row in rows})
    if period not in ('general', 'ultimo_periodo'):
        raise ValueError('Periodo desconocido.')
    if ficha['id'] == 17:
        mortality_tables = [table for table in tables if table['filas'] and table['filas'][0] == ['Año', 'Total']]
        if len(mortality_tables) == 1:
            years = sorted({row['año'] for row in registros(mortality_tables[0])})
    selected = (list(años_objetivo) if años_objetivo is not None
                else years[-2:] if ficha['id'] <= 16
                else [years[-1] - 1, years[-1]] if years else []) if period == 'ultimo_periodo' else years
    if period == 'general' and ficha['id'] >= 17 and years:
        selected = list(range(years[0], years[-1] + 1))
    result = {'puntaje': None, 'años_observados': years, 'años_evaluados': selected,
              'cobertura': 'Observaciones documentadas; la ausencia de ediciones anteriores no acredita inaplicabilidad.'}
    if not selected or (period == 'ultimo_periodo' and len(selected) < 2):
        return {**result, 'motivo': 'Cobertura temporal insuficiente.'}
    if period == 'ultimo_periodo':
        if (len(selected) != 2 or selected[1] <= selected[0]
                or (ficha['id'] >= 17 and selected[1] != selected[0] + 1)):
            raise ValueError('El último periodo requiere dos ediciones ascendentes; los indicadores anuales requieren años consecutivos.')
        coverage = cobertura_periodo(section, selected)
        result.update(coverage)
        if coverage['cobertura_temporal_insuficiente']:
            return {**result, 'motivo': 'Faltan observaciones para evaluar el último periodo completo.'}
    if mappings and ficha['id'] == 3:
        return {**result, **calificar_temas_proteccion(section, period, mappings, selected)}
    if mappings and ficha['id'] == 10:
        return {**result, **calificar_temas_policiales(section, period, mappings, selected)}
    if mappings and ficha['id'] == 8:
        return {**result, **calificar_uniformes(section, mappings, selected)}
    if ficha['id'] == 15:
        return {**result, **calificar_llamadas(section, period, selected)}
    if ficha['id'] == 17:
        return {**result, **calificar_fallecimientos(section, selected)}
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
        priority = ficha.get('prioridad_cierre')
        if (priority and period == priority['periodo'] and len(values) == 2
                and values[-1] > values[-2]):
            first = Decimal(str(priority['peso_primera_edicion']))
            last = Decimal(str(priority['peso_ultima_edicion']))
            metrics['promedio'] = (first * values[-2] + last * values[-1]) / (first + last)
            result['prioridad_cierre_aplicada'] = {
                'anio_primero': selected[0], 'anio_ultimo': selected[1],
                'valor_primero': str(values[-2]), 'valor_ultimo': str(values[-1]),
                'peso_primero': str(first), 'peso_ultimo': str(last)}
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
    if results[2]['puntaje'] == 1 and not results[3].get('cobertura_temporal_insuficiente'):
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


def agregar(results, rules, sin_respuesta=(), *, modo='completo'):
    expected = set(range(1, 19))
    if set(results) != expected:
        raise ValueError('Se requieren exactamente los indicadores 1–18.')
    if modo not in ('completo', 'evaluables'):
        raise ValueError('Modo de agregación desconocido: use completo o evaluables.')
    sin_respuesta = tuple(sin_respuesta)
    partial_policy = rules.get('agregacion', {}).get('modos', {}).get('evaluables', {})
    minimums = partial_policy.get('minimos', {})
    pending = [key for key, value in results.items() if value['puntaje'] is None]
    scores = {key: value['puntaje'] for key, value in results.items() if value['puntaje'] is not None}
    if any(type(value) is not int or not 1 <= value <= 5 for value in scores.values()):
        raise ValueError('Puntajes inválidos.')
    if any(key not in scores or scores[key] != 1 for key in sin_respuesta):
        raise ValueError('Falta de respuesta sólo puede registrarse para indicadores con puntaje 1.')
    coverage = {
        name: {'evaluables': sum(i in scores for i in ids), 'total': len(ids),
               'minimo_requerido': minimums.get(name, (2 * len(ids) + 2) // 3),
               'indicadores_evaluables': [i for i in ids if i in scores],
               'indicadores_pendientes': [i for i in ids if i not in scores]}
        for name, ids in rules['dimensiones'].items()}
    if any(type(value['minimo_requerido']) is not int
           or not 1 <= value['minimo_requerido'] <= value['total'] for value in coverage.values()):
        raise ValueError('El mínimo de cobertura de cada dimensión debe ser un entero válido.')
    base = {'metodo': modo, 'alcance': 'indicadores_evaluables' if pending else 'completo',
            'indicadores_pendientes': pending,
            'cobertura': {'evaluables': len(scores), 'total': 18, 'por_dimension': coverage}}
    if pending:
        bounds = []
        for limit in (1, 5):
            completed = {key: {'puntaje': scores.get(key, limit)} for key in expected}
            bounds.append(agregar(completed, rules, sin_respuesta, modo='completo'))
        base['intervalo_completo'] = {
            'promedio_minimo': bounds[0]['promedio_tres_dimensiones'],
            'promedio_maximo': bounds[1]['promedio_tres_dimensiones'],
            'calificacion_minima': bounds[0]['calificacion_final'],
            'calificacion_maxima': bounds[1]['calificacion_final'],
            'interpretacion': 'Límites de sensibilidad si los pendientes recibieran 1 o 5; no son puntajes imputados.'}
        insufficient = [name for name, value in coverage.items()
                        if value['evaluables'] < value['minimo_requerido']]
        if modo == 'completo' or insufficient:
            return {**base, 'estado': 'pendiente', 'calificacion_final': None,
                    'dimensiones_con_cobertura_insuficiente': insufficient}
    dims = {name: sum(Decimal(scores[i]) for i in ids if i in scores) / coverage[name]['evaluables']
            for name, ids in rules['dimensiones'].items()}
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
    if pending:
        limit = partial_policy.get('tope_con_pendientes', 'MUY BIEN')
        if limit not in order[:-1]:
            raise ValueError('La evaluación parcial requiere un tope inferior a EXCELENTE.')
        if final > order.index(limit):
            cap('cobertura_parcial', order.index(limit))
    return {**base, 'estado': 'calculado_parcial' if pending else 'calculado',
            'promedios_dimension': {key: str(value) for key, value in dims.items()},
            'promedio_tres_dimensiones': str(mean), 'calificacion_preliminar': preliminary,
            'calificacion_final': order[final], 'candados_aplicados': applied,
            'redondeo': 'ROUND_HALF_UP a dos decimales sólo para clasificación; criterio operativo explícito.'}
