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
    refs = list({r['url']: r for line in statuses for r in line['referencias']}.values())
    if refs:
        values['bibliografia'] += '\n\n' + '\n\n'.join(
            f"{r['titulo']}. {r['url']} — {r['localizador']}. Consulta: {r['fecha_consulta']}. "
            f"Aplicabilidad: {r['aplicabilidad']}. Revisión: {r['revisado_por']}." for r in refs)


def narrativas(result, rules):
    values = result['valores_plantilla']
    sections = result['indicadores']
    recent = result.get('periodos_evaluacion', {}).get('ultimo_periodo', {}).get('años_objetivo', [])
    recent_text = ' y '.join(map(str, recent)) or 'los dos años consecutivos de cierre documental'
    values['introduccion_periodo_general'] = (
        f"El periodo documental de {result['municipio']}, {result.get('estado', '')}, comprende "
        f"{values.get('año_inicial', 'el inicio observado')}–{values.get('año_final', 'el cierre observado')}. "
        'La interpretación general integra las capacidades reportadas y sus cambios, con los años faltantes identificados en cada indicador.')
    values['introduccion_ultimo_periodo'] = (
        f'El último periodo corresponde a {recent_text}, con un mismo intervalo para los 18 indicadores. '
        'Cuando falta alguno de esos años, se conserva el puntaje observado como no disponible y se emite '
        'la calificación documental de no acreditación. No se arrastra la nota de otro año ni se atribuye desempeño deficiente.')
    values['enfoque_gobierno'] = (
        'La información se examina para identificar capacidades reportadas, carencias documentales y acciones de seguimiento. '
        'Las propuestas se relacionan con los hallazgos de cada indicador y con las referencias que se desarrollan a continuación.')
    values['criterio_lectura_graficas'] = (
        'Las tablas conservan los valores y años de las fuentes; los análisis y cierres explican sus cambios y limitaciones. '
        'Las gráficas muestran las calificaciones documentales asignadas de ambos periodos; '
        'su nota distingue el puntaje observado de la base por no acreditación. Esta base no es un cero ni un dato imputado '
        'a las tablas. Diferencias de cobertura no prueban cambios de desempeño. Las series originales se conservan en las tablas.')
    values['bienes_a_proteger'] = (
        'La medición examina la protección civil, las condiciones del personal y la información y eficiencia policial '
        'como aspectos relacionados con la seguridad física, humana y el respeto de los derechos humanos. '
        'La existencia de capacidades declaradas y sus puntajes internos no acredita por sí sola resultados de protección '
        'ni cumplimiento jurídico; los estándares se revisan por separado en los benchmarks.')
    comparable = [s['numero'] for s in sections if s['evaluaciones']['general'].get('referencia_estatal')]
    values['comparacion_estatal_municipal'] = (
        'El documento conserva las tablas municipales y estatales con sus ámbitos y coordenadas originales. '
        'Una comparación sustantiva requiere la misma variable, unidad y año; no se equipara un conteo municipal con '
        'un total estatal ni una respuesta de existencia con un porcentaje estatal. '
        + ('Los cálculos registran referencias estatales explícitas en los indicadores ' + ', '.join(map(str, comparable)) + '.'
           if comparable else 'No se establece una posición global del municipio frente al estado con la información actual.'))
    comparable_scores = [s for s in sections if s['evaluaciones']['general']['puntaje'] is not None
                         and s['evaluaciones']['ultimo_periodo']['puntaje'] is not None]
    changes = [s['numero'] for s in comparable_scores
               if s['evaluaciones']['general']['puntaje'] != s['evaluaciones']['ultimo_periodo']['puntaje']]
    values['avances_municipales'] = (
        ('Hay diferencias entre el puntaje general y el del último periodo en los indicadores ' + ', '.join(map(str, changes)) + '. '
         if changes else 'No hay pares de puntajes general/reciente disponibles para comparar. '
         if not comparable_scores else 'Los puntajes comparables coinciden entre ambos periodos. ')
        + 'El periodo general incluye observaciones del reciente; esta comparación no demuestra por sí sola una '
          'tendencia sostenida ni una mejora causal. Los años y valores originales deben revisarse en cada indicador.')
    for dimension, key in [('proteccion_civil', 'resumen_proteccion_civil'),
                           ('condiciones_del_personal', 'resumen_condiciones_personal'),
                           ('inteligencia_y_eficiencia_policial', 'resumen_inteligencia_eficiencia')]:
        ids = rules['dimensiones'][dimension]
        pending = [s['numero'] for s in sections if s['numero'] in ids and s['evaluaciones']['ultimo_periodo']['puntaje'] is None]
        mean = result['contenido_word']['promedios_dimension']['ultimo_periodo'][dimension]
        label = {'proteccion_civil': 'Protección civil',
                 'condiciones_del_personal': 'Condiciones del personal',
                 'inteligencia_y_eficiencia_policial': 'Inteligencia y eficiencia policial'}[dimension]
        values[key] = (f"{label}: promedio documental {mean}/5. "
                       f"{len(ids) - len(pending)} de {len(ids)} indicadores con puntaje observado en el último periodo. "
                       + ('La base de no acreditación se asignó a los indicadores ' + ', '.join(map(str, pending)) + '. ' if pending else '')
                       + 'Este valor no sustituye la evaluación de resultados ni el benchmark externo.')
    values['tendencia_general'] = 'La tendencia general requiere revisar series compatibles y cobertura temporal. ' + values['avances_municipales']
    strong = [s['numero'] for s in sections if s['evaluaciones']['ultimo_periodo']['puntaje'] is not None
              and s['evaluaciones']['ultimo_periodo']['puntaje'] >= 4]
    weak = [s['numero'] for s in sections if s['evaluaciones']['ultimo_periodo']['puntaje'] is not None
            and s['evaluaciones']['ultimo_periodo']['puntaje'] <= 2]
    pending = [s['numero'] for s in sections if s['evaluaciones']['ultimo_periodo']['puntaje'] is None]
    values['fortalezas_seguridad'] = (
        'Los indicadores con puntaje interno de 4 o 5 en el último periodo son ' + ', '.join(map(str, strong)) + '. '
        if strong else 'No hay indicadores con puntaje interno de 4 o 5 confirmado para el último periodo. ')
    values['fortalezas_seguridad'] += 'Estos resultados orientan la revisión de capacidades a conservar; no acreditan efectos sobre el delito.'
    values['areas_mejora_seguridad'] = (
        'Los indicadores con puntaje interno de 1 o 2 en el último periodo son ' + ', '.join(map(str, weak)) + '. '
        if weak else 'No hay indicadores con puntaje interno de 1 o 2 confirmado para el último periodo. ')
    if pending:
        values['areas_mejora_seguridad'] += ('Los indicadores ' + ', '.join(map(str, pending))
                                           + ' tienen nota documental de no acreditación y puntaje observado no disponible; '
                                           'falta de datos no equivale a desempeño deficiente.')
    values['recomendaciones_gobierno'] = (
        ('Completar y clasificar la evidencia de los indicadores ' + ', '.join(map(str, pending)) + ' antes de priorizar intervenciones. '
         if pending else 'Conservar la trazabilidad de todos los indicadores y revisar los hallazgos con el municipio. ')
        + 'Contrastar capacidades observadas con los benchmarks revisados y definir responsables de seguimiento. '
          'Las decisiones operativas, presupuestarias o normativas requieren una revisión específica; no se deducen automáticamente de los puntajes.')
    values['justificacion_prioridades'] = (
        'Las prioridades se fundamentan en los valores documentales, los criterios internos y las revisiones pendientes. '
        'Las referencias externas deben sustentar su aplicabilidad al municipio y al periodo. '
        'Este bloque no genera una plataforma electoral ni explica causas sin evidencia adicional.')
