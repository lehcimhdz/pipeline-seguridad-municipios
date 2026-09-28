"""Lecturas indicativas reproducibles: nunca imputan puntajes ni cobertura.

Las reglas generales homologan lo que aparece en las tablas municipales. No
convierten un encabezado ambiguo en un universo verificado, ni rellenan vacíos.
"""
from decimal import Decimal
import re

from calificar import coincide, filas_por_año, normalizar, numero, tema_sin_informacion
from evidencia_complementaria import tasas_comparables


def _numero(value):
    result = numero(str(value))
    return result if result is not None and result >= 0 else None


def _celda(row, column, scope='municipal'):
    return {'ambito': scope, 'anio': row['año'], 'tabla': row['tabla'],
            'fila': row['fila'], 'columna': column, 'valor': row['celdas'][column]}


def _conteo(section, year, column='Total', scope='municipal'):
    rows = [r for r in filas_por_año(section, scope).get(year, []) if column in r['celdas']]
    if len(rows) != 1:
        return None, []
    return _numero(rows[0]['celdas'][column]), [_celda(rows[0], column, scope)]


def _observacion(e, year, fields):
    """Conserva el origen declarado; una inferencia no recibe sello de revisión."""
    return [{'anio': year, 'campo': field, 'valor': e[field],
             **{k: e[k] for k in ('fuente', 'localizador', 'revision',
                                 'trazabilidad', '_trazabilidad') if k in e}}
            for field in fields if field in e]


def _profesionalizacion(topic):
    text = normalizar(topic)
    return bool(re.match(r'^(?:profesionalizacion|formacion inicial|actualizacion|'
                         r'especializacion|alta direccion)(?:\b|\s)', text))


def _presencia(row):
    """Devuelve presencia positiva sin sumar asistentes ni aceptar contradicciones."""
    cells = row['celdas']
    parsed = [numero(str(cells[key])) for key in ('Total', 'Porcentaje') if key in cells]
    if any(v is not None and v < 0 for v in parsed):
        return False, 'Total o porcentaje negativo.', None
    values = {key: _numero(cells[key]) for key in ('Total', 'Porcentaje') if key in cells}
    if values.get('Porcentaje') is not None and values['Porcentaje'] > 100:
        return False, 'Porcentaje fuera de rango.', None
    observed = [v for v in values.values() if v is not None]
    total, percentage = values.get('Total'), values.get('Porcentaje')
    if total == 0 and percentage is not None and percentage > 0:
        return False, 'Total cero y porcentaje positivo contradicen la presencia del tema.', None
    if total is not None and total > 0 and percentage == 0:
        return True, None, ('El conteo positivo acredita participación aunque el porcentaje se muestre '
                            'como cero; podría obedecer a redondeo, pero la fuente no lo confirma.')
    return any(v > 0 for v in observed), None, None


def _capacitacion(section, years, obs, mappings, result):
    if not years:
        return
    year = years[-1]
    result['anio_referencia'] = year
    groups = mappings.get('capacitacion_policial_nucleo', {})
    found, unknown, excluded, positive_topics = set(), set(), set(), set()
    conflicts, cautions = [], []
    for row in filas_por_año(section).get(year, []):
        topic = row['celdas'].get('Tema', '')
        if 'Tema' in row['celdas']:
            result['evidencias'].append(_celda(row, 'Tema'))
        for key in ('Total', 'Porcentaje'):
            if key in row['celdas']:
                result['evidencias'].append(_celda(row, key))
        positive, conflict, caution = _presencia(row)
        if conflict:
            conflicts.append({'tabla': row['tabla'], 'fila': row['fila'], 'motivo': conflict})
            continue
        if caution:
            cautions.append({'tabla': row['tabla'], 'fila': row['fila'], 'motivo': caution})
        if _profesionalizacion(topic):
            excluded.add(topic)
            continue
        if not positive:
            continue
        positive_topics.add(topic)
        matched = {group for group, patterns in groups.items()
                   if not tema_sin_informacion(topic) and coincide(topic, patterns)}
        found.update(matched)
        if not matched:
            unknown.add(topic)
    result.update(grupos_acreditados=sorted(found), temas_no_homologados=sorted(unknown),
                  profesionalizacion_excluida=sorted(excluded), conflictos=conflicts,
                  advertencias=cautions)
    result['base'] = [f'{year}: {len(found)} grupos núcleo con participación positiva.'] if positive_topics else []
    result['condiciones'].append('La lectura corresponde a la edición reciente; no suma asistentes '
                                'por tema ni estima la proporción de personas únicas capacitadas.')
    if conflicts:
        result['condiciones'].append('Las filas con contradicciones entre total y porcentaje no acreditan temas.')
    if cautions:
        result['condiciones'].append('En filas con conteo positivo y porcentaje cero se conserva la '
                                    'presencia del tema por el conteo. El porcentaje podría estar '
                                    'redondeado; no se afirma esa causa ni se reconstruye una cobertura.')
    if found:
        result.update(nivel_indicativo=3 if len(found) >= 2 else 2, confianza='baja')
        if unknown:
            result['condiciones'].append('Los grupos acreditados son un mínimo observable; los temas '
                                        'sin homologar no se cuentan como ausencia de otros grupos.')
    else:
        e = obs.get(str(year), {})
        if (e.get('revision') == 'verificada' and e.get('ausencia_temas_nucleo_acreditada') is True
                and not positive_topics and not conflicts):
            result.update(nivel_indicativo=1, confianza='baja')
            result['evidencias'].extend(_observacion(e, year, ['ausencia_temas_nucleo_acreditada']))
            result['base'] = [f'{year}: ausencia de temas núcleo acreditada expresamente.']


