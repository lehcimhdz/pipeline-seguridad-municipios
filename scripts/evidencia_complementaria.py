"""Carga evidencia revisada sin convertir definiciones del censo en datos municipales."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from datetime import date
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def huella_objeto(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def vacia(municipio, estado):
    return {'version': '1.0', 'municipio': municipio, 'estado': estado,
            'fuentes': [], 'poblacion': [], 'observaciones': {}}


def validar(value, municipio, estado):
    if value.get('version') != '1.0' or value.get('municipio') != municipio or value.get('estado') != estado:
        raise ValueError('La evidencia complementaria no corresponde al municipio, estado o versión.')
    sources = {}
    for source in value.get('fuentes', []):
        identifier = source.get('id')
        if not identifier or identifier in sources or not source.get('titulo'):
            raise ValueError('Fuente complementaria sin identidad única o título.')
        path = Path(source['archivo'])
        if not path.is_absolute():
            path = ROOT / path
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source.get('sha256'):
            raise ValueError('Cambió una fuente complementaria: revisar sus observaciones.')
        sources[identifier] = source

    def provenance(item):
        if (item.get('fuente') not in sources or not item.get('localizador')
                or item.get('revision') != 'verificada'):
            raise ValueError('Cada dato complementario exige fuente, localizador y revisión verificada.')

    seen = set()
    methods = {}
    for item in value.get('poblacion', []):
        provenance(item)
        scope, year = item.get('ambito'), item.get('anio')
        if scope not in ('municipal', 'estatal') or type(year) is not int:
            raise ValueError('Población sin ámbito o año válido.')
        key = scope, year
        if key in seen:
            raise ValueError('Hay dos poblaciones para un mismo ámbito y año.')
        seen.add(key)
        try:
            number = Decimal(str(item['valor']))
            if isinstance(item['valor'], bool) or not number.is_finite() or number <= 0:
                raise ValueError('La población debe ser positiva.')
        except (InvalidOperation, KeyError) as exc:
            raise ValueError('Población inválida.') from exc
        if (item.get('metodo') not in ('reconstruccion', 'proyeccion', 'censo', 'encuesta', 'interpolacion_geometrica')
                or not item.get('serie') or not item.get('fecha_referencia')):
            raise ValueError('Población sin método, serie o fecha de referencia.')
        try:
            reference = date.fromisoformat(item['fecha_referencia'])
            if reference.year != year:
                raise ValueError('El año y la fecha de población no coinciden.')
        except (TypeError, ValueError) as exc:
            raise ValueError('Fecha de referencia poblacional inválida o incompatible con el año.') from exc
        if item['metodo'] == 'interpolacion_geometrica':
            anchors = item.get('anclajes', [])
            if len(anchors) != 2:
                raise ValueError('La interpolación exige sus dos anclajes documentados.')
            for anchor in anchors:
                provenance(anchor)
            try:
                a, b = anchors
                y0, y1 = a['anio'], b['anio']
                p0, p1 = Decimal(str(a['valor'])), Decimal(str(b['valor']))
                if (type(y0) is not int or type(y1) is not int or not y0 < year < y1
                        or not p0.is_finite() or not p1.is_finite() or min(p0, p1) <= 0):
                    raise ValueError('Anclajes inválidos o extrapolación.')
                expected = p0 * (p1 / p0) ** (Decimal(year-y0) / (y1-y0))
                if abs(expected-number) > 1:
                    raise ValueError('La población no coincide con la interpolación declarada.')
            except (KeyError, TypeError, InvalidOperation, ValueError) as exc:
                raise ValueError('Interpolación no reproducible con los anclajes documentados.') from exc
        methods.setdefault(scope, set()).add(item['serie'])
    if any(len(series) > 1 for series in methods.values()):
        raise ValueError('No mezclar series de población en un mismo ámbito.')
    for number, observations in value.get('observaciones', {}).items():
        if not re.fullmatch(r'(?:[1-9]|1[0-8])', number) or not isinstance(observations, dict):
            raise ValueError('Indicador complementario inválido.')
        for year, item in observations.items():
            if not re.fullmatch(r'\d{4}', year):
                raise ValueError('Año complementario inválido.')
            provenance(item)
    return deepcopy(value)


def cargar(path, municipio, estado):
    value = json.loads(Path(path).read_text(encoding='utf-8')) if path else vacia(municipio, estado)
    return validar(value, municipio, estado)


def poblacion(data, year, scope='municipal'):
    return next((r for r in data.get('poblacion', []) if r['anio'] == year and r['ambito'] == scope), None)


def tasas_comparables(data, year, local, state):
    a, b = poblacion(data, year), poblacion(data, year, 'estatal')
    if not a or not b or (a['serie'], a['metodo'], a['fecha_referencia']) != (b['serie'], b['metodo'], b['fecha_referencia']):
        return None
    return (Decimal(str(local)) * 1000 / Decimal(str(a['valor'])),
            Decimal(str(state)) * 1000 / Decimal(str(b['valor'])))
