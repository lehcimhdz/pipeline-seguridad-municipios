"""Vincula una interpretación escrita por un agente/editor a su evidencia.

La revisión numérica no demuestra por sí misma la verdad de una interpretación:
el autor debe revisar causalidad, comparabilidad, unidades y recomendaciones.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from redaccion_consultoria import comprobar_texto
from evidencia_complementaria import huella_objeto

ROOT = Path(__file__).resolve().parents[1]
BLOQUES = {'resumen_general', 'resumen_ultimo_periodo', 'bibliografia'} | {
    f'analisis_indicador_{number:02d}' for number in range(1, 19)}
NUMERO = re.compile(r'(?<![\w])\d+(?:,\d{3})*(?:\.\d+)?(?![\w])')
HASH = re.compile(r'[0-9a-f]{64}')
VINCULOS_METODOLOGICOS = ('benchmark_sha256', 'reglas_sha256', 'ponderacion_sha256',
                         'definiciones_sha256', 'textos_narrativos_sha256')


def huella_evaluacion(result):
    return huella_objeto({'calculos': result['calculos'], 'periodos': result['periodos_evaluacion'],
                         'indicadores': {str(s['numero']): s['evaluaciones'] for s in result['indicadores']}})


def nombre_editorial(municipio):
    plain = unicodedata.normalize('NFKD', municipio)
    plain = ''.join(char for char in plain if not unicodedata.combining(char)).lower()
    return re.sub(r'[^a-z0-9]+', '_', plain).strip('_') + '.json'


def cargar_redaccion(redaccion=None, *, municipio):
    if isinstance(redaccion, dict):
        return deepcopy(redaccion)
    path = Path(redaccion) if redaccion is not None else ROOT / 'input/redaccion' / nombre_editorial(municipio)
    if not path.is_file():
        raise ValueError(f'Falta la interpretación editorial de {municipio}. Preparar y revisar el archivo {path}.')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise ValueError(f'No se pudo leer la interpretación editorial: {path}.') from exc


def _numeros(text):
    return {Decimal(token.replace(',', '')) for token in NUMERO.findall(str(text))}


def _fuentes(entries):
    result = {}
    for entry in entries:
        filename, digest = entry.get('archivo', ''), entry.get('sha256', '')
        if (not isinstance(filename, str) or Path(filename).name != filename or '/' in filename or '\\' in filename
                or not isinstance(digest, str) or not HASH.fullmatch(digest) or filename in result):
            raise ValueError('La redacción debe identificar cada fuente una sola vez por su nombre exacto y su huella.')
        result[filename] = digest
    if not result:
        raise ValueError('La redacción no tiene fuentes documentales verificables.')
    return result


def _resolver_hechos(result, facts):
    sections = {section['numero']: section for section in result['indicadores']}
    resolved = {}
    for key, fact in facts.items():
        if not isinstance(fact, dict):
            raise ValueError(f'Hecho editorial inválido: {key}.')
        if fact.get('operacion'):
            continue
        if fact.get('origen') == 'complemento':
            try:
                number, year = fact['indicador'], fact['anio']
                if number not in sections or type(year) is not int:
                    raise ValueError('Identidad de hecho inválida.')
                data = result['evidencia_complementaria']
                if fact.get('ambito') in ('municipal', 'estatal') and fact['campo'] == 'poblacion':
                    records = [r for r in data['poblacion'] if r['ambito'] == fact['ambito'] and r['anio'] == year]
                    if len(records) != 1: raise ValueError('Población ausente o ambigua.')
                    value = records[0]['valor']
                else:
                    value = data['observaciones'][str(number)][str(year)][fact['campo']]
                if isinstance(value, (dict, list, bool)) or value is None or fact.get('valor') != value:
                    raise ValueError('El dato no coincide con el complemento.')
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError(f'El hecho complementario {key} no coincide con la evidencia.') from exc
            resolved[key] = {'valor': value, 'numeros': _numeros(value) | {Decimal(year)}, 'indicador': number}
            continue
        try:
            section = sections[fact['indicador']]
            tables = [table for table in section['tablas'] if table['tabla'] == fact['tabla']]
            if len(tables) != 1:
                raise ValueError('Tabla ausente o ambigua.')
            table = tables[0]
            header = table['filas'][0]
            column = header.index(fact['columna'])
            index = fact['fila']
            if not isinstance(index, int) or isinstance(index, bool) or index <= 0:
                raise ValueError('La fila debe identificar una observación, no la cabecera.')
            row = table['filas'][index]
            value = row[column]
            if fact.get('valor') != value:
                raise ValueError('La celda cambió.')
            year = row[header.index('Año')] if 'Año' in header else ''
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ValueError(f'El hecho {key} no coincide con la evidencia estadística.') from exc
        resolved[key] = {'valor': value, 'numeros': _numeros(value) | _numeros(year),
                         'indicador': fact['indicador']}
    pending = {key: value for key, value in facts.items() if value.get('operacion')}
    while pending:
        progress = False
        for key, fact in list(pending.items()):
            refs = fact.get('operandos', [])
            if len(refs) != 2 or any(ref not in resolved for ref in refs):
                continue
            try:
                left, right = (Decimal(str(resolved[ref]['valor']).replace(',', '')) for ref in refs)
                op = fact['operacion']
                if op == 'resta':
                    number = left - right
                elif op == 'variacion_porcentual' and right != 0:
                    number = (left - right) / right * 100
                else:
                    raise ValueError('Operación no admitida.')
                places = fact.get('decimales', 1)
                if not isinstance(places, int) or not 0 <= places <= 4:
                    raise ValueError('Precisión no admitida.')
                number = number.quantize(Decimal(1).scaleb(-places))
                if Decimal(str(fact['valor'])) != number:
                    raise ValueError('El resultado declarado no corresponde a la operación.')
            except (InvalidOperation, ValueError, KeyError, TypeError) as exc:
                raise ValueError(f'Cálculo editorial inválido: {key}.') from exc
            resolved[key] = {'valor': str(number), 'numeros': {number, abs(number)},
                             'indicador': resolved[refs[0]]['indicador']}
            del pending[key]
            progress = True
        if not progress:
            raise ValueError('Hay cálculos editoriales con referencias inexistentes o circulares.')
    return resolved


def validar_redaccion(result, artifact):
    if artifact.get('version') != '2.3':
        raise ValueError('Se requiere una interpretación editorial versión 2.3, revisada con la nueva metodología.')
    if any(artifact.get(field) != result.get(field) for field in ('municipio', 'estado')):
        raise ValueError('La interpretación editorial corresponde a otro municipio o estado.')
    links = artifact.get('vinculos', {})
    if _fuentes(links.get('fuentes', [])) != _fuentes(result.get('fuentes', [])):
        raise ValueError('La interpretación editorial está desactualizada: cambiaron las fuentes documentales.')
    contract = result.get('contrato', {})
    for key in VINCULOS_METODOLOGICOS:
        expected = contract.get(key)
        if not isinstance(expected, str) or not HASH.fullmatch(expected) or links.get(key) != expected:
            raise ValueError(f'La interpretación editorial no corresponde al criterio vigente: {key}.')
    supplemental_hash = result.get('evidencia_complementaria_sha256')
    if (not isinstance(supplemental_hash, str) or not HASH.fullmatch(supplemental_hash)
            or links.get('evidencia_complementaria_sha256') != supplemental_hash):
        raise ValueError('La redacción no corresponde a la evidencia complementaria vigente.')
    if links.get('evaluacion_sha256') != huella_evaluacion(result):
        raise ValueError('Cambió la evaluación o el esquema: revisar de nuevo la interpretación editorial.')
    revision = artifact.get('revision', {})
    if revision.get('estado') != 'revisada' or revision.get('tipo_autor') not in ('agente_editorial', 'persona'):
        raise ValueError('La interpretación debe estar revisada e identificar el tipo de autor editorial.')
    facts = artifact.get('hechos', {})
    if not isinstance(facts, dict) or not facts:
        raise ValueError('La interpretación no declara hechos verificables.')
    resolved = _resolver_hechos(result, facts)
    selection = artifact.get('seleccion_editorial', {})
    if set(selection) != {str(i) for i in range(1, 19)}:
        raise ValueError('Falta la selección editorial de los dieciocho encuadres.')
    for number, entry in selection.items():
        if (entry.get('encuadre_id') != number or entry.get('revision_semantica') is not True
                or not isinstance(entry.get('consecuencia_revisada'), str) or not entry['consecuencia_revisada'].strip()):
            raise ValueError('Cada encuadre requiere revisión del significado y una consecuencia específica documentada.')
    blocks = artifact.get('bloques', {})
    if set(blocks) != BLOQUES:
        raise ValueError('La interpretación debe contener los dos resúmenes, los dieciocho análisis y la bibliografía.')
    count = 0
    for variable, paragraphs in blocks.items():
        if not isinstance(paragraphs, list) or not paragraphs:
            raise ValueError(f'Falta el texto editorial de {variable}.')
        if variable.startswith('resumen_') and len(paragraphs) != 3:
            raise ValueError(f'{variable} requiere tres párrafos de síntesis.')
        for paragraph in paragraphs:
            text = paragraph.get('texto', '')
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f'Párrafo vacío en {variable}.')
            comprobar_texto(text, variable)
            if re.search(r'\{[^{}]+\}|\[(?:INSERTAR|AÑOS|MUNICIPIO)[^\]]*\]', text, re.I):
                raise ValueError(f'Marcador editorial pendiente en {variable}.')
            refs = paragraph.get('evidencia', [])
            if variable != 'bibliografia' and not refs:
                raise ValueError(f'El párrafo de {variable} no declara evidencia.')
            if any(ref not in resolved for ref in refs):
                raise ValueError(f'El párrafo de {variable} cita un hecho inexistente.')
            if variable.startswith('analisis_indicador_'):
                number = int(variable.rsplit('_', 1)[-1])
                if not any(resolved[ref]['indicador'] == number for ref in refs):
                    raise ValueError(f'El texto de {variable} no cita evidencia de su indicador.')
            allowed = set().union(*(resolved[ref]['numeros'] for ref in refs)) if refs else set()
            if _numeros(text) - allowed:
                raise ValueError(f'El texto de {variable} contiene cifras sin respaldo en los hechos citados.')
            count += 1
        cited = {resolved[ref]['indicador'] for p in paragraphs for ref in p.get('evidencia', [])}
        if variable.startswith('resumen_'):
            if len(cited) < 2:
                raise ValueError('La síntesis requiere hechos de al menos dos indicadores.')
            period = 'general' if variable == 'resumen_general' else 'ultimo_periodo'
            low = {s['numero'] for s in result['indicadores'] if s['numero'] in (2, 4, 5, 10, 11, 12, 13, 14)
                   and s['evaluaciones'][period].get('puntaje') in (1, 2)}
            if not low <= cited:
                raise ValueError('La síntesis omite evidencia de un indicador prioritario con desempeño bajo.')
    canonical = json.dumps(artifact, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return {'estado': 'verificada', 'version': '2.3', 'parrafos': count,
            'hechos': len(resolved), 'sha256': hashlib.sha256(canonical).hexdigest(),
            'autor': revision['tipo_autor'],
            'limite': 'La comprobación de fuentes y cifras no sustituye la revisión del significado, las unidades y las inferencias.'}
