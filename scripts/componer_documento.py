"""Contenido editorial reproducible a partir de resultados y evidencia del JSON."""
from decimal import Decimal, ROUND_HALF_UP

PERIODOS = {'general': 'Periodo general', 'ultimo_periodo': 'Último periodo'}
REVISION_EDITORIAL = 'REVISION_EDITORIAL_WORD'


def puntaje(value):
    return 'Pendiente' if value is None else str(value)


def decimal_corto(value):
    return str(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def componer(result, dictionary, rules):
    """Completa sólo prosa sustentada; conserva null en variantes descartadas.

    La composición no decide causas, vigencia jurídica ni revisiones humanas.
    Cada análisis remite a las tablas municipales/estatales originales.
    """
    values = result['valores_plantilla']
    sections = result['indicadores']
    title = f"Diagnóstico de seguridad municipal — {result['municipio']}, {result.get('estado') or 'entidad pendiente'}"
    analyses = []
    for section in sections:
        number = section['numero']
        paragraphs = []
        for period, label in PERIODOS.items():
            evaluation = section['evaluaciones'][period]
            years = ', '.join(map(str, evaluation.get('años_evaluados', []))) or 'sin cobertura confirmada'
            if evaluation['puntaje'] is None:
                sentence = f"{label} ({years}): calificación pendiente. {evaluation.get('motivo', 'Requiere revisión de evidencia.')}"
            else:
                sentence = f"{label} ({years}): {evaluation['puntaje']}/5. Criterio aplicado: {evaluation['criterio_aplicado']}."
            if evaluation.get('nota'):
                sentence += ' ' + evaluation['nota']
            paragraphs.append(sentence)
        refs = [f"tabla {table['tabla']} ({table['ambito']})" for table in section['tablas']]
        paragraphs.append('Evidencia: PAQUETE SEGURIDAD, ' + '; '.join(refs) + '. Las tablas siguientes conservan los valores reportados; una celda vacía representa un dato pendiente de clasificar.')
        if not all(section.get('control_cruzado_anexo', {}).get(key, False)
                   for key in ('tablas_identicas', 'calificacion_reportada_coincide')):
            paragraphs.append('El control cruzado con el Anexo requiere revisión.')
        key = f'analisis_indicador_{number:02d}'
        values[key] = '\n\n'.join(paragraphs)
        analyses.append({'indicador': number, 'variable': key,
                         'cierre': 'Las puntuaciones anteriores corresponden a los criterios internos de la ficha. Los datos autodeclarados no acreditan por sí solos calidad operativa ni efectos sobre el delito.'})
    dimension_names = {item['codigo']: item['nombre'] for item in dictionary['catalogos']['dimensiones']}
    dimension_values = {period: {} for period in PERIODOS}
    for period, label in PERIODOS.items():
        pending = [s['numero'] for s in sections if s['evaluaciones'][period]['puntaje'] is None]
        grade = result['calculos'][period]['calificacion_final']
        sentences = [f"{label}: {len(sections) - len(pending)} de 18 indicadores cuentan con puntaje calculado."]
        if pending:
            sentences.append('La calificación global permanece pendiente por los indicadores ' + ', '.join(map(str, pending)) + '.')
        else:
            sentences.append(f"La calificación global calculada es {grade}, después de aplicar los candados de la metodología interna.")
        dims = []
        for name, ids in rules['dimensiones'].items():
            scores = [s['evaluaciones'][period]['puntaje'] for s in sections if s['numero'] in ids]
            mean = None if any(s is None for s in scores) else decimal_corto(sum(Decimal(s) for s in scores) / len(scores))
            dimension_values[period][name] = mean
            dims.append(f"{dimension_names[name]}: {mean + '/5' if mean else 'promedio pendiente'}")
        values[f'resumen_{period}'] = ' '.join(sentences) + '\n\n' + '; '.join(dims) + '. No se infiere una tendencia temporal ni una posición frente al estado a partir de información incompleta.'
    rows = []
    for section in sections:
        evaluations = section['evaluaciones']
        notes = [f"{PERIODOS[p]}: {v['motivo']}" for p, v in evaluations.items() if v['puntaje'] is None]
        if len(notes) == 2 and evaluations['general']['motivo'] == evaluations['ultimo_periodo']['motivo']:
            notes = ['Ambos periodos: ' + evaluations['general']['motivo']]
        rows.append({'indicador': section['numero'],
                     'general': puntaje(evaluations['general']['puntaje']),
                     'ultimo_periodo': puntaje(evaluations['ultimo_periodo']['puntaje']),
                     'nota': ' '.join(notes)})
    grades = {p: result['calculos'][p]['calificacion_final'] or 'PENDIENTE' for p in PERIODOS}
    active = ['municipio', 'estado', 'año_inicial', 'año_final', 'resumen_general', 'resumen_ultimo_periodo'] + [a['variable'] for a in analyses]
    result['contenido_word'] = {
        'version': '1.0', 'perfil': 'diagnostico_desde_evidencia',
        'titulo': title,
        'aviso_borrador': 'BORRADOR DE REVISIÓN — evaluación pendiente de validación; no es un diagnóstico final.',
        'periodo': f"Periodo documental: {values['año_inicial']}–{values['año_final']}. Los años se conservan como etiquetas de las tablas fuente.",
        'calificaciones': grades, 'hoja_computo': rows,
        'promedios_dimension': dimension_values,
        'promedios_generales': {p: result['calculos'][p].get('promedio_tres_dimensiones') for p in PERIODOS},
        'candados': {p: ', '.join(str(c['regla_id']) for c in result['calculos'][p].get('candados_aplicados', []))
                    if grades[p] != 'PENDIENTE' else 'Pendiente' for p in PERIODOS},
        'analisis': analyses,
        'variables_activas': active,
        'variables_no_aplicables': sorted(set(dictionary['variables_documento']) - set(active)),
        'decision_editorial': 'Se usan los resúmenes y análisis específicos. Se excluyen guía de captura, textos alternativos genéricos, productos de gobierno/electoral y bancos de fuentes sugeridas; se conserva el Anexo 1 metodológico. Esta selección no resuelve sus verificaciones ni acredita vigencia externa.',
    }
    # Quitar únicamente los bloqueos técnicos que esta composición sí resuelve.
    result['validaciones'] = [v for v in result['validaciones']
                              if v['codigo'] not in ('VARIABLES_PENDIENTES', 'COMPOSICION_WORD_PENDIENTE')]
    missing = [key for key in active if values.get(key) is None or values.get(key) == '']
    if missing:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'VARIABLES_ACTIVAS_PENDIENTES', 'variables': missing})
    if not any(v['codigo'] == REVISION_EDITORIAL for v in result['validaciones']):
        result['validaciones'].append({'nivel': 'revision', 'codigo': REVISION_EDITORIAL,
                                      'detalle': 'Revisar prosa, correspondencia de años, criterios y referencias del Anexo 1 antes de validar la versión final.'})
    return result
