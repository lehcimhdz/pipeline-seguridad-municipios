"""Redacción publicable y controles de separación entre informe y trazabilidad."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/redaccion_consultoria.json'
PERIODOS = {'general': 'Periodo general', 'ultimo_periodo': 'Último periodo'}
URL = re.compile(r'https?://[^\s<>]+', re.I)


def cargar_estilo():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def enumerar(values):
    items = [str(v) for v in values]
    return ', '.join(items[:-1]) + ' y ' + items[-1] if len(items) > 1 else (items[0] if items else '')


def periodo_texto(years):
    years = sorted(set(years))
    return str(years[0]) if len(years) == 1 else f'{years[0]}–{years[-1]}' if years else 'periodo sin confirmar'


def comprobar_texto(text, ubicacion='texto', config=None):
    """Control léxico acotado: no certifica calidad literaria ni verdad factual."""
    config = config or cargar_estilo()
    visible = URL.sub('', text)
    for name, pattern in config['patrones_no_publicables'].items():
        if re.search(pattern, visible, re.I):
            raise ValueError(f'Redacción no publicable en {ubicacion}: {name}. Revisar el texto de origen.')
    if re.search(r'\b[A-ZÁÉÍÓÚÑ]{2,}(?:_[A-Z0-9ÁÉÍÓÚÑ]+)+\b', visible):
        raise ValueError(f'Redacción no publicable en {ubicacion}: código interno de revisión.')


def validar_publicacion(result):
    """Sólo inspecciona contenido para el lector; preserva datos y bitácora internos."""
    config = cargar_estilo()
    count = 0
    def check(value, location):
        nonlocal count
        if isinstance(value, str):
            comprobar_texto(value, location, config)
            count += 1
    for key, value in result['valores_plantilla'].items():
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    for field in ('titulo', 'fuente'):
                        check(item.get(field), f'{key}[{i}].{field}')
                    for category in item.get('categorias', []):
                        check(category, key)
                    for r, row in enumerate(item.get('filas', [])):
                        for c, cell in enumerate(row):
                            check(cell, f'{key}[{i}].filas[{r}][{c}]')
        else:
            check(value, key)
    content = result['contenido_word']
    for key in ('titulo', 'aviso_borrador', 'periodo'):
        check(content.get(key), 'contenido_word.' + key)
    for note in content.get('notas_alcance', []):
        check(note, 'notas_alcance')
    for key, value in content.get('textos_pendientes', {}).items():
        check(value, key)
    return {'perfil_redaccion': config['perfil'], 'version_redaccion': config['version'],
            'textos_publicables_verificados': count, 'referencias_tecnicas_en_textos': 0}


def motivo_publico(evaluation, numero=None):
    missing = evaluation.get('años_faltantes_por_ambito', {})
    if missing:
        parts = [f"{('municipales' if scope == 'municipal' else 'estatales')} de {enumerar(years)}"
                 for scope, years in missing.items() if years]
        if parts:
            return 'Faltan observaciones ' + '; y '.join(parts) + ' para completar la evaluación del periodo.'
    if evaluation.get('años_faltantes'):
        return 'Falta información de ' + enumerar(evaluation['años_faltantes']) + ' para completar la evaluación del periodo.'
    reason = evaluation.get('motivo', '')
    if 'homologación, denominadores' in reason:
        requirements = {
            4: 'relacionar el personal de seguridad con una población de referencia del mismo año',
            8: 'comprobar la frecuencia de entrega de uniformes, la cobertura del personal y su comparabilidad con la información estatal',
            9: 'relacionar los equipos disponibles con el número de elementos y distinguir existencias, entregas y disponibilidad operativa',
            14: 'comparar la dotación de cámaras por habitante con la referencia estatal y comprobar las condiciones de operación y monitoreo',
            17: 'precisar las bases de los porcentajes de egreso y las tasas de fallecimiento para valorar la reposición del estado de fuerza',
            18: 'relacionar las puestas a disposición con la incidencia delictiva y distinguir los procedimientos penales de los administrativos',
        }
        if numero in requirements:
            return 'La valoración requiere ' + requirements[numero] + '.'
    if 'ficha' in reason or 'criterio inequívoco' in reason:
        return 'La combinación de resultados disponible requiere precisar el criterio de evaluación antes de emitir una valoración de desempeño.'
    if any(word in reason.lower() for word in ('duplicad', 'más de una observación', 'conciliación')):
        return 'Es necesario conciliar las observaciones correspondientes a un mismo año antes de establecer comparaciones.'
    if any(word in reason.lower() for word in ('vacío', 'fuera de rango', 'no válido')):
        return 'La valoración requiere aclarar los valores faltantes o inconsistentes de la información proporcionada.'
    if reason:
        # Una explicación sustantiva breve puede conservarse, nunca un mensaje interno.
        try:
            comprobar_texto(reason)
        except ValueError:
            pass
        else:
            return reason.rstrip('.') + '.'
    return 'La información disponible resulta insuficiente para determinar el desempeño del indicador.'


def nota_indicador(section, period):
    evaluation = section['evaluaciones'][period]
    detail = ('NO ACREDITADO por información insuficiente'
              if evaluation['puntaje'] is None else 'valoración sustentada en la información disponible')
    return f"{PERIODOS[period]}: {evaluation['puntaje_asignado']}/5 — {detail}."


def titulo_tabla(table):
    scope = 'municipal' if table['ambito'] == 'municipal' else 'estatal'
    return f"Información {scope}. Cuadro {table['tabla']} del compendio de seguridad."


def fuente_grafica(section):
    missing = [PERIODOS[p].lower() for p in PERIODOS if section['evaluaciones'][p]['puntaje'] is None]
    base = 'Fuente: elaboración propia a partir de la documentación de seguridad. Escala de 1 a 5.'
    if missing:
        base += (' En ' + enumerar('el ' + label for label in missing)
                 + ', se aplica la base por información insuficiente; no expresa un desempeño observado.')
    return base + ' Las diferencias entre periodos deben interpretarse considerando la cobertura de la información.'


def bibliografia_documental(result):
    descriptions = {
        ' anexo.docx': 'Anexo de medición municipal',
        ' paquete seguridad.docx': 'Compendio de seguridad municipal',
        ' paquete gobierno abierto y buen gobierno.docx': 'Compendio de gobierno abierto y buen gobierno',
        ' paquete desarrollo urbano sostenible y derechos humanos conexos.docx': 'Compendio de desarrollo urbano sostenible y derechos humanos conexos',
    }
    refs = []
    for source in result.get('fuentes', []):
        filename = source.get('archivo', '').lower()
        title = next((title for suffix, title in descriptions.items() if filename.endswith(suffix)), None)
        if title:
            refs.append(f"{title}. Documentación de {result['municipio']} proporcionada para este diagnóstico.")
        elif source.get('proveedor'):
            ref = f"{source['proveedor']}. Información estadística complementaria."
            if source.get('pagina_oficial'):
                ref += ' ' + source['pagina_oficial']
            refs.append(ref)
        elif source.get('nombre') or source.get('titulo'):
            refs.append(source.get('titulo') or source['nombre'])
        else:
            refs.append('Documentación complementaria proporcionada para el diagnóstico municipal.')
    return list(dict.fromkeys(refs)) or ['Documentación de seguridad proporcionada para el diagnóstico municipal.']


def texto_pendiente(key):
    if key.startswith('minimos_'):
        return 'La determinación de los requisitos aplicables queda sujeta a la revisión de las fuentes normativas.'
    if key.startswith(('benchmark_', 'investigacion_')):
        return 'Este apartado requiere completar y revisar las referencias antes de formular conclusiones.'
    return 'La información necesaria para desarrollar este apartado se encuentra pendiente de revisión.'


def notas_alcance(result):
    codes = {v['codigo'] for v in result.get('validaciones', [])}
    notes = []
    if 'COBERTURA_EDICIONES' in codes:
        notes.append('Los años corresponden a las etiquetas de las fuentes consultadas. Antes de cerrar la evaluación, debe confirmarse su correspondencia con el año de referencia de cada levantamiento.')
    if codes & {'DIFERENCIA_ANEXO'}:
        notes.append('Se identificaron diferencias entre el compendio de seguridad y su anexo que requieren conciliación.')
    if codes & {'IDENTIDAD_NO_CONFIRMADA'}:
        notes.append('La identificación territorial de la documentación debe confirmarse antes de su aprobación.')
    if codes & {'INVESTIGACION_PENDIENTE', 'APARTADOS_INVESTIGACION_PENDIENTES', 'MINIMOS_PROTECCION_CIVIL_PENDIENTES', 'REVISION_FUENTES_INVESTIGACION'}:
        notes.append('Las referencias normativas y de investigación requieren revisión de vigencia, pertinencia y aplicación al municipio y al periodo estudiado.')
    if codes & {'PUNTAJE_NO_ACREDITADO', 'INDICADOR_PENDIENTE'}:
        notes.append('Las calificaciones por información insuficiente deberán revisarse al completar la evidencia señalada en cada indicador. Su asignación no acredita un desempeño desfavorable.')
    if codes:
        notes.append('La versión de trabajo queda sujeta a la revisión sustantiva de los hallazgos, las comparaciones y las recomendaciones antes de su aprobación.')
    return notes
