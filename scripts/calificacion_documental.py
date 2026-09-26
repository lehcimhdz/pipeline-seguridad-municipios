"""Nota documental siempre definida, separada del desempeño no observado.

El piso no imputa datos: sólo limita cuánto se acredita con la evidencia
disponible. La sensibilidad es un escenario aritmético, no incertidumbre
estadística ni una predicción del desempeño faltante.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from calificar import agregar


POLITICA_DOCUMENTAL = {
    'version': '1.0',
    'piso_no_acreditado': 1,
    'techo_sensibilidad': 5,
    'pesos_dimension': {
        'proteccion_civil': 1,
        'condiciones_del_personal': 1,
        'inteligencia_y_eficiencia_policial': 1,
    },
    'escala_documental': [
        {'minimo': 4.5, 'calificacion': 'ACREDITACIÓN MUY ALTA'},
        {'minimo': 3.5, 'calificacion': 'ACREDITACIÓN ALTA'},
        {'minimo': 2.5, 'calificacion': 'ACREDITACIÓN PARCIAL'},
        {'minimo': 1.5, 'calificacion': 'ACREDITACIÓN BAJA'},
        {'minimo': 1, 'calificacion': 'NO ACREDITADO'},
    ],
    'candados': {
        'dimension_colapsada_minimo': 1.5,
        'excelente_dimension_minimo': 4,
        'muy_bien_dimension_minimo': 2.5,
        'falta_respuesta_umbral': 10,
    },
    'interpretacion': (
        'El puntaje asignado acredita evidencia contra criterios internos; no demuestra '
        'desempeño deficiente cuando falta evidencia. El puntaje observado permanece null. '
        'No es una acreditación oficial ni certificación legal.'),
    'sensibilidad': 'Rango de promedios antes de candados, con faltantes en 1 y 5; no es intervalo de confianza.',
}


def _decimal(value, name):
    if isinstance(value, bool):
        raise ValueError(f'Parámetro documental inválido: {name}.')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f'Parámetro documental inválido: {name}.') from error
    if not number.is_finite():
        raise ValueError(f'Parámetro documental no finito: {name}.')
    return number


def validar_politica(rules):
    """Rechaza configuración incompleta o pesos que excluyen evidencia."""
    policy = rules.get('calificacion_documental')
    if not isinstance(policy, dict) or not isinstance(policy.get('version'), str) or not policy['version']:
        raise ValueError('Falta la política de calificación documental versionada.')
    for name, expected in (('piso_no_acreditado', 1), ('techo_sensibilidad', 5)):
        if type(policy.get(name)) is not int or policy[name] != expected:
            raise ValueError(f'{name} debe conservar el extremo {expected} de la escala 1–5.')
    dimensions = rules.get('dimensiones', {})
    if not isinstance(dimensions, dict) or set(dimensions) != set(POLITICA_DOCUMENTAL['pesos_dimension']):
        raise ValueError('La política requiere las tres dimensiones de seguridad.')
    ids = [number for numbers in dimensions.values() for number in numbers]
    if any(type(number) is not int for number in ids) or sorted(ids) != list(range(1, 19)):
        raise ValueError('Las dimensiones deben distribuir exactamente los indicadores 1–18 una vez.')
    if any(not numbers for numbers in dimensions.values()):
        raise ValueError('Una dimensión no puede estar vacía.')
    weights = policy.get('pesos_dimension')
    if not isinstance(weights, dict) or set(weights) != set(dimensions):
        raise ValueError('Los pesos documentales deben cubrir las tres dimensiones.')
    for name, weight in weights.items():
        if _decimal(weight, name) <= 0:
            raise ValueError('Todos los pesos documentales deben ser positivos.')
    scale = policy.get('escala_documental')
    if not isinstance(scale, list) or len(scale) != 5:
        raise ValueError('La escala documental requiere cinco categorías.')
    thresholds, labels = [], []
    for item in scale:
        if not isinstance(item, dict) or not isinstance(item.get('calificacion'), str) or not item['calificacion'].strip():
            raise ValueError('Cada categoría documental debe tener nombre y mínimo.')
        thresholds.append(_decimal(item.get('minimo'), 'escala_documental.minimo'))
        labels.append(item['calificacion'])
    if (len(set(labels)) != 5 or thresholds != sorted(set(thresholds), reverse=True)
            or thresholds[-1] != 1 or thresholds[0] > 5):
        raise ValueError('Escala documental inválida: mínimos descendentes únicos entre 1 y 5.')
    limits = policy.get('candados')
    if not isinstance(limits, dict) or set(limits) != set(POLITICA_DOCUMENTAL['candados']):
        raise ValueError('Faltan los parámetros de los candados documentales.')
    for name in ('dimension_colapsada_minimo', 'excelente_dimension_minimo', 'muy_bien_dimension_minimo'):
        if not 1 <= _decimal(limits[name], name) <= 5:
            raise ValueError('Los mínimos de los candados deben estar entre 1 y 5.')
    if type(limits['falta_respuesta_umbral']) is not int or not 1 <= limits['falta_respuesta_umbral'] <= 18:
        raise ValueError('El umbral de falta de respuesta debe estar entre 1 y 18.')
    return policy


def _validar_resultados(results):
    if set(results) != set(range(1, 19)) or any(type(key) is not int for key in results):
        raise ValueError('Se requieren exactamente los indicadores 1–18.')
    for number, evaluation in results.items():
        if not isinstance(evaluation, dict) or 'puntaje' not in evaluation:
            raise ValueError(f'Falta el puntaje observado del indicador {number}.')
        observed = evaluation['puntaje']
        if observed is not None and (type(observed) is not int or not 1 <= observed <= 5):
            raise ValueError(f'Puntaje observado inválido del indicador {number}.')
        if observed is not None and evaluation.get('cobertura_temporal_insuficiente'):
            raise ValueError('No se admite puntaje observado con cobertura temporal insuficiente.')


def asignar_calificaciones(results, rules):
    """Anota los 18 resultados sin reemplazar null ni modificar evidencia."""
    policy = validar_politica(rules)
    _validar_resultados(results)
    for evaluation in results.values():
        observed = evaluation['puntaje']
        if observed is None:
            reason = evaluation.get('motivo') or 'No existe un criterio observado verificable.'
            evaluation.update(
                puntaje_asignado=policy['piso_no_acreditado'],
                base_calificacion='no_acreditado',
                motivo_asignacion=f'Piso documental de {policy["piso_no_acreditado"]}/5. {reason} '
                                  'No demuestra mal desempeño ni falta de respuesta municipal.',
            )
        else:
            evaluation.update(
                puntaje_asignado=observed,
                base_calificacion='observado',
                motivo_asignacion='Se conserva el puntaje observado: '
                                  + evaluation.get('criterio_aplicado', 'criterio de la ficha satisfecho') + '.',
            )
    return results


def _categoria(mean, scale):
    rounded = mean.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    for index, item in enumerate(scale):
        if rounded >= _decimal(item['minimo'], 'mínimo'):
            return index
    raise ValueError('Promedio documental fuera de escala.')


def agregar_documental(results, rules, sin_respuesta=()):
    """Agrega notas asignadas y publica cobertura/rango sin ocultar faltantes."""
    policy = validar_politica(rules)
    expected = asignar_calificaciones(deepcopy(results), rules)
    for number, evaluation in results.items():
        if type(evaluation.get('puntaje_asignado')) is not int or not 1 <= evaluation['puntaje_asignado'] <= 5:
            raise ValueError(f'Asignación documental inconsistente: indicador {number}, puntaje_asignado debe ser integer 1–5.')
        for key in ('puntaje_asignado', 'base_calificacion', 'motivo_asignacion'):
            if evaluation.get(key) != expected[number][key]:
                raise ValueError(f'Asignación documental inconsistente: indicador {number}, {key}.')
    pending = sorted(number for number, evaluation in results.items() if evaluation['puntaje'] is None)
    scores = {number: Decimal(evaluation['puntaje_asignado']) for number, evaluation in results.items()}
    dimensions = rules['dimensiones']
    weights = {name: _decimal(weight, name) for name, weight in policy['pesos_dimension'].items()}
    total_weight = sum(weights.values())
    means = {name: sum(scores[number] for number in ids) / len(ids) for name, ids in dimensions.items()}
    mean = sum(means[name] * weight for name, weight in weights.items()) / total_weight
    maximum_means = {
        name: sum(Decimal(policy['techo_sensibilidad']) if number in pending else scores[number]
                  for number in ids) / len(ids) for name, ids in dimensions.items()
    }
    maximum = sum(maximum_means[name] * weight for name, weight in weights.items()) / total_weight
    known_fraction = sum(weights[name] * Decimal(sum(number not in pending for number in ids)) / len(ids)
                         for name, ids in dimensions.items()) / total_weight
    scale = policy['escala_documental']
    preliminary = _categoria(mean, scale)
    final, applied = preliminary, []
    limits = policy['candados']

    def cap(rule, index):
        nonlocal final
        previous = final
        final = max(final, index)
        applied.append({'regla_id': rule, 'modifica_calificacion': final != previous})

    if min(means.values()) < _decimal(limits['dimension_colapsada_minimo'], 'dimension_colapsada_minimo'):
        cap(1, 2)
    if final == 0 and (min(means.values()) < _decimal(limits['excelente_dimension_minimo'], 'excelente_dimension_minimo')
                       or min(scores.values()) == 1):
        cap(2, 1)
    if final == 1 and min(means.values()) < _decimal(limits['muy_bien_dimension_minimo'], 'muy_bien_dimension_minimo'):
        cap(3, 2)
    nonresponse = set(sin_respuesta)
    if any(type(number) is not int or number not in results or results[number]['puntaje'] != 1 for number in nonresponse):
        raise ValueError('La falta de respuesta explícita requiere puntaje observado 1; un faltante no basta.')
    if len(nonresponse) >= limits['falta_respuesta_umbral']:
        cap(4, 4)
    return {
        'estado': 'calculado',
        'metodologia_version': policy['version'],
        'tipo_calificacion': 'documental',
        'promedios_dimension': {name: str(value) for name, value in means.items()},
        'promedio_tres_dimensiones': str(mean),
        'calificacion_preliminar': scale[preliminary]['calificacion'],
        'calificacion_final': scale[final]['calificacion'],
        'candados_aplicados': applied,
        'categoria_desempeno': agregar(results, rules, nonresponse)['calificacion_final'] if not pending else None,
        'cobertura': {'observados': 18 - len(pending), 'asignados': 18, 'total': 18,
                      'no_acreditados': len(pending),
                      'porcentaje': str(Decimal(18 - len(pending)) / 18 * 100),
                      'ponderada_porcentaje': str(known_fraction * 100)},
        'sensibilidad': {'minimo': str(mean), 'maximo': str(maximum)},
        'indicadores_pendientes': pending,
        'redondeo': 'ROUND_HALF_UP a dos decimales sólo para clasificación; precisión interna conservada.',
    }
