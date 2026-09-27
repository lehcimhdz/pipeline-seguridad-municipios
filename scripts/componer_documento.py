"""Compone la medición consultiva; cálculos y trazabilidad permanecen separados."""
from decimal import Decimal, ROUND_HALF_UP

from analisis_evidencia import analizar_indicador
from documentos import registros
from redaccion_consultoria import (PERIODOS, bibliografia_documental, enumerar,
                                  fuente_grafica, notas_alcance, periodo_texto,
                                  texto_pendiente, titulo_tabla, validar_publicacion)

REVISION_EDITORIAL = 'REVISION_EDITORIAL_WORD'


def puntaje(value):
    return 'Pendiente' if value is None else str(value)


def decimal_corto(value):
    return str(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _resumen(analyses, numbers, reciente=False):
    key = 'hallazgo_reciente' if reciente else 'hallazgo_municipal'
    return ' '.join(analyses[number][key] for number in numbers
                    if number in analyses and analyses[number][key])


def componer(result, dictionary, rules):
    values = result['valores_plantilla']
    sections = result['indicadores']
    municipality, state = result['municipio'], result.get('estado') or 'la entidad'
    for key in list(values):
        if key == 'tabla_calificaciones' or key.startswith(('tablas_municipales_', 'tablas_estatales_')):
            del values[key]
    analyses = {section['numero']: analizar_indicador(section, municipality, state,
                                                    result.get('periodos_evaluacion'))
                for section in sections}
    for section in sections:
        number = section['numero']
        analysis = analyses[number]
        values[f'analisis_indicador_{number:02d}'] = '\n\n'.join(analysis['parrafos'])
        values[f'cierre_indicador_{number:02d}'] = analysis['cierre']
        values[f'tablas_indicador_{number:02d}'] = [
            {'titulo': titulo_tabla(table), 'ambito': table['ambito'],
             'tabla_fuente': table['tabla'], 'filas': table['filas']}
            for table in section['tablas']]
        scores = [section['evaluaciones'][period]['puntaje'] for period in PERIODOS]
        values[f'graficas_indicador_{number:02d}'] = ([{
            'tipo': 'puntajes', 'titulo': f"Valoración: {section['nombre']}",
            'categorias': list(PERIODOS.values()), 'valores': scores,
            'fuente': fuente_grafica(section),
        }] if any(score is not None for score in scores) else [])
    years = [value for value in (values.get('año_inicial'), values.get('año_final')) if value is not None]
    if not years:
        years = sorted({row['año'] for section in sections for table in section['tablas']
                        if table.get('ambito') == 'municipal' for row in registros(table)})
    period_label = periodo_texto(years)
    values['introduccion_seguridad'] = (
        f'Esta medición examina las capacidades de seguridad de {municipality}, {state}, durante {period_label}, '
        'para identificar avances, problemas que requieren atención y prioridades de gestión. '
        'Los dieciocho indicadores abarcan protección civil, condiciones del personal e información y eficiencia policial.\n\n'
        f'El análisis utiliza el Paquete Seguridad y el Anexo de {municipality}. Presenta la evolución municipal '
        f'y la información de {state} como contexto, distinguiendo los conteos, los porcentajes y la existencia de capacidades. '
        'Las recomendaciones se apoyan en esos hallazgos; no suponen causas, suficiencia operativa ni resultados sobre el delito que los documentos no permiten establecer.')
    historic = [_resumen(analyses, group) for group in ((1, 2), (4, 7), (14, 15))]
    values['resumen_general'] = '\n\n'.join(part for part in historic if part) or (
        f'La información de {municipality} requiere ampliarse para identificar cambios en sus capacidades de seguridad.')
    recent_years = sorted({year for section in sections
                           for year in section['evaluaciones']['ultimo_periodo'].get('años_evaluados', [])})
    missing_years = sorted({year for section in sections
                            for year in section['evaluaciones']['ultimo_periodo'].get('años_faltantes', [])})
    if missing_years:
        recent_intro = (f'La valoración de {periodo_texto(recent_years)} está incompleta por falta de información '
                        f'de {enumerar(missing_years)} en varios indicadores. Los hallazgos disponibles describen '
                        'los años que se indican a continuación y no cubren por sí solos todo el periodo reciente.')
    else:
        recent_intro = (f'Para valorar la situación reciente de {municipality}, las últimas observaciones disponibles '
                        'permiten identificar las siguientes prioridades, respetando la cobertura temporal de cada indicador.')
    values['resumen_ultimo_periodo'] = recent_intro + '\n\n' + _resumen(analyses, (5, 10, 16), reciente=True)
    conclusions = []
    for numbers, recommendation in (
        ((1, 2), 'La prioridad en protección civil es dar continuidad a la planeación y comprobar que la capacitación se traduzca en capacidad de respuesta ante los riesgos locales.'),
        ((4, 7), 'En la gestión del personal conviene revisar la estabilidad de la fuerza, sostener la certificación y vincular la formación con las necesidades de los turnos y las funciones operativas.'),
        ((15, 18), 'La actividad policial debe acompañarse de seguimiento a la atención ciudadana y a la resolución de los procedimientos. Estas decisiones requieren revisar calidad y resultados, además del volumen de actividad.'),
    ):
        findings = _resumen(analyses, numbers, reciente=True)
        conclusions.append((findings + ' ' if findings else '') + recommendation)
    values['conclusiones_seguridad'] = '\n\n'.join(conclusions)
    values['bibliografia'] = '\n\n'.join(bibliografia_documental(result))
    grades = {period: result['calculos'][period]['calificacion_final'] or 'PENDIENTE' for period in PERIODOS}
    values.update(calificacion_general=grades['general'], calificacion_ultimo_periodo=grades['ultimo_periodo'])
    dimensions = {period: {} for period in PERIODOS}
    for period in PERIODOS:
        for name, ids in rules['dimensiones'].items():
            scores = [section['evaluaciones'][period]['puntaje'] for section in sections if section['numero'] in ids]
            dimensions[period][name] = (None if not scores or any(score is None for score in scores)
                                        else decimal_corto(sum(Decimal(str(score)) for score in scores) / len(scores)))
    active = [key for key, definition in dictionary['variables_documento'].items()
              if definition.get('apariciones_por_documento', {}).get('medicion', 1)
              and key != 'tabla_calificaciones'
              and not key.startswith(('tablas_municipales_', 'tablas_estatales_'))]
    active_set = set(active)
    for key in list(values):
        if key not in active_set:
            del values[key]
    result['version'] = '2.1'
    result['contenido_word'] = {
        'version': '2.1', 'perfil': 'seguridad_medicion_v2',
        'titulo': f'Medición de seguridad de {municipality}, {state} ({period_label})',
        'aviso_borrador': 'Versión de trabajo para revisión de hallazgos y recomendaciones.',
        'periodo': f'Periodo de observaciones: {period_label}. La cobertura varía entre indicadores.',
        'calificaciones': grades, 'promedios_dimension': dimensions,
        'promedios_generales': {p: result['calculos'][p].get('promedio_tres_dimensiones') for p in PERIODOS},
        'hoja_computo': [{'indicador': section['numero'],
                         **{p: puntaje(section['evaluaciones'][p]['puntaje']) for p in PERIODOS}}
                        for section in sections],
        'analisis': [{'indicador': number, 'variable': f'analisis_indicador_{number:02d}',
                     'cierre': analysis['cierre'], 'evidencia': analysis['evidencia'],
                     'limite_periodo_reciente': analysis['limite_periodo_reciente']}
                    for number, analysis in analyses.items()],
        'variables_activas': active, 'variables_no_aplicables': [],
        'decision_editorial': 'Medición de seguridad: dieciocho indicadores, dos fuentes municipales y redacción consultiva. Los puntajes pendientes permanecen sin asignación.',
    }
    result['validaciones'] = [item for item in result.get('validaciones', [])
                             if item['codigo'] not in ('VARIABLES_PENDIENTES', 'COMPOSICION_WORD_PENDIENTE', 'VARIABLES_ACTIVAS_PENDIENTES')]
    missing = [key for key in active if values.get(key) is None or values.get(key) == '']
    if missing:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'VARIABLES_ACTIVAS_PENDIENTES', 'variables': missing})
    if not any(item['codigo'] == REVISION_EDITORIAL for item in result['validaciones']):
        result['validaciones'].append({'nivel': 'revision', 'codigo': REVISION_EDITORIAL,
                                      'detalle': 'Revisar hallazgos, comparaciones, cobertura temporal y recomendaciones antes de aprobar la medición.'})
    result['contenido_word']['notas_alcance'] = notas_alcance(result)
    result['contenido_word']['textos_pendientes'] = {key: texto_pendiente(key) for key in missing}
    result['contenido_word']['control_redaccion'] = validar_publicacion(result)
    return result
