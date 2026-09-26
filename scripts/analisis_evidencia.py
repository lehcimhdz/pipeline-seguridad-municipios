"""Lecturas descriptivas de las tablas; no infiere causas ni suma categorías."""
from calificar import normalizar, numero
from documentos import registros

CATEGORIAS = {'tema', 'tema impartido', 'equipamiento', 'elementos del uniforme',
              'evento', 'instrumento'}
SI = {'si', 'si existe', 'existe'}
NO = {'no', 'no existe'}


def formato_numero(value):
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def variacion(first, last, field):
    difference = last - first
    if difference == 0:
        return 'sin diferencia entre ambos valores'
    if 'porcentaje' in normalizar(field):
        unit = 'punto porcentual' if abs(difference) == 1 else 'puntos porcentuales'
    else:
        unit = 'unidad del campo' if abs(difference) == 1 else 'unidades del campo'
    sign = '+' if difference > 0 else '−'
    return f'variación de {sign}{formato_numero(abs(difference))} {unit}'


def referencia(table, years, source):
    labels = ', '.join(map(str, years)) or 'sin año válido'
    return f"{source}, tabla {table['tabla']} ({table.get('ambito') or 'ámbito sin clasificar'}), años {labels}"


def valor(row, field):
    raw = row['celdas'].get(field, '').strip()
    return raw or 'dato vacío'


