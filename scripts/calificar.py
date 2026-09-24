"""Cálculo determinista de criterios explícitos; nunca imputa datos faltantes."""
from decimal import Decimal, ROUND_HALF_UP
import operator
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


def calificar_indicador(section, ficha, period):
    tables = [table for table in section['tablas'] if table['ambito'] == 'municipal']
    rows = [row for table in tables for row in registros(table)]
    years = sorted({row['año'] for row in rows})
    selected = years[-2:] if period == 'ultimo_periodo' else years
    result = {'puntaje': None, 'años_observados': years, 'años_evaluados': selected,
              'cobertura': 'Observaciones documentadas; la ausencia de ediciones anteriores no acredita inaplicabilidad.'}
    if not selected or (period == 'ultimo_periodo' and len(selected) < 2):
        return {**result, 'motivo': 'Cobertura temporal insuficiente.'}
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
