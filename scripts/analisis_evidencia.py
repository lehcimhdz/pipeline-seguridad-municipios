"""Lectura consultiva de los dieciocho indicadores, con evidencia separada de la prosa."""
from collections import defaultdict
from decimal import Decimal

from calificar import normalizar, numero
from documentos import registros
from redaccion_consultoria import enumerar, periodo_texto

CATEGORIAS = {'tema', 'tema impartido', 'elementos del uniforme', 'equipamiento', 'evento', 'instrumento'}
SI = {'si', 'si existe', 'existe'}
NO = {'no', 'no existe'}


def formato_numero(value):
    value = Decimal(str(value))
    text = format(value, ',f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def concepto(number, field, scope):
    name = normalizar(field)
    if name == 'porcentaje':
        descriptions = {
            1: 'la proporción de municipios con plan de protección civil',
            5: 'el porcentaje de aprobación de las evaluaciones de control de confianza',
            6: 'la proporción de municipios con instituto de formación policial',
            7: 'la proporción de policías con Certificado Único Policial vigente',
            11: 'la proporción de municipios con sistemas de información georreferenciados',
            12: 'la proporción de municipios que realiza patrullajes estratégicos',
            13: 'la proporción de municipios que atiende problemas comunitarios',
            15: 'la proporción de llamadas procedentes',
            16: 'la proporción de municipios con informe anual de actividades',
            17: 'el porcentaje de cadetes egresados',
        }
        return descriptions.get(number, 'el porcentaje de ' + field.lower())
    if name == 'total':
        return {4: 'el personal destinado a seguridad pública', 14: 'el número de cámaras de vigilancia',
                17: 'el número de policías fallecidos', 18: 'el número de personas puestas a disposición'}.get(number, field.lower())
    return {'numero de cursos': 'el número de cursos de protección civil',
            'personal capacitado': 'el personal capacitado en protección civil',
            'numero de servidores capacitados': 'el personal capacitado en protección civil',
            'llamadas procedentes': 'el número de llamadas procedentes',
            'total de personas': 'el número de personas puestas a disposición'}.get(name, field.lower())


def capacidad(number):
    return {1: 'un plan o programa de protección civil',
            6: 'un instituto de formación policial', 11: 'sistemas de información georreferenciados',
            12: 'patrullajes estratégicos', 13: 'atención a problemas comunitarios',
            16: 'un informe anual de actividades'}.get(number, 'la capacidad evaluada')


def diferencia(first, last, percentage=False):
    diff = last - first
    if not diff:
        return 'sin cambio entre ambas observaciones'
    action = 'un aumento' if diff > 0 else 'una disminución'
    unit = (' punto porcentual' if abs(diff) == 1 else ' puntos porcentuales') if percentage else ''
    return f'{action} de {formato_numero(abs(diff))}{unit}'


def leer_serie(rows, field, number, scope, location):
    by_year = defaultdict(list)
    for row in rows:
        by_year[row['año']].append(row)
    duplicates = [year for year, items in by_year.items() if len(items) > 1]
    subject = concepto(number, field, scope)
    if duplicates:
        return (f'En {location}, la información sobre {subject} presenta varias observaciones para '
                f'{enumerar(sorted(duplicates))}. Es necesario conciliarlas antes de establecer una evolución anual.')
    ordered = [by_year[year][0] for year in sorted(by_year)]
    first, last = ordered[0], ordered[-1]
    raw = lambda row: str(row['celdas'].get(field, '')).strip()
    yes = [row['año'] for row in ordered if normalizar(raw(row)) in SI]
    no = [row['año'] for row in ordered if normalizar(raw(row)) in NO]
    if yes or no:
        parts = []
        if yes:
            parts.append(f'{location} reporta {capacidad(number)} en {enumerar(yes)}')
        if no:
            parts.append((f'{location} reporta la ausencia de {capacidad(number)}' if not yes else
                          'reporta su ausencia') + f' en {enumerar(no)}')
        sentence = '; '.join(parts) + '.'
        missing = [row['año'] for row in ordered if normalizar(raw(row)) not in SI | NO]
        if missing:
            sentence += f' La situación de {enumerar(missing)} no está confirmada.'
        return sentence
    vals = [numero(raw(row)) for row in ordered]
    percent = normalizar(field) == 'porcentaje'
    unit = '%' if percent else ''
    shown = lambda value: formato_numero(value) + unit
    outside = percent and any(value is not None and (value < 0 or value > 100) for value in vals)
    if len(ordered) >= 2 and vals[0] is not None and vals[-1] is not None:
        if outside:
            sentence = (f'En {location}, {subject} registra {shown(vals[0])} en {first["año"]} '
                        f'y {shown(vals[-1])} en {last["año"]}.')
        elif vals[0] == vals[-1]:
            sentence = f'En {location}, {subject} registra {shown(vals[0])} tanto en {first["año"]} como en {last["año"]}.'
        else:
            sentence = (f'En {location}, {subject} pasó de {shown(vals[0])} en {first["año"]} '
                        f'a {shown(vals[-1])} en {last["año"]}, {diferencia(vals[0], vals[-1], percent)}.')
        if len(ordered) >= 3 and vals[-2] is not None:
            if vals[-2] == vals[-1]:
                sentence += f' El valor de {last["año"]} coincide con el de {ordered[-2]["año"]}.'
            elif not percent or all(0 <= value <= 100 for value in vals[-2:]):
                sentence += (f' Frente a {shown(vals[-2])} en {ordered[-2]["año"]}, '
                             f'el resultado de {last["año"]} supone {diferencia(vals[-2], vals[-1], percent)}.')
            else:
                sentence += f' En {ordered[-2]["año"]} se reportó un valor de {shown(vals[-2])}.'
    elif vals[-1] is not None:
        sentence = f'En {location}, {subject} registra {shown(vals[-1])} en {last["año"]}.'
    elif any(value is not None for value in vals):
        previous = next((row, value) for row, value in reversed(list(zip(ordered, vals))) if value is not None)
        sentence = (f'En {location}, no hay información de {subject} para {last["año"]}. '
                    f'La última observación disponible corresponde a {previous[0]["año"]}: {shown(previous[1])}.')
    else:
        sentence = f'En {location}, la información de {subject} no permite establecer una evolución cuantitativa en {periodo_texto(by_year)}.'
    missing = [row['año'] for row, value in zip(ordered, vals) if value is None]
    if missing and vals[-1] is not None:
        sentence += f' No se dispone de información comparable para {enumerar(missing)}.'
    if outside:
        sentence += ' Hay porcentajes fuera del intervalo de 0 a 100%; deben aclararse las bases de referencia antes de interpretar la evolución.'
    return sentence


def leer_categorias(rows, category, number, location):
    years = sorted({row['año'] for row in rows})
    latest = [row for row in rows if row['año'] == years[-1]]
    names = list(dict.fromkeys(row['celdas'].get(category, '').strip() for row in latest
                              if row['celdas'].get(category, '').strip()))
    label = {3: 'temas de protección civil', 8: 'elementos de uniforme', 9: 'tipos de equipamiento',
             10: 'temas de capacitación policial',
             17: ('tipos de evento asociados con los fallecimientos' if normalizar(category) == 'evento'
                  else 'categorías de instrumentos involucrados en los fallecimientos')}.get(number, 'rubros')
    if not names:
        return f'En {location}, la información de {years[-1]} no permite identificar {label}.'
    numeric = [row for row in latest if numero(row['celdas'].get('Total', '')) is not None]
    selected = sorted(numeric, key=lambda row: numero(row['celdas']['Total']), reverse=True)[:3] if numeric else latest[:3]
    samples = []
    for row in selected:
        data = row['celdas']
        detail = data.get(category, '').strip()
        if not detail:
            continue
        if numeric:
            quantity = formato_numero(numero(data['Total']))
            singular = numero(data['Total']) == 1
            suffix = (' participante' if singular else ' participantes') if number == 10 else (
                (' unidad' if singular else ' unidades') if number == 9 else (' caso' if singular else ' casos'))
            detail += f' ({quantity}{suffix}'
            if numero(data.get('Porcentaje', '')) is not None:
                detail += f'; {formato_numero(numero(data["Porcentaje"]))}%'
            detail += ')'
        elif data.get('Frecuencia', '').strip():
            awarded = normalizar(data.get('Otorgado', ''))
            status = 'entrega ' + data['Frecuencia'].lower() if awarded in SI else 'entrega no confirmada'
            detail += f' ({status})'
        elif numero(data.get('Porcentaje', '')) is not None:
            detail += f' ({formato_numero(numero(data["Porcentaje"]))}% de los municipios)'
        samples.append(detail)
    if number == 17 and numeric and all(numero(row['celdas']['Total']) == 0 for row in numeric):
        sentence = (f'En {location}, el desglose de {label} de {years[-1]} registra cero en '
                    'los conceptos con información cuantitativa. Este desglose debe cotejarse con el total de fallecimientos.')
    else:
        sentence = (f'En {years[-1]}, {location} reporta {len(names)} {label}; '
                    + ('entre ellos, ' if len(names) > 3 else '') + enumerar(samples) + '.')
    if number == 10:
        zeros = sum(numero(row['celdas'].get('Total', '')) == 0 for row in latest)
        if zeros:
            sentence += f' En {zeros} ' + ('tema' if zeros == 1 else 'temas') + ' se reportan cero participantes.'
        sentence += ' La participación por curso no representa personas distintas entre cursos.'
        positive = [row for row in numeric if numero(row['celdas']['Total']) > 0]
        if positive and len({numero(row['celdas']['Total']) for row in positive}) > 1:
            smallest = min(positive, key=lambda row: numero(row['celdas']['Total']))
            sentence += (f' Una de las menores participaciones corresponde a {smallest["celdas"][category]}: '
                         f'{formato_numero(numero(smallest["celdas"]["Total"]))} participantes.')
    if any('Total' in row['celdas'] and numero(row['celdas']['Total']) is None for row in latest):
        sentence += ' Hay conceptos sin una cantidad disponible; deben aclararse antes de completar la valoración.'
    return sentence


RECOMENDACIONES = {
    1: 'La continuidad del programa importa para organizar responsabilidades ante emergencias. Conviene revisar su actualización, los responsables de activación y los ejercicios de coordinación; la sola existencia del documento no demuestra preparación operativa.',
    2: 'La capacidad de respuesta requiere sostener la formación y comprobar lo aprendido. Se recomienda programar cursos a partir de los riesgos locales y verificar mediante ejercicios las funciones de quienes participan.',
    3: 'La preparación ante emergencias requiere una formación acorde con los riesgos locales. Conviene contrastar los temas impartidos con los riesgos del municipio y asegurar continuidad en primeros auxilios, evacuación y análisis de riesgos.',
    4: 'Los cambios del personal afectan la organización de turnos y despliegues. Es necesario revisar altas, bajas y asignaciones antes de ajustar el reclutamiento; sin población y distribución operativa comparables no puede establecerse si la dotación es suficiente.',
    5: 'La aprobación de evaluaciones de control de confianza requiere seguimiento continuo. Conviene identificar los grupos pendientes de evaluación o renovación y programar su atención, sin confundir el porcentaje aprobado con una garantía de conducta individual.',
    6: 'Un instituto de formación puede sostener la profesionalización si dispone de programas, instructores y seguimiento. Se recomienda revisar su actividad efectiva y vincular su oferta con las necesidades de los mandos y del personal operativo.',
    7: 'La vigencia del Certificado Único Policial exige anticipar vencimientos y atender requisitos pendientes. Se recomienda mantener un calendario individual de renovación para sostener la cobertura y evitar interrupciones.',
    8: 'La entrega de uniformes debe responder al uso y desgaste de cada prenda. Conviene verificar la cobertura por persona y por turno, así como los mecanismos de reposición; las frecuencias reportadas no prueban que todo el personal esté cubierto.',
    9: 'La disponibilidad de equipo condiciona las tareas que pueden realizarse con protección adecuada. Conviene contrastar el inventario con las asignaciones por turno, su mantenimiento y su funcionamiento antes de definir compras o reposiciones.',
    10: 'La formación necesita continuidad y relación con las tareas policiales. Se recomienda priorizar los temas con menor participación, revisar asistencia y aprendizaje, y asegurar que la capacitación llegue a quienes realizan esas funciones.',
    11: 'La información georreferenciada puede apoyar decisiones sobre el despliegue policial. Conviene verificar la actualización de los registros, la calidad de la ubicación y el uso de los análisis en las decisiones de supervisión.',
    12: 'Los patrullajes estratégicos requieren traducir el análisis territorial en recorridos y horarios revisables. Se recomienda documentar el criterio de asignación y evaluar los resultados por zona, sin atribuir al patrullaje cambios delictivos que no se han medido.',
    13: 'La atención comunitaria necesita seguimiento de los acuerdos y de los problemas recurrentes. Conviene registrar tiempos de atención, reincidencia de los conflictos y cumplimiento de compromisos para valorar su utilidad para los vecinos.',
    14: 'El número de cámaras es sólo una parte de la capacidad de vigilancia. Antes de ampliar la red, conviene revisar cuántas funcionan, qué zonas cubren y cómo se atienden sus alertas; el inventario por sí solo no permite determinar suficiencia.',
    15: 'La atención de llamadas requiere revisar tanto su procedencia como la respuesta que reciben. Se recomienda identificar motivos de improcedencia y dar seguimiento a despacho, tiempos de atención y cierre, sin equiparar volumen de llamadas con eficacia policial.',
    16: 'El informe anual ofrece una oportunidad de rendición de cuentas. Conviene vincularlo con metas, resultados y compromisos de mejora, y comprobar que pueda consultarse y compararse entre años.',
    17: 'La formación de nuevos elementos y la protección del personal deben planearse conjuntamente. Conviene conciliar las cifras de egreso y fallecimientos, revisar las circunstancias de los decesos y orientar capacitación, equipo y protocolos a los riesgos documentados.',
    18: 'Las puestas a disposición describen actividad policial, pero una variación en su número no demuestra mayor o menor seguridad. Conviene distinguir asuntos penales y administrativos y revisar su resolución y legalidad antes de fijar metas de volumen.',
}


def recomendacion(section):
    """Ajusta la prioridad al cambio observado, sin convertirlo en explicación causal."""
    number = section['numero']

    def recent(field):
        by_year = defaultdict(list)
        for table in section['tablas']:
            if table.get('ambito') != 'municipal' or not table.get('filas') or field not in table['filas'][0]:
                continue
            for row in registros(table):
                by_year[row['año']].append(row['celdas'].get(field, ''))
        years = sorted(by_year)[-2:]
        if len(years) != 2 or any(len(by_year[year]) != 1 for year in years):
            return None
        values = [numero(by_year[year][0]) for year in years]
        return values if all(value is not None for value in values) else None

    field = 'Porcentaje' if number in (5, 7, 15) else 'Total de personas' if number == 18 else 'Total'
    values = recent(field)
    opening = ''
    if values:
        change = values[1] - values[0]
        if number == 4 and change < 0:
            opening = 'La reducción reciente del personal obliga a revisar cómo se cubren los turnos y las funciones sustantivas. '
        elif number == 5 and change < 0:
            opening = 'La menor aprobación respecto de la observación anterior aconseja revisar las necesidades de evaluación y acompañamiento. '
        elif number == 7 and change > 0:
            opening = 'El avance reciente en la certificación puede conservarse si se anticipan los vencimientos. '
        elif number == 14 and change > 0:
            opening = 'El crecimiento del inventario reportado hace pertinente verificar la operación y el aprovechamiento de la red. '
        elif number == 15 and change < 0:
            opening = 'La disminución de la proporción de llamadas procedentes hace prioritario revisar su clasificación y canalización. '
        elif number == 18 and change < 0:
            opening = 'La reducción reciente de las puestas a disposición requiere examinar qué tipos de asuntos disminuyeron. '
    if number == 2:
        courses = recent('Número de cursos')
        people = recent('Número de servidores capacitados')
        if courses and people and courses[1] < courses[0] and people[1] > people[0]:
            opening = 'El aumento del personal capacitado junto con un menor número de cursos hace pertinente revisar el tamaño de los grupos y el aprovechamiento de la formación. '
    # El hallazgo contextual sustituye la apertura general para evitar dos
    # frases consecutivas que recomienden la misma acción.
    base = RECOMENDACIONES[number]
    return opening + (base if number == 18 else base.split('. ', 1)[-1]) if opening else base


def analizar_indicador(section, municipio='El municipio', estado='el estado', periodos=None):
    paragraphs, trace = [], []
    municipal, latest_findings = [], []
    number = section['numero']
    tables = sorted(section['tablas'], key=lambda table: table.get('ambito') != 'municipal')
    for table in tables:
        rows = list(registros(table)) if table.get('filas') else []
        location = municipio if table.get('ambito') == 'municipal' else estado
        fields = [field for field in table['filas'][0] if field != 'Año'] if table.get('filas') else []
        trace.append({'tabla': table['tabla'], 'ambito': table.get('ambito'),
                      'años_observados': sorted({row['año'] for row in rows}),
                      'filas': [row['fila'] for row in rows], 'campos': fields, 'fuente': 'PAQUETE SEGURIDAD'})
        if not rows:
            paragraphs.append(f'La información de {location} no identifica años que permitan examinar la evolución de este indicador.')
            continue
        category = next((field for field in fields if normalizar(field) in CATEGORIAS), None)
        if category:
            paragraph = leer_categorias(rows, category, number, location)
        else:
            paragraph = ' '.join(leer_serie(rows, field, number, table.get('ambito'), location) for field in fields)
        paragraphs.append(paragraph)
        if table.get('ambito') == 'municipal':
            municipal.append(paragraph)
            latest_years = sorted({row['año'] for row in rows})[-2:]
            latest_rows = [row for row in rows if row['año'] in latest_years]
            latest_text = (
                leer_categorias(latest_rows, category, number, location) if category else
                ' '.join(leer_serie(latest_rows, field, number, table.get('ambito'), location)
                         for field in fields))
            latest_findings.append(latest_text or paragraph)
    # Sólo comparar porcentajes que miden el mismo concepto en ambos territorios.
    if number in (5, 7, 15):
        pairs = {}
        for scope in ('municipal', 'estatal'):
            grouped = defaultdict(list)
            for table in tables:
                if table.get('ambito') == scope and 'Porcentaje' in table.get('filas', [[]])[0]:
                    for row in registros(table):
                        grouped[row['año']].append(numero(row['celdas'].get('Porcentaje', '')))
            pairs[scope] = {year: values[0] for year, values in grouped.items()
                            if len(values) == 1 and values[0] is not None and 0 <= values[0] <= 100}
        common = sorted(set(pairs['municipal']) & set(pairs['estatal']))
        if common:
            year = common[-1]
            gap = pairs['municipal'][year] - pairs['estatal'][year]
            relation = 'por encima' if gap > 0 else 'por debajo'
            comparison = (f'En {year}, {municipio} se sitúa {formato_numero(abs(gap))} puntos porcentuales '
                          f'{relation} de la referencia de {estado}.' if gap else
                          f'En {year}, {municipio} y {estado} registran el mismo porcentaje.')
            paragraphs.append(comparison)
    closing = recomendacion(section)
    period_limit = ''
    recent = section.get('evaluaciones', {}).get('ultimo_periodo', {})
    missing = recent.get('años_faltantes', [])
    missing_scope = recent.get('años_faltantes_por_ambito', {})
    if missing_scope:
        parts = [f'información {scope} de {enumerar(years)}' for scope, years in missing_scope.items() if years]
        if parts:
            period_limit = 'La valoración del periodo reciente queda pendiente hasta completar ' + enumerar(parts) + '.'
    elif missing:
        period_limit = 'La valoración del periodo reciente requiere completar la información de ' + enumerar(missing) + '.'
    if not municipal:
        closing = f'La información disponible de {municipio} no permite establecer un hallazgo municipal. ' + closing
    return {'parrafos': paragraphs, 'cierre': closing, 'evidencia': trace,
            'hallazgo_municipal': municipal[0] if municipal else '',
            'hallazgo_reciente': latest_findings[0] if latest_findings else '',
            'hallazgos_municipales': municipal, 'limite_periodo_reciente': period_limit}