def _proteccion_civil(section, years, obs, definitions, result):
    groups = definitions.get('normalizacion_proteccion_civil', {}).get('grupos', {})
    per_year, ratios = [], []
    for year in years:
        found, unknown = set(), []
        for row in filas_por_año(section).get(year, []):
            topic = row['celdas'].get('Tema impartido', '')
            if 'Tema impartido' in row['celdas']:
                result['evidencias'].append(_celda(row, 'Tema impartido'))
            matched = {group for group, aliases in groups.items()
                       if not tema_sin_informacion(topic)
                       and any(normalizar(alias) in normalizar(topic) for alias in aliases)}
            found.update(matched)
            if not matched:
                unknown.append(topic)
        e = obs.get(str(year), {})
        captured = e.get('grupos_captados', [])
        catalog_valid = (e.get('catalogo_completo') is True and bool(captured)
                         and len(captured) == len(set(captured)) and set(captured) <= set(groups))
        # Una lista de temas impartidos no es el catálogo completo del cuestionario.
        if catalog_valid and not unknown and (found or e.get('ausencia_temas_acreditada') is True):
            ratios.append(Decimal(len(found & set(captured))) / len(captured))
            result['evidencias'].extend(_observacion(e, year, ['grupos_captados', 'catalogo_completo']))
        per_year.append({'anio': year, 'grupos_acreditados': sorted(found),
                         'temas_no_homologados': unknown,
                         'grupos_captados': captured if catalog_valid else None})
    result['grupos_por_anio'] = per_year
    result['base'] = [f'{item["anio"]}: {len(item["grupos_acreditados"])} grupos núcleo identificados.'
                      for item in per_year if item['grupos_acreditados']]
    if years and len(ratios) == len(years):
        average = sum(ratios) / len(ratios)
        risk = all('identificacion_y_analisis_de_riesgos' in p['grupos_acreditados'] for p in per_year)
        level = (5 if average >= Decimal('.8') and risk else 4 if average >= Decimal(2) / 3
                 else 3 if average >= Decimal(1) / 3 else 2 if average > 0 else 1)
        result.update(nivel_indicativo=level, confianza='baja')
    else:
        result['condiciones'].append('Los temas impartidos no permiten reconstruir por sí solos el '
                                    'catálogo captado en cada edición; no se inventa ese denominador.')


def _equipamiento(section, years, obs, result):
    for year in years:
        for row in filas_por_año(section).get(year, []):
            item = row['celdas'].get('Equipamiento')
            count = _numero(row['celdas'].get('Total'))
            if item and count is not None:
                result['base'].append(f'{year}: {count} unidades reportadas de {item}.')
                result['evidencias'].extend(_celda(row, key) for key in ('Equipamiento', 'Total'))
    ratios = []
    for year in years:
        e = obs.get(str(year), {})
        if e.get('_conflictos'):
            result['condiciones'].append('Hay datos de equipamiento o universo pendientes de conciliación.')
            return
        staff = _numero(e.get('personal_policial'))
        vest = _numero(e.get('chalecos'))
        nature = e.get('naturaleza_del_dato')
        result['evidencias'].extend(_observacion(e, year, ['personal_policial', 'chalecos', 'naturaleza_del_dato']))
        if staff in (None, 0) or vest is None or nature not in ('inventario_al_cierre', 'asignado_al_cierre'):
            result['condiciones'].append('Se necesitan personal policial y chalecos comparables, '
                                        'con distinción entre inventario y equipo asignado.')
            return
        ratio = vest / staff
        ratios.append(ratio)
        result['base'].append(f'{year}: {ratio} chalecos por policía ({nature}).')
        # Si ambas lecturas se documentaron, no se elige sólo la más favorable.
        for key in ('chalecos_inventario', 'chalecos_asignados'):
            if key in e:
                value = _numero(e[key])
                result['evidencias'].extend(_observacion(e, year, [key]))
                if value is None:
                    return
                ratios.append(value / staff)
    if ratios and all(v >= 1 for v in ratios):
        result.update(nivel_indicativo=4, confianza='baja')
    elif ratios and all(v < Decimal('.5') for v in ratios):
        result.update(nivel_indicativo=2, confianza='baja')
    result['condiciones'].append('La razón describe existencias o asignación según la fuente; '
                                'no acredita funcionamiento, distribución por turno ni protección efectiva.')


