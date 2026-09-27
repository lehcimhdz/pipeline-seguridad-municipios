"""Textos de apoyo y controles del contenido destinado al lector de la medición."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/redaccion_consultoria.json'
PERIODOS = {'general': 'Periodo general', 'ultimo_periodo': 'Último periodo'}


def cargar_estilo():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def enumerar(values):
    items = [str(value) for value in values]
    return ', '.join(items[:-1]) + ' y ' + items[-1] if len(items) > 1 else (items[0] if items else '')


def periodo_texto(years):
    years = sorted(set(years))
    return (str(years[0]) if len(years) == 1 else f'{years[0]}–{years[-1]}') if years else 'sin periodo confirmado'


def comprobar_texto(text, ubicacion='texto', config=None):
    """Rechaza filtraciones técnicas; no certifica veracidad ni calidad literaria."""
    if not isinstance(text, str):
        return
    config = config or cargar_estilo()
    for name, pattern in config['patrones_no_publicables'].items():
        if re.search(pattern, text, re.I):
            raise ValueError(f'Redacción no publicable en {ubicacion}: {name}.')
    if re.search(r'\b[A-ZÁÉÍÓÚÑ]{2,}(?:_[A-Z0-9ÁÉÍÓÚÑ]+)+\b', text):
        raise ValueError(f'Redacción no publicable en {ubicacion}: código interno de revisión.')


def validar_publicacion(result):
    """Revisa la superficie editorial sin modificar evidencia ni validaciones."""
    config = cargar_estilo()
    count = 0

    def check(value, location):
        nonlocal count
        if isinstance(value, str):
            comprobar_texto(value, location, config)
            count += 1

    for key, value in result.get('valores_plantilla', {}).items():
        if isinstance(value, list):
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    check(item, key)
                    continue
                for field in ('titulo', 'fuente'):
                    check(item.get(field), f'{key}[{index}].{field}')
                for category in item.get('categorias', []):
                    check(category, key)
                for row in item.get('filas', []):
                    for cell in row:
                        check(cell, key)
        else:
            check(value, key)
    content = result.get('contenido_word', {})
    for key in ('titulo', 'aviso_borrador', 'periodo'):
        check(content.get(key), f'contenido_word.{key}')
    for note in content.get('notas_alcance', []):
        check(note, 'notas_alcance')
    for key, value in content.get('textos_pendientes', {}).items():
        check(value, key)
    return {'perfil_redaccion': config['perfil'], 'version_redaccion': config['version'],
            'textos_publicables_verificados': count, 'referencias_tecnicas_en_textos': 0}


def titulo_tabla(table):
    scope = 'municipal' if table.get('ambito') == 'municipal' else 'estatal'
    return f"Información {scope}. Cuadro {table.get('tabla', table.get('tabla_fuente', ''))} del Paquete Seguridad."


def fuente_grafica(section):
    missing = [PERIODOS[p].lower() for p in PERIODOS
               if section['evaluaciones'][p]['puntaje'] is None]
    text = 'Fuente: elaboración propia con el Paquete Seguridad y su Anexo. Escala de 1 a 5.'
    if missing:
        text += ' La valoración de ' + enumerar(missing) + ' permanece pendiente y no se representa como cero.'
    return text


def texto_pendiente(key):
    if key.startswith('calificacion_'):
        return 'Pendiente'
    return 'La información disponible aún no permite completar la valoración de este apartado.'


def bibliografia_documental(result):
    """Sólo las dos fuentes autorizadas; sus huellas permanecen en result.fuentes."""
    municipality = result['municipio']
    titles = {' paquete seguridad.docx': 'Paquete Seguridad', ' anexo.docx': 'Anexo de medición municipal'}
    refs = []
    for source in result.get('fuentes', []):
        filename = Path(source.get('archivo', '')).name.casefold()
        title = next((label for suffix, label in titles.items() if filename.endswith(suffix)), None)
        if title:
            refs.append(f'{title} de {municipality}. Documentación proporcionada para esta medición.')
    return list(dict.fromkeys(refs)) or [
        f'Paquete Seguridad y Anexo de medición municipal de {municipality}. Documentación de referencia de esta medición.'
    ]


def notas_alcance(result):
    codes = {item['codigo'] for item in result.get('validaciones', [])}
    notes = []
    if 'COBERTURA_EDICIONES' in codes:
        notes.append('Los años identifican las observaciones de los documentos proporcionados; la cobertura temporal varía entre indicadores.')
    if 'DIFERENCIA_ANEXO' in codes:
        notes.append('Las diferencias entre el Paquete Seguridad y el Anexo requieren conciliación antes de cerrar la medición.')
    if 'IDENTIDAD_NO_CONFIRMADA' in codes:
        notes.append('La identificación del municipio y del estado requiere confirmación documental.')
    if 'INDICADOR_PENDIENTE' in codes:
        notes.append('Las valoraciones pendientes se conservarán sin calificación hasta disponer de información suficiente; no se interpretan como desempeño desfavorable.')
    if codes:
        notes.append('Versión sujeta a revisión de los hallazgos, las comparaciones y las prioridades propuestas.')
    return notes
