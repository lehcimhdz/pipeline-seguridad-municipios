#!/usr/bin/env python3
"""Localiza y audita incidencia oficial; nunca completa por sí sola la ficha 18.

La descarga es opcional. Los totales sólo son candidatos: la comparación con
personas ante el MP y la decisión `incidencia_comparable` son otra revisión.
"""
import argparse
import asyncio
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
          'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')


def key(value):
    clean = ''.join(c for c in unicodedata.normalize('NFD', value.casefold())
                    if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '_', clean).strip('_')


def _encoding(path):
    with Path(path).open('rb') as source:
        sample = source.read(8192)
    try:
        sample.decode('utf-8-sig')
        return 'utf-8-sig'
    except UnicodeDecodeError:
        return 'latin-1'


def _number(value):
    value = str(value).strip().replace(',', '')
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'Celda de incidencia no numérica: {value!r}.') from exc
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise ValueError('La incidencia exige enteros no negativos.')
    return int(number)


def total_anual(path, year, state_code, municipality_code=None):
    """Suma sólo filas de la geografía pedida y meses íntegramente numéricos."""
    matches = 0
    amount = 0
    path = Path(path)
    with path.open(encoding=_encoding(path), newline='') as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError('CSV de incidencia sin encabezado.')
        columns = {key(name): name for name in reader.fieldnames}
        mandatory = {'ano', 'clave_ent', *MONTHS}
        if not mandatory <= columns.keys():
            raise ValueError(f'CSV de incidencia sin columnas obligatorias: {sorted(mandatory - columns.keys())}')
        municipal_column = columns.get('cve_municipio') or columns.get('clave_mun')
        if municipality_code is not None and not municipal_column:
            raise ValueError('El archivo no tiene clave municipal; no permite extraer ese ámbito.')
        if municipality_code is None and municipal_column:
            raise ValueError('Para el estado se requiere el CSV estatal, no sumar municipios incompletos.')
        for row in reader:
            if str(row[columns['ano']]).strip() != str(year):
                continue
            if str(row[columns['clave_ent']]).strip().zfill(2) != str(state_code).zfill(2):
                continue
            if municipality_code is not None:
                raw = str(row[municipal_column]).strip()
                if raw.zfill(5) != str(municipality_code).zfill(5) and raw.zfill(3) != str(municipality_code)[-3:].zfill(3):
                    continue
            matches += 1
            amount += sum(_number(row[columns[month]]) for month in MONTHS)
    if not matches:
        raise ValueError('No hay filas para la geografía y el año solicitados.')
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    return {'anio': year, 'ambito': 'municipal' if municipality_code is not None else 'estatal',
            'valor': amount, 'filas': matches, 'meses': list(MONTHS),
            'archivo': str(path), 'sha256': digest,
            'definicion': 'presuntos delitos registrados en averiguaciones previas o carpetas de investigación'}


async def descubrir_y_descargar(directory=None):
    """`open-data-mexico` sólo localiza recursos; descarga únicamente si se pide."""
    try:
        from open_data_mexico import DatosGobMX  # dependencia opcional
    except ImportError as exc:
        raise RuntimeError('Instalar la dependencia opcional: pip install -r requirements-discovery.txt') from exc
    async with DatosGobMX() as client:
        dataset = await client.get_dataset('incidencia_delictiva')
        if dataset is None or dataset.organization_slug != 'sesnsp':
            raise ValueError('No se identificó el conjunto oficial del SESNSP.')
        found = {}
        downloads = {}
        for resource in dataset.resources:
            name = key(resource.name)
            scope = 'municipal' if 'municipal' in name else 'estatal' if 'estatal' in name else None
            if scope and resource.format and resource.format.lower() == 'csv':
                if scope in found:
                    raise ValueError('Hay más de un recurso de incidencia para un ámbito; revisar edición.')
                item = {'id': resource.resource_id, 'nombre': resource.name,
                        'url': resource.download_url, 'formato': resource.format}
                if directory is not None:
                    content = await client.get_resource_bytes(resource)
                    downloads[scope] = content
                found[scope] = item
        if set(found) != {'municipal', 'estatal'}:
            raise ValueError('No se encontraron ambos recursos de incidencia del SESNSP.')
        for scope, content in downloads.items():
            destination = Path(directory) / f'sesnsp_incidencia_{scope}.csv'
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            found[scope].update(archivo=str(destination), sha256=hashlib.sha256(content).hexdigest())
        return {'conjunto': dataset.url, 'organizacion': dataset.organization_name,
                'recursos': found}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descubrir', action='store_true')
    parser.add_argument('--descargar', action='store_true', help='Guarda ambos CSV oficiales en input/fuentes/.')
    parser.add_argument('--municipal', type=Path, help='CSV municipal descargado del SESNSP.')
    parser.add_argument('--estatal', type=Path, help='CSV estatal de la misma edición.')
    parser.add_argument('--entidad', default='19', help='Clave de entidad; 19 para Nuevo León.')
    parser.add_argument('--municipio', default='19006', help='Clave municipal; 19006 para Apodaca.')
    parser.add_argument('--anios', nargs='+', type=int, default=[2023, 2024])
    args = parser.parse_args()
    if args.descargar and not args.descubrir:
        parser.error('--descargar requiere --descubrir')
    report = {}
    if args.descubrir:
        report['catalogo'] = asyncio.run(descubrir_y_descargar(ROOT / 'input/fuentes' if args.descargar else None))
    local = args.municipal or (ROOT / 'input/fuentes/sesnsp_incidencia_municipal.csv' if args.descargar else None)
    state = args.estatal or (ROOT / 'input/fuentes/sesnsp_incidencia_estatal.csv' if args.descargar else None)
    if local or state:
        report['totales_candidatos'] = {str(year): {
            **({'municipal': total_anual(local, year, args.entidad, args.municipio)} if local else {}),
            **({'estatal': total_anual(state, year, args.entidad)} if state else {})} for year in args.anios}
        report['advertencia'] = ('Estos totales no se incorporan automáticamente al complemento ni '
                                 'acreditan `incidencia_comparable`; verificar cobertura y conciliación con CNGMD. '
                                 'Para la comparación se requieren CSV municipal y estatal de la misma edición.')
    if not report:
        parser.error('Indicar --descubrir o al menos un archivo --municipal o --estatal.')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
