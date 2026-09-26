"""Contenido editorial reproducible a partir de resultados y evidencia del JSON."""
from decimal import Decimal, ROUND_HALF_UP
from analisis_evidencia import analizar_indicador
from investigacion import integrar, narrativas

PERIODOS = {'general': 'Periodo general', 'ultimo_periodo': 'Último periodo'}
REVISION_EDITORIAL = 'REVISION_EDITORIAL_WORD'


def puntaje(value):
    return 'Pendiente' if value is None else str(value)


def decimal_corto(value):
    return str(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def nota_documental(calculation):
    return f"{decimal_corto(calculation['promedio_tres_dimensiones'])}/5 — {calculation['calificacion_final']}"


def textos_metodologia(result, rules):
    """Texto visible: la nota asignada nunca se presenta como evidencia inventada."""
    policy = rules['calificacion_documental']
    weights = policy['pesos_dimension']
    total = sum(Decimal(str(v)) for v in weights.values())
    dimension_labels = {'proteccion_civil': 'protección civil',
                        'condiciones_del_personal': 'condiciones del personal',
                        'inteligencia_y_eficiencia_policial': 'inteligencia y eficiencia policial'}
    weights_text = '; '.join(
        f"{dimension_labels[key]}: {decimal_corto(Decimal(str(value)) / total * 100)} %"
        for key, value in weights.items())
    values = {'metodologia_calificacion': (
        f"Metodología documental {policy['version']}. Escala 1–5: se conserva el puntaje observado cuando "
        f"existe evidencia comparable y un criterio inequívoco. De lo contrario se asigna "
        f"{policy['piso_no_acreditado']}/5 por no acreditación documental, sin inventar datos ni concluir "
        'desempeño deficiente o falta de respuesta municipal. Se promedian los indicadores dentro de cada dimensión '
        f"con igual peso y después las dimensiones ({weights_text}). "
        'Los candados limitan la categoría, no alteran el promedio numérico. '
        'Las categorías documentales no equivalen a las categorías históricas de desempeño. '
        'El puntaje observado y el motivo de cada asignación se conservan en el JSON. '
        'La calificación siempre se emite, pero no convierte el documento en una evaluación final validada. '
        'Parámetros y justificación: reglas_calificacion.json y METODOLOGIA_CALIFICACION.md.')}
    for period, label in PERIODOS.items():
        calculation = result['calculos'][period]
        coverage = calculation['cobertura']
        sensitivity = calculation['sensibilidad']
        values[f'cobertura_{period}'] = (
            f"{label} — cobertura: {coverage['observados']}/{coverage['total']} puntajes observados "
            f"({decimal_corto(coverage['porcentaje'])} %); cobertura ponderada "
            f"{decimal_corto(coverage['ponderada_porcentaje'])} %. "
            f"Se asignaron {coverage['asignados']}/{coverage['total']} calificaciones documentales. "
            'Estos porcentajes miden disponibilidad de evidencia calificable, no probabilidad de certeza.')
        values[f'sensibilidad_{period}'] = (
            f"{label} — sensibilidad: {decimal_corto(sensitivity['minimo'])}–"
            f"{decimal_corto(sensitivity['maximo'])}/5 antes de candados, al colocar los puntajes no acreditados "
            f"en {policy['piso_no_acreditado']} y {policy['techo_sensibilidad']}. "
            'Es un escenario de sensibilidad, no una estimación del desempeño ni un intervalo de confianza.')
    return values


def componer(result, dictionary, rules):
    """Completa sólo prosa sustentada; conserva null en variantes descartadas.

    La composición no decide causas, vigencia jurídica ni revisiones humanas.
    Cada análisis remite a las tablas municipales/estatales originales.
    """
    values = result['valores_plantilla']
    sections = result['indicadores']
    title = f"Diagnóstico de seguridad municipal — {result['municipio']}, {result.get('estado') or 'entidad pendiente'}"
    source = next((item['archivo'] for item in result.get('fuentes', [])
                   if item.get('archivo', '').casefold().endswith(' paquete seguridad.docx')), 'PAQUETE SEGURIDAD')
    periods = result.get('periodos_evaluacion', {})
    analyses = []
    for section in sections:
        number = section['numero']
        reading = analizar_indicador(section, source, periods)
        paragraphs = list(reading['parrafos'])
        for period, label in PERIODOS.items():
            evaluation = section['evaluaciones'][period]
            years = ', '.join(map(str, evaluation.get('años_evaluados', []))) or 'sin cobertura confirmada'
            assigned = evaluation['puntaje_asignado']
            if evaluation['puntaje'] is None:
                sentence = (f"{label} ({years}): calificación documental {assigned}/5 por no acreditación. "
                            f"{evaluation['motivo_asignacion']}")
                visible = f'{label}: {assigned}/5 — NO ACREDITADO (asignación documental; puntaje observado no disponible).'
            else:
                sentence = f"{label} ({years}): {assigned}/5 con puntaje observado. Criterio aplicado: {evaluation['criterio_aplicado']}."
                visible = f'{label}: {assigned}/5 — sustentado en puntaje observado.'
            values[f'calificacion_indicador_{number:02d}_{period}'] = visible
            if evaluation.get('nota'):
                sentence += ' ' + evaluation['nota']
            paragraphs.append(sentence)
        if not all(section.get('control_cruzado_anexo', {}).get(key, False)
                   for key in ('tablas_identicas', 'calificacion_reportada_coincide')):
            paragraphs.append('El control cruzado con el Anexo requiere revisión.')
        key = f'analisis_indicador_{number:02d}'
        values[key] = '\n\n'.join(paragraphs)
        analyses.append({'indicador': number, 'variable': key,
                         'cierre': reading['cierre'], 'evidencia': reading['evidencia']})
    dimension_names = {item['codigo']: item['nombre'] for item in dictionary['catalogos']['dimensiones']}
    dimension_values = {period: {} for period in PERIODOS}
    for period, label in PERIODOS.items():
        pending = [s['numero'] for s in sections if s['evaluaciones'][period]['puntaje'] is None]
        calculation = result['calculos'][period]
        grade = nota_documental(calculation)
        target_years = periods.get(period, {}).get('años_objetivo', [])
        period_label = label + (' (' + ', '.join(map(str, target_years)) + ')' if target_years else '')
        sentences = [f"{period_label}: calificación documental {grade}. "
                     f"Los 18 indicadores tienen nota asignada; {len(sections) - len(pending)} cuentan con puntaje observado."]
        if pending:
            sentences.append('Se asignó la base documental de no acreditación a los indicadores ' + ', '.join(map(str, pending))
                             + '; sus faltantes no se interpretan como desempeño deficiente.')
        else:
            sentences.append('Todos los puntajes están sustentados en criterios observables; la revisión editorial sigue siendo independiente.')
        dims = []
        for name, ids in rules['dimensiones'].items():
            mean = decimal_corto(calculation['promedios_dimension'][name])
            dimension_values[period][name] = mean
            dims.append(f"{dimension_names[name]}: {mean}/5 documental")
        values[f'resumen_{period}'] = ' '.join(sentences) + '\n\n' + '; '.join(dims) + '. No se infiere una tendencia temporal ni una posición frente al estado a partir de información incompleta.'
    rows = []
    for section in sections:
        evaluations = section['evaluaciones']
        notes = [f"{PERIODOS[p]}: {v['motivo']}" for p, v in evaluations.items() if v['puntaje'] is None]
        if len(notes) == 2 and evaluations['general']['motivo'] == evaluations['ultimo_periodo']['motivo']:
            notes = ['Ambos periodos: ' + evaluations['general']['motivo']]
        rows.append({'indicador': section['numero'],
                     'general': puntaje(evaluations['general']['puntaje_asignado']),
                     'ultimo_periodo': puntaje(evaluations['ultimo_periodo']['puntaje_asignado']),
                     'nota': ' '.join(notes)})
    grades = {p: nota_documental(result['calculos'][p]) for p in PERIODOS}
    values.update(calificacion_general=grades['general'], calificacion_ultimo_periodo=grades['ultimo_periodo'])
    values.update(textos_metodologia(result, rules))
    for section, analysis in zip(sections, analyses):
        number = section['numero']
        tables = [{'titulo': f"Datos {table['ambito']} — PAQUETE SEGURIDAD, tabla {table['tabla']}",
                   'ambito': table['ambito'], 'tabla_fuente': table['tabla'], 'filas': table['filas']}
                  for table in section['tablas']]
        values[f'tablas_indicador_{number:02d}'] = tables
        values[f'cierre_indicador_{number:02d}'] = analysis['cierre']
        scores = [section['evaluaciones'][period]['puntaje_asignado'] for period in PERIODOS]
        missing = [PERIODOS[p] for p in PERIODOS if section['evaluaciones'][p]['puntaje'] is None]
        values[f'graficas_indicador_{number:02d}'] = ([{
            'tipo': 'puntajes', 'titulo': f"Indicador {number:02d}: calificaciones documentales",
            'categorias': list(PERIODOS.values()), 'valores': scores,
            'fuente': ('Metodología documental interna; escala 1–5. '
                       + ('Base por no acreditación (no desempeño observado): ' + ', '.join(missing) + '. ' if missing else '')
                       + 'Las diferencias de cobertura no demuestran una tendencia de desempeño.')
        }])
    sources = result.get('fuentes', [])
    values['bibliografia'] = '\n\n'.join(
        f"{source.get('archivo') or source.get('nombre') or source.get('tipo', 'Fuente externa')}. "
        f"SHA-256: {source['sha256']}." if source.get('sha256') else str(source.get('nombre', 'Fuente externa declarada'))
        for source in sources) or 'Referencias documentales registradas en el JSON fuente.'
    active = list(dictionary['variables_documento'])
    result['contenido_word'] = {
        'version': '3.2', 'perfil': 'seguridad_investigacion_v3',
        'titulo': title,
        'aviso_borrador': 'BORRADOR DE REVISIÓN — evaluación pendiente de validación; no es un diagnóstico final.',
        'periodo': (f"Periodo documental: {values.get('año_inicial', 'pendiente')}–{values.get('año_final', 'pendiente')}. "
                    + ('Intervalo reciente común: ' + '–'.join(map(str, periods['ultimo_periodo']['años_objetivo'])) + '. '
                       if periods.get('ultimo_periodo', {}).get('años_objetivo') else '')
                    + 'Los años se conservan como etiquetas de las tablas fuente.'),
        'periodos_evaluacion': periods,
        'calificaciones': grades, 'hoja_computo': rows,
        'promedios_dimension': dimension_values,
        'promedios_generales': {p: result['calculos'][p].get('promedio_tres_dimensiones') for p in PERIODOS},
        'candados': {p: ', '.join(str(c['regla_id']) for c in result['calculos'][p].get('candados_aplicados', []))
                    if grades[p] != 'PENDIENTE' else 'Pendiente' for p in PERIODOS},
        'analisis': analyses,
        'variables_activas': active,
        'variables_no_aplicables': sorted(set(dictionary['variables_documento']) - set(active)),
        'decision_editorial': 'Único perfil de medición de SEGURIDAD v3. Investigación en cuatro líneas, mínimos de protección civil, análisis, gráficas y tablas; propuestas y tendencias limitadas a evidencia. Los benchmarks no cambian puntajes.',
    }
    result['validaciones'] = [v for v in result['validaciones'] if v['codigo'] not in
        ('INVESTIGACION_PENDIENTE', 'REVISION_FUENTES_INVESTIGACION', 'APARTADOS_INVESTIGACION_PENDIENTES',
         'MINIMOS_PROTECCION_CIVIL_PENDIENTES', 'VARIABLES_ACTIVAS_PENDIENTES')]
    narrativas(result, rules)
    integrar(result)
    # Quitar únicamente los bloqueos técnicos que esta composición sí resuelve.
    result['validaciones'] = [v for v in result['validaciones']
                              if v['codigo'] not in ('VARIABLES_PENDIENTES', 'COMPOSICION_WORD_PENDIENTE')]
    missing = [key for key in active if values.get(key) is None or values.get(key) == '']
    if missing:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'VARIABLES_ACTIVAS_PENDIENTES', 'variables': missing})
    if not any(v['codigo'] == REVISION_EDITORIAL for v in result['validaciones']):
        result['validaciones'].append({'nivel': 'revision', 'codigo': REVISION_EDITORIAL,
                                      'detalle': 'Revisar prosa, cobertura, comparaciones, investigación, aplicabilidad de referencias y mínimos antes de validar la versión final.'})
    return result
