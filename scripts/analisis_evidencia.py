"""Lecturas descriptivas de las tablas; no infiere causas ni suma categorías."""
from calificar import normalizar, numero
from documentos import registros
from redaccion_consultoria import motivo_publico

CATEGORIAS = {'tema', 'tema impartido', 'equipamiento', 'elementos del uniforme',
              'evento', 'instrumento'}
SI = {'si', 'si existe', 'existe'}
NO = {'no', 'no existe'}
NOTA_CATEGORIAS = 'Las cifras por categoría no se suman, pues podrían incluir personas o conceptos comunes.'


def formato_numero(value):
    text = format(value, ',f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def variacion(first, last, field):
    difference = last - first
    if difference == 0:
        return 'sin cambio entre ambas observaciones'
    if 'porcentaje' in normalizar(field):
        unit = 'punto porcentual' if abs(difference) == 1 else 'puntos porcentuales'
    else:
        # El nombre de la variable conserva el concepto medido; no se inventa
        # una unidad (personas, equipos o recursos) para encabezados ambiguos.
        unit = ''
    sign = '+' if difference > 0 else '−'
    return f'variación de {sign}{formato_numero(abs(difference))} {unit}'.rstrip()


def referencia(table, years, source):
    labels = 'años ' + ', '.join(map(str, years)) if years else 'sin año identificable'
    scope = {'municipal': 'Información municipal', 'estatal': 'Información estatal'}.get(
        table.get('ambito'), 'Información de ámbito no especificado')
    return f"{scope}, cuadro {table['tabla']}; {labels}"


def valor(row, field):
    raw = row['celdas'].get(field, '').strip()
    return raw or 'no disponible'


def sujeto_campo(field, section):
    """Nombra magnitudes inequívocas; los encabezados ambiguos se citan literalmente."""
    name = normalizar(field)
    if name == 'total':
        return {4: 'El personal destinado a funciones de seguridad pública',
                14: 'El número de cámaras de vigilancia',
                18: 'El número de personas puestas a disposición'}.get(section.get('numero'))
    return {'porcentaje': 'El porcentaje reportado', 'numero de cursos': 'El número de cursos',
            'personal capacitado': 'El personal capacitado',
            'numero de servidores capacitados': 'El número de servidores capacitados',
            'llamadas procedentes': 'El número de llamadas procedentes',
            'total de personas': 'El número de personas reportado'}.get(name)


def leer_campo(rows, field, sujeto=None):
    """Compara extremos sólo si hay una observación y valor comparable por año."""
    years = sorted({row['año'] for row in rows})
    by_year = {year: [row for row in rows if row['año'] == year] for year in years}
    repeated = [year for year, items in by_year.items() if len(items) != 1]
    if repeated:
        return (f'«{field}» presenta más de una observación para '
                + ', '.join(map(str, repeated)) + '; no se establece una cifra anual única.',
                f'La evolución de «{field}» requiere conciliar las observaciones '
                'del mismo año antes de determinar cambios.')
    ordered = [by_year[year][0] for year in years]
    first, last = ordered[0], ordered[-1]
    present = [row['año'] for row in ordered if normalizar(valor(row, field)) in SI]
    absent = [row['año'] for row in ordered if normalizar(valor(row, field)) in NO]
    missing = [row['año'] for row in ordered if not row['celdas'].get(field, '').strip()]
    if present or absent:
        parts = []
        if present:
            parts.append('se declara su existencia en ' + ', '.join(map(str, present)))
        if absent:
            parts.append('se declara su ausencia en ' + ', '.join(map(str, absent)))
        unknown = [row for row in ordered if row['año'] not in present + absent]
        if unknown:
            parts.append('no se dispone de una respuesta afirmativa o negativa en ' + ', '.join(
                f"{row['año']} («{valor(row, field)}»)" for row in unknown))
        narrative = f'«{field}»: ' + '; '.join(parts) + '.'
        closing = f"La situación más reciente de «{field}» se declara como «{valor(last, field)}» en {last['año']}"
        if len(ordered) > 1:
            previous = ordered[-2]
            closing += f", frente a «{valor(previous, field)}» en {previous['año']}"
        closing += '. La declaración de existencia no acredita su funcionamiento efectivo.'
        if missing:
            note = ' No hay información para ' + ', '.join(map(str, missing)) + '; su ausencia no equivale a cero.'
            narrative += note
            closing += note
        return narrative, closing
    numbers = [numero(row['celdas'].get(field, '')) for row in ordered]
    subject = sujeto or f'«{field}»'
    if len(ordered) > 1 and numbers[0] is not None and numbers[-1] is not None:
        narrative = (f"{subject} pasó de {valor(first, field)} en {first['año']} "
                     f"a {valor(last, field)} en {last['año']}, una {variacion(numbers[0], numbers[-1], field)}."
                     if numbers[0] != numbers[-1] else
                     f"{subject} registra {valor(first, field)} en {first['año']} y "
                     f"{valor(last, field)} en {last['año']}, sin cambio entre ambos extremos.")
        if len(ordered) > 2 and numbers[-2] is not None:
            previous = ordered[-2]
            closing = ((f"{subject} registra " if sujeto else f"El valor más reciente de «{field}» es ")
                       + f"{valor(last, field)} en {last['año']}, "
                       f"frente a {valor(previous, field)} en {previous['año']}; "
                       + variacion(numbers[-2], numbers[-1], field) + '.')
        else:
            closing = (f"Al cierre de la serie, {subject[0].lower() + subject[1:]} registra {valor(last, field)} en {last['año']}; "
                       + variacion(numbers[0], numbers[-1], field)
                       + f" respecto de {valor(first, field)} en {first['año']}.")
    else:
        sample = ordered[-2:]
        narrative = f'«{field}» se reporta como ' + '; '.join(
            f"«{valor(row, field)}» en {row['año']}" for row in sample) + '.'
        closing = (f"La última respuesta sobre «{field}» es «{valor(last, field)}» en {last['año']}."
                   if last['año'] not in missing else
                   f"No se dispone de un valor de «{field}» para el año más reciente, {last['año']}.")
        if any(value is not None for value in numbers):
            closing += ' La información no permite calcular una variación entre extremos numéricos comparables.'
        else:
            closing += ' Su carácter descriptivo no permite establecer una variación numérica.'
    if missing:
        note = ' No hay información para ' + ', '.join(map(str, missing)) + '; su ausencia no equivale a cero.'
        narrative += note
        closing += note
    return narrative, closing


def leer_categorias(rows, fields, category):
    years = sorted({row['año'] for row in rows})
    latest = [row for row in rows if row['año'] == years[-1]]
    names = list(dict.fromkeys(row['celdas'][category].strip() for row in latest
                              if row['celdas'].get(category, '').strip()))
    details = []
    # Se citan muestras, no sumas de personas/equipos o categorías solapadas.
    for row in latest[:3]:
        other = [f'{field}: {valor(row, field)}' for field in fields if field != category]
        details.append(f"«{valor(row, category)}»" + (' (' + '; '.join(other) + ')' if other else ''))
    sample = 'entre las categorías reportadas se encuentran ' if len(latest) > 3 else 'se reportan '
    narrative = (f"En {years[-1]} se documentan {len(names)} categorías distintas de «{category}»; "
                 + sample + '; '.join(details) + '.')
    if len(years) > 1:
        first_names = {row['celdas'][category].strip() for row in rows
                       if row['año'] == years[0] and row['celdas'].get(category, '').strip()}
        narrative += (f" En {years[0]} se documentaron {len(first_names)} categorías. "
                      'Esta comparación describe la diversidad declarada, no su cobertura ni efectividad; '
                      'las denominaciones no se han homologado entre años.')
    numeric_fields = [field for field in fields if field != category
                      and any(numero(row['celdas'].get(field, '')) is not None for row in latest)]
    if numeric_fields:
        field = next((field for field in numeric_fields if normalizar(field) == 'total'), numeric_fields[0])
        candidates = [row for row in latest if numero(row['celdas'].get(field, '')) is not None]
        chosen = max(candidates, key=lambda row: numero(row['celdas'][field]))
        maximum = numero(chosen['celdas'][field])
        tied = sum(numero(row['celdas'][field]) == maximum for row in candidates)
        if maximum == 0 and all(numero(row['celdas'][field]) == 0 for row in candidates):
            closing = (f"En {years[-1]}, las {len(candidates)} observaciones con valor numérico "
                       f"de «{field}» registran cero; ninguna presenta un valor superior a las demás.")
        else:
            label = 'uno de los valores máximos reportados' if tied > 1 else 'el valor máximo reportado'
            closing = (f"En {years[-1]}, «{valor(chosen, category)}» presenta {label} "
                       f"de «{field}»: {valor(chosen, field)}")
            percentage = next((key for key in fields if normalizar(key) == 'porcentaje' and key != field), None)
            if percentage:
                closing += f"; el porcentaje reportado para esta categoría es {valor(chosen, percentage)}"
            closing += '.'
        closing += ' ' + NOTA_CATEGORIAS
    else:
        closing = (f"La información de {years[-1]} acredita la declaración de "
                   + ', '.join('«' + name + '»' for name in names[:3])
                   + ', sin establecer por sí sola su cobertura o efectividad.'
                   if names else f"En {years[-1]} no se identifican categorías de «{category}».")
        extra = [field for field in fields if field != category]
        if extra:
            closing += f' Para «{valor(latest[0], category)}» se reporta ' + '; '.join(
                f'«{field}»: «{valor(latest[0], field)}»' for field in extra) + '.'
    empty = sorted({row['año'] for row in rows for field in fields
                    if not row['celdas'].get(field, '').strip()})
    if empty:
        note = (' La información de ' + ', '.join(map(str, empty))
                + ' presenta datos no disponibles; no se interpretan como cero.')
        narrative += note
        closing += note
    return narrative, closing


def analizar_indicador(section, source='PAQUETE SEGURIDAD', periodos=None):
    """Devuelve párrafos, cierre específico y coordenadas auditables de sus tablas."""
    paragraphs, conclusions, trace = [], [], []
    for table in section['tablas']:
        rows = list(registros(table)) if table.get('filas') else []
        years = sorted({row['año'] for row in rows})
        headers = table['filas'][0] if table['filas'] else []
        fields = [field for field in headers if field != 'Año']
        citation = referencia(table, years, source)
        trace.append({'tabla': table['tabla'], 'ambito': table.get('ambito'),
                      'años_observados': years, 'campos': fields, 'fuente': source})
        if not rows:
            paragraphs.append(f'No se dispone de observaciones con año identificable ({citation}).')
            if table.get('ambito') == 'municipal':
                conclusions.append(f"El cuadro municipal {table['tabla']} no permite establecer una evolución temporal: no identifica los años de las observaciones.")
            continue
        category = next((field for field in fields if normalizar(field) in CATEGORIAS), None)
        if category:
            narrative, closing = leer_categorias(rows, fields, category)
            details, endings = [narrative], [closing]
        else:
            pairs = [leer_campo(rows, field, sujeto_campo(field, section)) for field in fields]
            details, endings = [pair[0] for pair in pairs], [pair[1] for pair in pairs]
        paragraphs.append(' '.join(details) + f' ({citation}).')
        if table.get('ambito') == 'municipal':
            conclusions.append(' '.join(endings) + f" (Información municipal, cuadro {table['tabla']}).")
    if not conclusions:
        conclusions.append('No hay observaciones municipales suficientes para interpretar este indicador.')
    recent = section.get('evaluaciones', {}).get('ultimo_periodo', {})
    target = (periodos or {}).get('ultimo_periodo', {}).get('años_objetivo') or recent.get('años_evaluados', [])
    if recent.get('años_faltantes'):
        label = ' ' + '–'.join(map(str, target)) if target else ''
        conclusions.append('La valoración del periodo reciente' + label + ' es incompleta. '
                           + motivo_publico(recent, section.get('numero')))
    elif recent.get('puntaje') is None and recent.get('motivo'):
        label = ' ' + '–'.join(map(str, target)) if target else ''
        conclusions.append('La valoración del periodo reciente' + label + ' tiene alcance limitado. '
                           + motivo_publico(recent, section.get('numero')))
    # Una cautela común basta; se conservan las cifras y citas de cada cuadro.
    if sum(NOTA_CATEGORIAS in item for item in conclusions) > 1:
        conclusions = [item.replace(' ' + NOTA_CATEGORIAS, '') for item in conclusions]
        conclusions.append(NOTA_CATEGORIAS)
    closing = ' '.join(conclusions)
    return {'parrafos': paragraphs, 'cierre': closing, 'evidencia': trace}