def _camaras(section, years, obs, result):
    counts = []
    for year in years:
        value, evidence = _conteo(section, year)
        result['evidencias'].extend(evidence)
        counts.append(value)
        if value is not None:
            result['base'].append(f'{year}: {value} cámaras reportadas.')
    if counts and all(v is not None for v in counts):
        if all(v > 0 for v in counts) and all(a <= b for a, b in zip(counts, counts[1:])):
            result.update(nivel_indicativo=3, confianza='baja')
        elif any(v == 0 for v in counts) and any(v > 0 for v in counts):
            result.update(nivel_indicativo=2, confianza='baja')
    if years and all(obs.get(str(y), {}).get('universo') == 'camaras_en_servicio' for y in years):
        result['condiciones'].append('La evidencia identifica cámaras en servicio; comparar la cobertura '
                                    'municipal y estatal por habitante requiere poblaciones compatibles.')
    else:
        result['condiciones'].append('La continuidad del conteo no acredita cámaras en servicio ni '
                                    'cobertura equivalente a la estatal.')


def _llamadas(section, years, obs, result):
    recent = years[-2:]
    counts = []
    for year in recent:
        value, evidence = _conteo(section, year, 'Llamadas procedentes')
        counts.append(value)
        result['evidencias'].extend(evidence)
        if value is not None:
            result['base'].append(f'{year}: {value} llamadas procedentes registradas para el municipio.')
    result['anios_referencia'] = recent
    if (len(recent) == 2 and all(v is not None for v in counts)
            and not any(obs.get(str(y), {}).get('registro_municipal') is False
                        or obs.get(str(y), {}).get('ausencia_registro_acreditada') is True for y in recent)):
        result.update(nivel_indicativo=3, confianza='baja')
    result['condiciones'].append('La presencia de cifras para el municipio permite una lectura '
                                'condicionada de continuidad. No identifica al operador del servicio '
                                'ni acredita competencia municipal, tiempos de respuesta o resolución.')


def _remisiones(section, years, obs, data, result):
    ratios = []
    for year in years:
        e = obs.get(str(year), {})
        def persons(scope):
            rows = filas_por_año(section, scope).get(year, [])
            columns = {key for row in rows for key in row['celdas']
                       if key in ('Total', 'Total de personas')}
            return _conteo(section, year, next(iter(columns)), scope) if len(columns) == 1 else (None, [])
        local, evidence = persons('municipal')
        state, state_evidence = persons('estatal')
        result['evidencias'].extend(evidence + state_evidence)
        if local is not None:
            result['base'].append(f'{year}: {local} personas reportadas; no se presume su destino.')
        if local is None or state is None or e.get('remisiones_comparables') is not True or e.get('_conflictos'):
            continue
        result['evidencias'].extend(_observacion(e, year, ['remisiones_comparables', 'universo_remisiones']))
        # MP y justicia cívica nunca se equiparan por compartir el rótulo Total.
        if e.get('universo_remisiones') not in ('ministerio_publico', 'justicia_civica', 'personas_remitidas_mismo_universo'):
            continue
        pair = tasas_comparables(data, year, local, state)
        if pair is None or pair[1] == 0:
            continue
        ratios.append(pair[0] / pair[1])
        result['evidencias'].extend({'tipo': 'poblacion', **p} for p in data.get('poblacion', []) if p['anio'] == year)
    if years and len(ratios) == len(years) and all(Decimal('.75') <= v <= Decimal('1.25') for v in ratios):
        result.update(nivel_indicativo=3, confianza='media')
    result['condiciones'].append('La comparación poblacional sólo es indicativa y requiere el mismo '
                                'tipo de personas y destino en ambos ámbitos. No sustituye la '
                                'incidencia delictiva ni acredita respeto o violación de derechos.')


def provisional(number, section, years, obs, motivo, definitions, mappings=None, data=None):
    """Devuelve lectura separada del puntaje; no modifica ninguno de sus argumentos."""
    years = sorted(set(years))
    result = {'nivel_indicativo': None, 'base': [], 'confianza': 'no_estimable',
              'falta': motivo, 'computa_en_agregacion': False, 'evidencias': [],
              'condiciones': [],
              'regla': definitions.get('interpretacion_provisional', {}).get('reglas_por_ficha', {}).get(
                  str(number), 'Describir la información disponible sin asignar un nivel no acreditado.')}
    if number == 3:
        _proteccion_civil(section, years, obs, definitions, result)
    elif number == 4:
        for year in years:
            value, evidence = _conteo(section, year)
            result['evidencias'].extend(evidence)
            if value is not None:
                result['base'].append(f'{year}: {value} personas reportadas en la plantilla total.')
        result['condiciones'].append('El tamaño de la plantilla no se transforma en desempeño sin '
                                    'población y personal policial acreditados.')
    elif number == 9:
        _equipamiento(section, years, obs, result)
    elif number == 10:
        _capacitacion(section, years, obs, mappings or {}, result)
    elif number == 14:
        _camaras(section, years, obs, result)
    elif number == 15:
        _llamadas(section, years, obs, result)
    elif number == 18:
        _remisiones(section, years, obs, data or {}, result)
    return result
