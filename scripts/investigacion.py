"""Contrato de investigación revisada y narrativa prudente del machote v3.

Validación estructural de procedencia; no verifica vigencia jurídica ni consulta
la web automáticamente. Sin referencias revisadas, los benchmarks quedan null.
"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/investigacion_seguridad.json'
FIELDS = ('titulo', 'url', 'fecha_consulta', 'localizador', 'aplicabilidad', 'revisado_por')


def validar_aporte(aporte, config=None):
    config = config or json.loads(CONFIG.read_text(encoding='utf-8'))
    if not isinstance(aporte, dict) or aporte.get('version') != '1.0' or not isinstance(aporte.get('lineas'), list):
        raise ValueError('La investigación requiere version=1.0 y una lista lineas.')
    expected = {line['id'] for line in config['lineas']}
    definitions = {line['id']: line for line in config['lineas']}
    seen = set()
    for line in aporte['lineas']:
        if not isinstance(line, dict) or line.get('id') not in expected or line['id'] in seen:
            raise ValueError('Línea de investigación desconocida o duplicada.')
        seen.add(line['id'])
        if line.get('estado') != 'verificado' or not isinstance(line.get('analisis'), str) or not line['analisis'].strip():
            raise ValueError('Un aporte requiere estado=verificado y analisis revisado.')
        refs = line.get('referencias')
        if not isinstance(refs, list) or not refs:
            raise ValueError('Un benchmark no puede verificarse sin referencias.')
        for reference in refs:
            if not isinstance(reference, dict) or any(not isinstance(reference.get(f), str) or not reference[f].strip() for f in FIELDS):
                raise ValueError('Referencia incompleta: requiere título, URL, fecha, localizador, aplicabilidad y revisor.')
            url = urlparse(reference['url'])
            if url.scheme != 'https' or not url.netloc or url.username or url.password:
                raise ValueError('La referencia requiere una URL HTTPS sin credenciales.')
            try:
                date.fromisoformat(reference['fecha_consulta'])
            except ValueError as error:
                raise ValueError('Fecha de consulta inválida.') from error
        parts = line.get('apartados', {})
        known = {part['id'] for part in definitions[line['id']].get('apartados', [])}
        if not isinstance(parts, dict) or not set(parts) <= known:
            raise ValueError('Apartados de investigación distintos al machote.')
        for text in parts.values():
            if not isinstance(text, str) or not text.strip() or not any(r['url'] in text for r in refs):
                raise ValueError('Cada apartado requiere texto y una cita de sus referencias declaradas.')
        cited = '\n'.join([line['analisis'], *parts.values()])
        if not all(reference['url'] in cited for reference in refs):
            raise ValueError('El análisis o sus apartados deben citar todas las referencias declaradas.')
    minima = aporte.get('minimos_indicadores', {})
    if not isinstance(minima, dict) or not set(minima) <= {'01', '02', '03'}:
        raise ValueError('Los mínimos de protección civil usan claves 01, 02 y 03.')
    urls = {r['url'] for line in aporte['lineas'] if line['id'] == 'proteccion_civil' for r in line['referencias']}
    for key, item in minima.items():
        if not isinstance(item, dict) or not isinstance(item.get('texto'), str) or not item['texto'].strip():
            raise ValueError(f'Mínimo de indicador {key} sin texto revisado.')
        refs = item.get('referencias')
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in urls for r in refs):
            raise ValueError('Los mínimos deben citar fuentes revisadas de protección civil.')
        if not all(url in item['texto'] for url in refs):
            raise ValueError('El texto de mínimos debe citar sus referencias.')
    return aporte


def integrar(result):
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    aporte = result.get('investigacion_aportada')
    if aporte is not None:
        validar_aporte(aporte, config)
        for field in ('municipio', 'estado'):
            if aporte.get(field) and aporte[field].strip().casefold() != (result.get(field) or '').strip().casefold():
                raise ValueError(f'La investigación corresponde a otro {field}.')
        declared_period = aporte.get('periodo_documental', {})
        for field, key in [('desde', 'año_inicial'), ('hasta', 'año_final')]:
            if field in declared_period and declared_period[field] != result['valores_plantilla'].get(key):
                raise ValueError('La investigación corresponde a otro periodo documental.')
    aporte = aporte or {'version': '1.0', 'lineas': [], 'minimos_indicadores': {}}
    lookup = {line['id']: line for line in aporte['lineas']}
    statuses = []
    values = result['valores_plantilla']
    for definition in config['lineas']:
        supplied = lookup.get(definition['id'])
        values[definition['variable']] = supplied['analisis'] if supplied else None
        parts = deepcopy(supplied.get('apartados', {})) if supplied else {}
        for part in definition.get('apartados', []):
            values[part['variable']] = parts.get(part['id'])
        statuses.append({**definition, 'estado': 'verificado' if supplied else 'pendiente',
                         'contenidos_apartados': parts,
                         'referencias': deepcopy(supplied['referencias']) if supplied else []})
    for i in range(1, 4):
        supplied = aporte.get('minimos_indicadores', {}).get(f'{i:02d}')
        values[f'minimos_indicador_{i:02d}'] = supplied['texto'] if supplied else None
    result['investigacion'] = {'version': '1.0', 'lineas': statuses,
                              'minimos_indicadores': deepcopy(aporte.get('minimos_indicadores', {})),
                              'verificacion': 'Revisión declarada por el aportante; el pipeline valida estructura y referencias, no vigencia ni contenido externo.'}
    missing = [line['id'] for line in statuses if line['estado'] != 'verificado']
    if missing:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'INVESTIGACION_PENDIENTE',
            'detalle': 'Benchmarks sin investigación revisada: ' + ', '.join(missing)})
    missing_minima = [f'{i:02d}' for i in range(1, 4) if values[f'minimos_indicador_{i:02d}'] is None]
    if missing_minima:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'MINIMOS_PROTECCION_CIVIL_PENDIENTES',
            'detalle': 'Mínimos normativos no verificados para los indicadores ' + ', '.join(missing_minima)})
    missing_parts = [part['variable'] for line in config['lineas'] for part in line.get('apartados', [])
                     if values.get(part['variable']) is None]
    if missing_parts:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'APARTADOS_INVESTIGACION_PENDIENTES',
                                      'variables': missing_parts})
    if aporte.get('pendientes_revision'):
        result['validaciones'].append({'nivel': 'revision', 'codigo': 'REVISION_FUENTES_INVESTIGACION',
                                      'detalle': ' '.join(aporte['pendientes_revision'])})
    citations = []
    for line in statuses:
        for reference in line['referencias']:
            citation = referencia_visible(reference)
            if citation not in citations:
                citations.append(citation)
    if citations:
        values['bibliografia'] = '\n\n'.join(
            item for item in [values.get('bibliografia'), *citations] if item)


def referencia_visible(reference):
    """Conserva la cita; reserva aplicabilidad, revisor y controles para el registro técnico."""
    attribution = []
    title = reference['titulo']
    for field in ('autor', 'institucion'):
        value = reference.get(field)
        if isinstance(value, str) and value.strip() and not title.casefold().startswith(value.strip().casefold()):
            if value.strip() not in attribution:
                attribution.append(value.strip())
    prefix = '. '.join(attribution) + '. ' if attribution else ''
    return (f"{prefix}{title}. {reference['url']}. {reference['localizador']}. "
            f"Consulta: {reference['fecha_consulta']}.")


def _indicadores(numbers, preposicion=''):
    """Referencia legible con concordancia y sin abreviaturas técnicas."""
    labels = list(map(str, numbers))
    if len(labels) == 18 and set(labels) == {str(i) for i in range(1, 19)}:
        return (preposicion + ' ' if preposicion else '') + 'los 18 indicadores'
    enumeration = labels[0] if len(labels) == 1 else ', '.join(labels[:-1]) + ' y ' + labels[-1]
    if len(labels) == 1:
        return ('del indicador ' if preposicion == 'de' else
                (preposicion + ' ' if preposicion else '') + 'el indicador ') + enumeration
    return (preposicion + ' ' if preposicion else '') + 'los indicadores ' + enumeration


def narrativas(result, rules):
    """Lectura de consultoría sustentada en resultados; no sustituye la investigación aportada."""
    values = result['valores_plantilla']
    sections = result['indicadores']
    recent = result.get('periodos_evaluacion', {}).get('ultimo_periodo', {}).get('años_objetivo', [])
    recent_text = ' y '.join(map(str, recent)) or 'los dos años consecutivos que cierran el periodo documental'
    start, end = values.get('año_inicial'), values.get('año_final')
    if start is not None and end is not None:
        period_description = f'abarca el periodo {start}–{end}'
    elif start is not None:
        period_description = f'incluye observaciones desde {start}, con el año de cierre por confirmar'
    elif end is not None:
        period_description = f'incluye observaciones hasta {end}, con el año inicial por confirmar'
    else:
        period_description = 'requiere confirmar su delimitación temporal'
    territory = result['municipio'] + (f", {result['estado']}" if result.get('estado') else '')
    pending_recent = [s['numero'] for s in sections if s['evaluaciones']['ultimo_periodo']['puntaje'] is None]
    observed_recent = len(sections) - len(pending_recent)
    values['introduccion_periodo_general'] = (
        f'El diagnóstico de seguridad de {territory} {period_description}. '
        'Su propósito es valorar las capacidades municipales reportadas en protección civil, condiciones del personal '
        'e inteligencia y eficiencia policial. La lectura conjunta permite identificar capacidades documentadas '
        'y asuntos que requieren seguimiento; su alcance depende de los años y variables disponibles en cada indicador.')
    values['introduccion_ultimo_periodo'] = (
        f'La evaluación reciente se concentra en {recent_text}, con un intervalo común para los {len(sections)} indicadores. '
        + (f'La documentación permite sustentar la valoración de {observed_recent} de ellos. '
           if observed_recent else 'Ninguno cuenta con evidencia suficiente para valorar el intervalo completo. ')
        + (('En los restantes ' if observed_recent else 'Por ello, en todos ')
           + 'se aplica la categoría de no acreditación documental, que expresa insuficiencia de evidencia '
           'para ese intervalo y no un juicio de desempeño deficiente. Esta distinción impide trasladar al presente '
           'capacidades acreditadas únicamente en años anteriores.' if pending_recent else
           'Esta cobertura permite una lectura conjunta del intervalo, sin sustituir la revisión de los resultados '
           'y de las condiciones en que opera cada capacidad municipal.'))
    values['enfoque_gobierno'] = (
        'Para la gestión municipal, el diagnóstico distingue entre capacidades documentadas, aspectos que ameritan '
        'revisión y vacíos de información. Esta separación permite orientar el seguimiento sin confundir la falta de '
        'registro con la ausencia de una capacidad. Las propuestas deben vincular cada hallazgo con la evidencia '
        'disponible, las responsabilidades institucionales y las condiciones de su posible aplicación.')
    values['criterio_lectura_graficas'] = (
        'Las tablas presentan los valores y años reportados por las fuentes; las gráficas comparan las calificaciones '
        'documentales de ambos periodos. Una calificación basada en observaciones y otra asignada por falta de '
        'acreditación no tienen el mismo fundamento. Por ello, la distancia entre dos barras debe leerse junto con '
        'sus notas de cobertura: no demuestra por sí sola una mejora o un deterioro del desempeño. '
        'Las asignaciones documentales no sustituyen los valores originales de las tablas.')
    values['bienes_a_proteger'] = (
        'La seguridad física de las personas, la protección de sus derechos y la capacidad de respuesta municipal '
        'constituyen el horizonte de esta evaluación. Los indicadores examinan capacidades relacionadas con esos '
        'propósitos, pero la existencia de un instrumento o una calificación favorable no acredita, por sí sola, '
        'resultados de protección. La valoración de su suficiencia y de su adecuación jurídica requiere contrastar '
        'la evidencia municipal con las referencias pertinentes para el lugar y el periodo analizados.')
    comparable = [s['numero'] for s in sections if s['evaluaciones']['general'].get('referencia_estatal')]
    values['comparacion_estatal_municipal'] = (
        'Las referencias estatales ofrecen un contexto para interpretar los datos municipales, siempre que coincidan '
        'la variable, la unidad de medida y el año. Un conteo municipal no es directamente equiparable al total del '
        'estado, ni la existencia de una capacidad equivale al porcentaje de municipios que la reportan. '
        + (_indicadores(comparable).capitalize() + (' incorpora' if len(comparable) == 1 else ' incorporan')
           + ' referencias estatales explícitas; '
           'sus resultados deben interpretarse de manera individual y no como una clasificación global del municipio.'
           if comparable else 'La información disponible no permite establecer una posición global del municipio frente al estado.'))
    comparable_scores = [s for s in sections if s['evaluaciones']['general']['puntaje'] is not None
                         and s['evaluaciones']['ultimo_periodo']['puntaje'] is not None]
    changes = [s['numero'] for s in comparable_scores
               if s['evaluaciones']['general']['puntaje'] != s['evaluaciones']['ultimo_periodo']['puntaje']]
    values['avances_municipales'] = (
        ('Las calificaciones sustentadas en observaciones difieren entre el periodo general y el reciente '
         + _indicadores(changes, 'en') + '. '
         if changes else 'La evidencia disponible no permite contrastar calificaciones observadas entre ambos periodos. '
         if not comparable_scores else 'Las calificaciones sustentadas en observaciones coinciden entre ambos periodos '
         + _indicadores([s['numero'] for s in comparable_scores], 'en') + '. ')
        + 'El periodo general puede incluir observaciones del intervalo reciente; no se trata necesariamente de dos '
          'etapas independientes. Para identificar avances es preciso revisar las series anuales y la continuidad '
          'de cada capacidad, además de las calificaciones agregadas.')
    for dimension, key in [('proteccion_civil', 'resumen_proteccion_civil'),
                           ('condiciones_del_personal', 'resumen_condiciones_personal'),
                           ('inteligencia_y_eficiencia_policial', 'resumen_inteligencia_eficiencia')]:
        ids = rules['dimensiones'][dimension]
        dimension_sections = [s for s in sections if s['numero'] in ids]
        pending = [s['numero'] for s in dimension_sections if s['evaluaciones']['ultimo_periodo']['puntaje'] is None]
        observed = len(dimension_sections) - len(pending)
        mean = result['contenido_word']['promedios_dimension']['ultimo_periodo'][dimension]
        label = {'proteccion_civil': 'Protección civil',
                 'condiciones_del_personal': 'Condiciones del personal',
                 'inteligencia_y_eficiencia_policial': 'Inteligencia y eficiencia policial'}[dimension]
        grade_text = (f'En {label.lower()}, la calificación documental del intervalo reciente es de {mean}/5. '
                      if mean is not None else f'En {label.lower()}, el promedio documental reciente no está disponible. ')
        if not observed:
            interpretation = (f'Ninguno de los {len(ids)} indicadores dispone de una calificación sustentada en '
                              'observaciones para ese intervalo. El resultado expresa falta de acreditación documental, '
                              'no ausencia de las capacidades evaluadas. ')
        elif pending:
            interpretation = (f'{observed} de los {len(ids)} indicadores cuentan con calificaciones sustentadas en '
                              'observaciones; en los restantes se aplica la base de no acreditación documental. '
                              'El promedio combina, por tanto, evidencia de capacidades y vacíos de información. ')
        else:
            interpretation = (f'Los {observed} indicadores cuentan con calificaciones sustentadas en observaciones. '
                              'Esta cobertura permite examinar la dimensión en conjunto, aunque el promedio no '
                              'acredita por sí mismo resultados de protección o de servicio. ')
        implications = {
            'proteccion_civil': 'El seguimiento debe precisar la continuidad y las condiciones de operación de los instrumentos de protección civil.',
            'condiciones_del_personal': 'La revisión debe relacionar las condiciones reportadas del personal con su cobertura y continuidad, antes de formular medidas de fortalecimiento.',
            'inteligencia_y_eficiencia_policial': 'Para orientar decisiones, conviene examinar conjuntamente la información disponible, las capacidades operativas y los resultados reportados, sin atribuir causalidad entre ellos.',
        }
        values[key] = grade_text + interpretation + implications[dimension]
    values['tendencia_general'] = (
        'No es posible establecer una trayectoria reciente con las calificaciones observadas disponibles. '
        if not comparable_scores else
        'Las diferencias entre calificaciones agregadas no bastan para establecer una tendencia sostenida. '
        if changes else
        'La coincidencia de calificaciones entre periodos no demuestra estabilidad en todas las variables evaluadas. ')
    values['tendencia_general'] += (
        'Una conclusión temporal requiere series con definiciones y unidades comparables, cobertura suficiente y '
        'revisión de los cambios anuales. Hasta contar con esa base, corresponde distinguir los resultados '
        'documentados de las hipótesis sobre su evolución.')
    strong = [s['numero'] for s in sections if s['evaluaciones']['ultimo_periodo']['puntaje'] is not None
              and s['evaluaciones']['ultimo_periodo']['puntaje'] >= 4]
    weak = [s['numero'] for s in sections if s['evaluaciones']['ultimo_periodo']['puntaje'] is not None
            and s['evaluaciones']['ultimo_periodo']['puntaje'] <= 2]
    pending = [s['numero'] for s in sections if s['evaluaciones']['ultimo_periodo']['puntaje'] is None]
    values['fortalezas_seguridad'] = (
        _indicadores(strong).capitalize() + (' obtiene una calificación observada' if len(strong) == 1 else ' obtienen calificaciones observadas')
        + ' de 4 o 5 en el intervalo reciente. Se trata de resultados favorables conforme a los criterios de esta evaluación. '
        'Conviene verificar la continuidad de las capacidades que los sustentan; no equivalen a evidencia de reducción del delito.'
        if strong else 'La evidencia del intervalo reciente no identifica indicadores con calificaciones observadas de 4 o 5. '
        'Este resultado no permite concluir que el municipio carezca de fortalezas, particularmente cuando la '
        'cobertura documental es incompleta.')
    values['areas_mejora_seguridad'] = (
        _indicadores(weak).capitalize() + (' registra una calificación observada' if len(weak) == 1 else ' registran calificaciones observadas')
        + ' de 1 o 2 en el intervalo reciente. Conviene revisar las condiciones reportadas que sustentan ese resultado. '
        if weak else 'No se identifican calificaciones observadas de 1 o 2 en el intervalo reciente. '
        'Esto no descarta necesidades de mejora fuera del alcance de la evidencia disponible. ')
    if pending:
        values['areas_mejora_seguridad'] += (_indicadores(pending, 'en').capitalize()
                                           + ', es necesario completar la evidencia para distinguir una carencia '
                                           'de registro de una posible limitación institucional.')
    recommendations = []
    if pending:
        recommendations.append('La primera tarea es completar la evidencia ' + _indicadores(pending, 'de')
                               + ', conservando la correspondencia entre año, variable y unidad de medida. '
                               'Conviene acordar con las áreas responsables qué registros faltan y cuándo podrán revisarse.')
    if weak:
        recommendations.append(_indicadores(weak, 'para').capitalize()
                               + ', se recomienda examinar las condiciones asociadas a las calificaciones bajas y '
                               'definir medidas de seguimiento proporcionales a los hallazgos comprobados.')
    if strong:
        recommendations.append('En los resultados favorables, el seguimiento debe concentrarse en verificar la '
                               'continuidad de las capacidades y documentar las condiciones que permiten sostenerlas.')
    if not recommendations:
        recommendations.append('Se recomienda revisar los hallazgos con las áreas municipales responsables y '
                               'establecer una agenda de seguimiento de las capacidades documentadas.')
    recommendations.append('Antes de adoptar medidas operativas, presupuestarias o normativas, es necesario '
                           'contrastar su pertinencia con la evidencia municipal y las referencias aplicables; '
                           'las calificaciones no sustituyen esa valoración.')
    values['recomendaciones_gobierno'] = '\n\n'.join(recommendations)
    values['justificacion_prioridades'] = (
        'Se propone ordenar el seguimiento según la solidez de la evidencia y la naturaleza del hallazgo: '
        'completar información donde no es posible valorar una capacidad, examinar las condiciones asociadas a '
        'resultados desfavorables y verificar la continuidad de los resultados favorables. Esta distinción evita '
        'tratar como equivalentes un vacío documental y una limitación observada. La prioridad de una intervención '
        'específica requiere, además, valorar su alcance, viabilidad y pertinencia para el municipio.')