def leer_campo(rows, field):
    """Compara extremos sólo si hay una observación y valor comparable por año."""
    years = sorted({row['año'] for row in rows})
    by_year = {year: [row for row in rows if row['año'] == year] for year in years}
    if any(len(items) != 1 for items in by_year.values()):
        return (f'«{field}» contiene varias filas en un mismo año; su comparación exige conciliación.',
                f'«{field}» requiere conciliar observaciones del mismo año antes de interpretar cambios.')
    ordered = [by_year[year][0] for year in years]
    first, last = ordered[0], ordered[-1]
    present = [row['año'] for row in ordered if normalizar(valor(row, field)) in SI]
    absent = [row['año'] for row in ordered if normalizar(valor(row, field)) in NO]
    missing = [row['año'] for row in ordered if not row['celdas'].get(field, '').strip()]
    if present or absent:
        parts = []
        if present:
            parts.append('presencia declarada en ' + ', '.join(map(str, present)))
        if absent:
            parts.append('ausencia declarada en ' + ', '.join(map(str, absent)))
        unknown = [row for row in ordered if row['año'] not in present + absent]
        if unknown:
            parts.append('respuesta sin clasificar en ' + ', '.join(
                f"{row['año']} («{valor(row, field)}»)" for row in unknown))
        narrative = f'«{field}»: ' + '; '.join(parts) + '.'
        closing = f"La última respuesta documentada de «{field}» es «{valor(last, field)}» ({last['año']})"
        if len(ordered) > 1:
            previous = ordered[-2]
            closing += f", frente a «{valor(previous, field)}» en {previous['año']}"
        return narrative, closing + '; esto describe la existencia reportada, no su funcionamiento efectivo.'
    numbers = [numero(row['celdas'].get(field, '')) for row in ordered]
    if len(ordered) > 1 and numbers[0] is not None and numbers[-1] is not None:
        narrative = (f"«{field}» pasó de {valor(first, field)} ({first['año']}) "
                     f"a {valor(last, field)} ({last['año']}); {variacion(numbers[0], numbers[-1], field)}.")
        if len(ordered) > 2 and numbers[-2] is not None:
            previous = ordered[-2]
            closing = (f"Entre las dos últimas observaciones documentadas, «{field}» pasó de "
                       f"{valor(previous, field)} ({previous['año']}) a {valor(last, field)} ({last['año']}); "
                       + variacion(numbers[-2], numbers[-1], field) + '.')
        else:
            closing = narrative
    else:
        sample = ordered[-2:]
        narrative = f'«{field}»: ' + '; '.join(
            f"{row['año']} = «{valor(row, field)}»" for row in sample) + '.'
        closing = narrative + (' No hay dos extremos numéricos comparables para calcular una variación.'
                               if any(value is not None for value in numbers) else '')
    if missing:
        note = ' Celdas vacías en ' + ', '.join(map(str, missing)) + '; no equivalen a cero.'
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
    sample = 'muestra de registros: ' if len(latest) > 3 else 'registros: '
    narrative = (f"En {years[-1]} se registran {len(names)} etiquetas distintas en «{category}»; "
                 + sample + '; '.join(details) + '.')
    if len(years) > 1:
        first_names = {row['celdas'][category].strip() for row in rows
                       if row['año'] == years[0] and row['celdas'].get(category, '').strip()}
        narrative += (f" En {years[0]} aparecen {len(first_names)} etiquetas distintas. "
                      'Los nombres se conservan sin homologar; esas cantidades describen el catálogo reportado, no su cobertura ni efectividad.')
    numeric_fields = [field for field in fields if field != category
                      and any(numero(row['celdas'].get(field, '')) is not None for row in latest)]
    if numeric_fields:
        field = next((field for field in numeric_fields if normalizar(field) == 'total'), numeric_fields[0])
        candidates = [row for row in latest if numero(row['celdas'].get(field, '')) is not None]
        chosen = max(candidates, key=lambda row: numero(row['celdas'][field]))
        maximum = numero(chosen['celdas'][field])
        tied = sum(numero(row['celdas'][field]) == maximum for row in candidates)
        label = 'uno de los valores máximos reportados' if tied > 1 else 'el valor máximo reportado'
        closing = (f"En {years[-1]}, «{valor(chosen, category)}» presenta {label} "
                   f"de «{field}»: {valor(chosen, field)}")
        percentage = next((key for key in fields if normalizar(key) == 'porcentaje' and key != field), None)
        if percentage:
            closing += f"; el porcentaje consignado en esa fila es {valor(chosen, percentage)}"
        closing += '. Las filas no se suman: las categorías podrían compartir personas o conceptos.'
    else:
        closing = (f"Los registros de {years[-1]} identifican {len(names)} etiquetas de «{category}», "
                   'entre ellas ' + ', '.join('«' + name + '»' for name in names[:3]) + '.')
        extra = [field for field in fields if field != category]
        if extra:
            closing += ' Para la primera categoría se reporta ' + '; '.join(
                f'«{field}»: «{valor(latest[0], field)}»' for field in extra) + '.'
    empty = sorted({row['año'] for row in rows for field in fields
                    if not row['celdas'].get(field, '').strip()})
    if empty:
        note = (' Hay campos vacíos en registros de ' + ', '.join(map(str, empty))
                + '; deben clasificarse y no se convierten en cero.')
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
            paragraphs.append(f'{citation}: no contiene observaciones con año válido.')
            if table.get('ambito') == 'municipal':
                conclusions.append(f"La tabla municipal {table['tabla']} no permite describir cambios: carece de observaciones con año válido.")
            continue
        category = next((field for field in fields if normalizar(field) in CATEGORIAS), None)
        if category:
            narrative, closing = leer_categorias(rows, fields, category)
            details, endings = [narrative], [closing]
        else:
            pairs = [leer_campo(rows, field) for field in fields]
            details, endings = [pair[0] for pair in pairs], [pair[1] for pair in pairs]
        paragraphs.append(f'Fuente: {citation}. ' + ' '.join(details))
        if table.get('ambito') == 'municipal':
            conclusions.extend(f"Tabla municipal {table['tabla']}: {ending}" for ending in endings)
    if not conclusions:
        conclusions.append('No hay observaciones municipales suficientes para interpretar este indicador.')
    recent = section.get('evaluaciones', {}).get('ultimo_periodo', {})
    target = (periodos or {}).get('ultimo_periodo', {}).get('años_objetivo') or recent.get('años_evaluados', [])
    if recent.get('años_faltantes'):
        conclusions.append('La lectura de estos datos no completa el intervalo reciente '
                           + '–'.join(map(str, target)) + ': faltan observaciones de '
                           + ', '.join(map(str, recent['años_faltantes'])) + '.')
    elif recent.get('puntaje') is None and recent.get('motivo'):
        conclusions.append('La calificación reciente permanece pendiente: ' + recent['motivo'])
    closing = f"Para «{section['nombre']}», la evidencia municipal muestra lo siguiente. " + ' '.join(conclusions)
    return {'parrafos': paragraphs, 'cierre': closing, 'evidencia': trace}
