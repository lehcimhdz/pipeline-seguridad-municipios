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
    for key in ('titulo', 'periodo'):
        check(content.get(key), f'contenido_word.{key}')
    for note in content.get('notas_alcance', []):
        check(note, 'notas_alcance')
    for key, value in content.get('textos_pendientes', {}).items():
        check(value, key)
    return {'perfil_redaccion': config['perfil'], 'version_redaccion': config['version'],
            'textos_publicables_verificados': count, 'referencias_tecnicas_en_textos': 0}
