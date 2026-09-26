"""Contenido editorial reproducible a partir de resultados y evidencia del JSON."""
from decimal import Decimal, ROUND_HALF_UP
from analisis_evidencia import analizar_indicador
from investigacion import integrar, narrativas
from redaccion_consultoria import (bibliografia_documental, enumerar, fuente_grafica,
                                  motivo_publico, nota_indicador, notas_alcance, periodo_texto,
                                  texto_pendiente, titulo_tabla, validar_publicacion)

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
        'La evaluación comprende 18 indicadores de protección civil, condiciones del personal e inteligencia '
        'y eficiencia policial. La escala va de 1 a 5. Los indicadores tienen igual peso dentro de cada '
        f'dimensión; el resultado conjunto considera las siguientes ponderaciones: {weights_text}. '
        'Las condiciones de consistencia de la metodología pueden limitar la categoría asignada cuando '
        'existen desequilibrios entre dimensiones, sin modificar el promedio numérico.'
        '\n\n'
        'Cada valoración se sustenta en información comparable y en los criterios definidos para el indicador. '
        f'Cuando la evidencia resulta insuficiente, se asigna la base de {policy["piso_no_acreditado"]}/5, '
        'identificada como «no acreditado». Esta convención permite presentar una calificación documental '
        'completa, pero no demuestra un desempeño desfavorable ni una falta de respuesta del municipio. '
        'Por ello, los resultados deben leerse junto con la cobertura de información y las limitaciones '
        'señaladas en cada apartado. La medición no constituye una certificación oficial de cumplimiento.')}
    for period, label in PERIODOS.items():
        calculation = result['calculos'][period]
        coverage = calculation['cobertura']
        sensitivity = calculation['sensibilidad']
        if not coverage['observados']:
            coverage_text = (f"En el {label.lower()}, ninguno de los {coverage['total']} indicadores reúne "
                             'la evidencia necesaria para valorar su desempeño (cobertura: 0 %). '
                             'Todos reciben la base por información insuficiente.')
        else:
            coverage_text = (f"En el {label.lower()}, la información permite valorar {coverage['observados']} de "
                             f"{coverage['total']} indicadores ({decimal_corto(coverage['porcentaje'])} %).")
            if decimal_corto(coverage['ponderada_porcentaje']) != decimal_corto(coverage['porcentaje']):
                coverage_text += (f" Al considerar el peso de las dimensiones, la cobertura equivale a "
                                  f"{decimal_corto(coverage['ponderada_porcentaje'])} %.")
            if coverage['observados'] < coverage['total']:
                coverage_text += (f" Los {coverage['total'] - coverage['observados']} restantes reciben la base "
                                  'por información insuficiente.')
        values[f'cobertura_{period}'] = coverage_text
        values[f'sensibilidad_{period}'] = (
            f"Para el {label.lower()}, el promedio puede variar entre {decimal_corto(sensitivity['minimo'])} "
            f"y {decimal_corto(sensitivity['maximo'])}/5 si los indicadores sin evidencia suficiente se sitúan "
            f"en los extremos {policy['piso_no_acreditado']} y {policy['techo_sensibilidad']} de la escala. "
            'Este ejercicio muestra cuánto depende el resultado de la información pendiente, antes de aplicar '
            'las condiciones de consistencia. El intervalo describe escenarios de cálculo, no una estimación estadística del desempeño.')
        if coverage['observados'] == coverage['total']:
            values[f'sensibilidad_{period}'] = (
                f"En el {label.lower()}, todos los indicadores cuentan con evidencia suficiente para su valoración. "
                f"El intervalo de sensibilidad se reduce a {decimal_corto(sensitivity['minimo'])}/5: "
                'no hay notas pendientes cuya variación altere este promedio. Esto no elimina las demás limitaciones de las fuentes.')
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
            values[f'calificacion_indicador_{number:02d}_{period}'] = nota_indicador(section, period)
            # La nota ya figura en su rótulo y gráfica. Aquí se desarrolla su límite
            # sustantivo; la insuficiencia del periodo reciente aparece en el cierre.
            if period == 'general' and evaluation['puntaje'] is None:
                limitation = motivo_publico(evaluation, number)
                paragraphs.append('En el periodo general, ' + limitation[0].lower() + limitation[1:])
            if evaluation.get('nota'):
                note = evaluation['nota']
                if note not in paragraphs:
                    paragraphs.append(note)
        if not all(section.get('control_cruzado_anexo', {}).get(key, False)
                   for key in ('tablas_identicas', 'calificacion_reportada_coincide')):
            paragraphs.append('Las diferencias entre el compendio de seguridad y su anexo requieren conciliación antes de cerrar la valoración.')
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
        period_label = label.lower() + (' (' + periodo_texto(target_years) + ')' if target_years else '')
        sentences = [f"La calificación del {period_label} es {grade}."]
        if len(pending) == len(sections):
            sentences.append('El resultado corresponde íntegramente a la base por información insuficiente. '
                             'La evidencia disponible no permite valorar el desempeño de los 18 indicadores para este intervalo; '
                             'por tanto, la nota expresa una limitación de la evaluación.')
        elif pending:
            sentences.append(f'La valoración se sustenta en {len(sections) - len(pending)} de los 18 indicadores. '
                             'Los indicadores ' + enumerar(pending) + ' reciben la base por información insuficiente, '
                             'por lo que su desempeño permanece sin determinar.')
        else:
            sentences.append('La información disponible permite sustentar la valoración de los 18 indicadores conforme a los criterios de la metodología.')
        dims = []
        for name, ids in rules['dimensiones'].items():
            mean = decimal_corto(calculation['promedios_dimension'][name])
            dimension_values[period][name] = mean
            dims.append(f"{dimension_names[name]}: {mean}/5")
        values[f'resumen_{period}'] = ' '.join(sentences) + '\n\n' + 'Los resultados por dimensión son: ' + '; '.join(dims) + '.'
    rows = []
    for section in sections:
        evaluations = section['evaluaciones']
        notes = [f"{PERIODOS[p]}: {motivo_publico(v, section['numero'])}" for p, v in evaluations.items() if v['puntaje'] is None]
        if len(notes) == 2 and evaluations['general']['motivo'] == evaluations['ultimo_periodo']['motivo']:
            notes = ['Ambos periodos: ' + motivo_publico(evaluations['general'], section['numero'])]
        rows.append({'indicador': section['numero'],
                     'general': puntaje(evaluations['general']['puntaje_asignado']),
                     'ultimo_periodo': puntaje(evaluations['ultimo_periodo']['puntaje_asignado']),
                     'nota': ' '.join(notes)})
    grades = {p: nota_documental(result['calculos'][p]) for p in PERIODOS}
    values.update(calificacion_general=grades['general'], calificacion_ultimo_periodo=grades['ultimo_periodo'])
    values.update(textos_metodologia(result, rules))
    for section, analysis in zip(sections, analyses):
        number = section['numero']
        tables = [{'titulo': titulo_tabla(table),
                   'ambito': table['ambito'], 'tabla_fuente': table['tabla'], 'filas': table['filas']}
                  for table in section['tablas']]
        values[f'tablas_indicador_{number:02d}'] = tables
        values[f'cierre_indicador_{number:02d}'] = analysis['cierre']
        scores = [section['evaluaciones'][period]['puntaje_asignado'] for period in PERIODOS]
        values[f'graficas_indicador_{number:02d}'] = ([{
            'tipo': 'puntajes', 'titulo': f"Indicador {number:02d}: calificaciones documentales",
            'categorias': list(PERIODOS.values()), 'valores': scores,
            'fuente': fuente_grafica(section)
        }])
    values['bibliografia'] = '\n\n'.join(bibliografia_documental(result))
    active = list(dictionary['variables_documento'])
    result['contenido_word'] = {
        'version': '3.4', 'perfil': 'seguridad_investigacion_v3',
        'titulo': title,
        'aviso_borrador': 'BORRADOR DE REVISIÓN — versión de trabajo sujeta a revisión sustantiva y aprobación.',
        'periodo': (f"Periodo documental: {values.get('año_inicial', 'pendiente')}–{values.get('año_final', 'pendiente')}. "
                    + ('Intervalo reciente común: ' + '–'.join(map(str, periods['ultimo_periodo']['años_objetivo'])) + '. '
                       if periods.get('ultimo_periodo', {}).get('años_objetivo') else '')
                    + 'Años consignados en las fuentes consultadas.'),
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
    result['contenido_word']['notas_alcance'] = notas_alcance(result)
    result['contenido_word']['textos_pendientes'] = {key: texto_pendiente(key) for key in missing}
    result['control_redaccion'] = validar_publicacion(result)
    return result
