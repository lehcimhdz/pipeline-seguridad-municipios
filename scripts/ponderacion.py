"""Agregación 2.3: pesos explícitos, cobertura y candados; sin imputación."""
from decimal import Decimal
from calificar import categoria

ORDER = ['CATASTRÓFICO', 'MAL', 'REGULAR', 'MUY BIEN', 'EXCELENTE']


def agregar_ponderado(results, rules, *, modo='completo', esquema=None, sensibilidad=True):
    policy = rules['ponderacion_config']
    config = policy['ponderacion']
    scheme = esquema or config['esquema_predeterminado']
    if scheme not in config['esquemas'] or modo not in ('completo', 'evaluables', 'disponibles'):
        raise ValueError('Esquema o modo de agregación inválido.')
    if set(results) != set(range(1, 19)):
        raise ValueError('Se requieren los 18 indicadores.')
    weights = {int(k): Decimal(str(v)) for k, v in config['pesos'].items()}
    if scheme == 'dimensiones_iguales':
        weights = {i: Decimal(1) for i in weights}
    if set(weights) != set(results) or any(w <= 0 for w in weights.values()):
        raise ValueError('Pesos inválidos.')
    priorities = config['prioritarios']
    if len(priorities) != len(set(priorities)) or not set(priorities) <= set(results):
        raise ValueError('Prioritarios inválidos.')
    scores = {i: r['puntaje'] for i, r in results.items() if r['puntaje'] is not None}
    if any(type(s) is not int or not 1 <= s <= 5 for s in scores.values()):
        raise ValueError('Puntajes inválidos.')
    pending = [i for i in results if i not in scores]
    not_applicable = [i for i in pending if results[i].get('estado_dato') == 'no_aplicable']
    priority_count = sum(i in scores for i in priorities)
    coverage_policy = policy['agregacion']['disponibles' if modo == 'disponibles' else 'evaluables']
    minimums = coverage_policy['cobertura_minima_por_dimension']
    coverage = {d: {'evaluables': sum(i in scores for i in ids), 'total': len(ids),
                    'minimo_requerido': minimums[d]} for d, ids in rules['dimensiones'].items()}
    output = {'metodo': modo, 'esquema': scheme, 'alcance': 'indicadores_evaluables' if pending else 'completo',
              'indicadores_pendientes': pending, 'indicadores_no_aplicables': not_applicable,
              'cobertura': {'evaluables': len(scores), 'total': 18, 'por_dimension': coverage,
                            'prioritarios_evaluables': priority_count, 'prioritarios_total': len(priorities)},
              'estado': 'pendiente', 'calificacion_final': None}
    if pending and sensibilidad and not not_applicable:
        bounds = []
        for value in (1, 5):
            scenario = {i: {**r, 'puntaje': scores.get(i, value)} for i, r in results.items()}
            bounds.append(agregar_ponderado(scenario, rules, modo='completo', esquema=scheme, sensibilidad=False))
        output['intervalo_completo'] = {'promedio_minimo': bounds[0]['promedio_tres_dimensiones'],
            'promedio_maximo': bounds[1]['promedio_tres_dimensiones'],
            'calificacion_minima': bounds[0]['calificacion_final'], 'calificacion_maxima': bounds[1]['calificacion_final'],
            'interpretacion': 'Escenarios extremos; no sustituyen los puntajes desconocidos.'}
        levels = {i: results[i].get('valoracion_provisional', {}).get('nivel_indicativo') for i in pending}
        if all(type(v) is int and 1 <= v <= 5 for v in levels.values()):
            scenario = {i: {**r, 'puntaje': scores[i] if i in scores else levels[i]} for i, r in results.items()}
            middle = agregar_ponderado(scenario, rules, modo='completo', esquema=scheme, sensibilidad=False)
            output['escenario_intermedio'] = {'promedio': middle['promedio_tres_dimensiones'],
                'calificacion': middle['calificacion_final'], 'es_observado': False, 'reduce_intervalo': False}
    insufficient = [d for d, c in coverage.items() if c['evaluables'] < c['minimo_requerido']]
    if (not_applicable or (pending and modo == 'completo') or insufficient
            or priority_count < coverage_policy['cobertura_prioritaria_minima']):
        output['motivo'] = 'Cobertura insuficiente o universo no comparable para la valoración seleccionada.'
        output['dimensiones_con_cobertura_insuficiente'] = insufficient
        return output
    dims = {d: sum(weights[i] * scores[i] for i in ids if i in scores) /
               sum(weights[i] for i in ids if i in scores) for d, ids in rules['dimensiones'].items()}
    if scheme == 'global':
        dw = {d: sum(weights[i] for i in ids if i in scores) / sum(weights[i] for i in scores)
              for d, ids in rules['dimensiones'].items()}
    elif scheme == 'dimensiones_iguales':
        dw = {d: Decimal(1) / 3 for d in dims}
    else:
        dw = {d: Decimal(str(w)) for d, w in config['esquemas'][scheme]['peso_dimension'].items()}
        if set(dw) != set(dims) or sum(dw.values()) != 1 or any(w <= 0 for w in dw.values()):
            raise ValueError('Los pesos de dimensión deben ser positivos y sumar uno.')
    mean = (sum(weights[i] * scores[i] for i in scores) / sum(weights[i] for i in scores)
            if scheme == 'global' else sum(dw[d] * dims[d] for d in dims))
    effective = {str(i): str(dw[d] * weights[i] / sum(weights[j] for j in ids if j in scores))
                 for d, ids in rules['dimensiones'].items() for i in ids if i in scores}
    preliminary = categoria(mean, rules)
    final = ORDER.index(preliminary)
    caps = []
    def cap(identifier, maximum):
        nonlocal final
        new = min(final, maximum)
        caps.append({'regla_id': identifier, 'modifica_calificacion': new != final})
        final = new
    if min(dims.values()) < Decimal('1.5'): cap(1, 2)
    if final == 4 and (min(dims.values()) < 4 or min(scores.values()) == 1): cap(2, 3)
    if final == 3 and min(dims.values()) < Decimal('2.5'): cap(3, 2)
    unresponsive = [i for i, r in results.items() if r.get('sin_respuesta_municipal') is True and scores.get(i) == 1]
    if len(unresponsive) >= 10: cap(4, 0)
    if final == 4 and (priority_count != len(priorities) or any(scores.get(i, 0) < 4 for i in priorities)): cap(7, 3)
    priority_mean = sum(weights[i] * scores[i] for i in priorities if i in scores) / sum(weights[i] for i in priorities if i in scores)
    if final >= 3 and (priority_mean < 3 or any(scores.get(i) == 1 for i in priorities)): cap(8, 2)
    if len(set(unresponsive) & set(priorities)) >= 4: cap(9, 1)
    if pending and final == 4: cap('cobertura_parcial', 3)
    output.update(estado=('calculado_disponibles' if modo == 'disponibles' and pending
                          else 'calculado_parcial' if pending else 'calculado'),
                  promedios_dimension={d: str(v) for d, v in dims.items()},
                  promedio_tres_dimensiones=str(mean), promedio_prioritarios=str(priority_mean),
                  calificacion_preliminar=preliminary, calificacion_final=ORDER[final],
                  pesos_efectivos=effective, candados_aplicados=caps)
    if modo == 'disponibles' and pending:
        output['advertencia_cobertura'] = ('Categoría calculada sólo con indicadores acreditados; '
                                          'puede cambiar al resolver los pendientes.')
    return output
