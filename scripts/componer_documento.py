"""Compone el estudio a partir de una interpretación editorial sustentada."""
from decimal import Decimal, ROUND_HALF_UP

from redaccion_editorial import cargar_redaccion, validar_redaccion
from redaccion_consultoria import PERIODOS, periodo_texto, validar_publicacion


def puntaje(value):
    return 'Sin valoración' if value is None else str(value)


def decimal_corto(value):
    return str(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def etiqueta_calificacion(calculation):
    grade = calculation.get('calificacion_final')
    if grade is None:
        return 'SIN VALORACIÓN CONJUNTA'
    if calculation.get('estado') == 'calculado_disponibles':
        return f'{grade} (COBERTURA PARCIAL)'
    return grade


def _nota_calificacion(result, period):
    """Publica la cobertura del cálculo sin sustituir el juicio editorial."""
    calculation = result['calculos'][period]
    graded = sum(section['evaluaciones'][period].get('puntaje') is not None
                 for section in result['indicadores'])
    total = len(result['indicadores'])
    grade = calculation.get('calificacion_final')
    if not grade:
        return (f'La información permite valorar {graded} de los {total} indicadores. '
                'La valoración conjunta requiere completar la evidencia de los restantes.')
    if calculation.get('estado') == 'calculado_disponibles':
        coverage = calculation['cobertura']
        dimensions = coverage['por_dimension']
        detail = ', '.join(f'{name} ({entry["evaluables"]} de {entry["total"]})'
                           for name, entry in (
                               ('protección civil', dimensions['proteccion_civil']),
                               ('condiciones del personal', dimensions['condiciones_del_personal']),
                               ('inteligencia y eficiencia policial', dimensions['inteligencia_y_eficiencia_policial'])))
        return (f'La calificación parcial {grade} considera {graded} de los {total} indicadores: {detail}. '
                f'Entre los {coverage["prioritarios_total"]} prioritarios, '
                f'{coverage["prioritarios_evaluables"]} cuentan con puntaje. '
                'Los demás no se calificaron por falta de evidencia suficiente; incorporarlos puede modificar el resultado.')
    if graded < total:
        return (f'La calificación {grade} comprende {graded} de los {total} indicadores; '
                'expresa el desempeño documentado y no presupone el resultado de los que carecen de evidencia suficiente.')
    return f'La calificación {grade} integra los {total} indicadores de seguridad.'


def componer(result, dictionary, rules, redaccion=None):
    """No inventa prosa: una nueva fuente exige una nueva interpretación editorial."""
    artifact = cargar_redaccion(redaccion, municipio=result['municipio'])
    editorial_control = validar_redaccion(result, artifact)
    values = {
        'municipio': result['municipio'], 'estado': result['estado'],
        'calificacion_general': etiqueta_calificacion(result['calculos']['general']),
        'calificacion_ultimo_periodo': etiqueta_calificacion(result['calculos']['ultimo_periodo']),
    }
    for key, paragraphs in artifact['bloques'].items():
        values[key] = '\n\n'.join(paragraph['texto'].strip() for paragraph in paragraphs)
    for period, key in (('general', 'resumen_general'), ('ultimo_periodo', 'resumen_ultimo_periodo')):
        values[key] += '\n\n' + _nota_calificacion(result, period)
    if set(values) != set(dictionary['variables_documento']):
        raise ValueError('La interpretación editorial no corresponde a las variables del contrato documental.')
    result['valores_plantilla'] = values
    years = result.get('periodos_evaluacion', {}).get('general', {}).get('años_objetivo', [])
    dimensions = {}
    for period in PERIODOS:
        dimensions[period] = {}
        for dimension, ids in rules['dimensiones'].items():
            value = result['calculos'][period].get('promedios_dimension', {}).get(dimension)
            dimensions[period][dimension] = decimal_corto(value) if value is not None else None
    result['version'] = '2.3'
    result['contenido_word'] = {
        'version': '2.3', 'perfil': 'estudio_seguridad',
        'titulo': f"Estudio de Seguridad de {result['municipio']}, {result['estado']}",
        'periodo': periodo_texto(years),
        'calificaciones': {period: values['calificacion_' + period] for period in PERIODOS},
        'promedios_dimension': dimensions,
        'promedios_generales': {period: result['calculos'][period].get('promedio_tres_dimensiones') for period in PERIODOS},
        'hoja_computo': [{'indicador': section['numero'],
                         **{period: puntaje(section['evaluaciones'][period]['puntaje']) for period in PERIODOS}}
                        for section in result['indicadores']],
        'variables_activas': sorted(values), 'control_editorial': editorial_control, 'redaccion': artifact,
    }
    result['validaciones'] = [item for item in result.get('validaciones', []) if item.get('codigo') not in {
        'REVISION_EDITORIAL_WORD', 'VARIABLES_PENDIENTES', 'COMPOSICION_WORD_PENDIENTE', 'VARIABLES_ACTIVAS_PENDIENTES'}]
    result['contenido_word']['control_redaccion'] = validar_publicacion(result)
    return result
