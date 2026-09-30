"""Lee los títulos de las imágenes originales con OCR local y conserva su origen.

El OCR aporta contexto documental; sus números no sustituyen las tablas fuente.
Las imágenes se envían por stdin a Tesseract, sin crear archivos ni usar red.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import zipfile

from documentos import sha256


TIMEOUT = 25
_INICIO = re.compile(r'^[^\W\d_][^:\n]{1,79}:\s*\S', re.UNICODE)
_PERIODO = re.compile(r'\(\s*(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}\s*\)')
_NO_IDENTIDAD = {'fuente', 'nota', 'notas', 'porcentaje', 'total', 'año', 'años',
                 'periodo', 'período', 'número', 'numero', 'elaboración', 'elaboracion'}


def extraer_titulo(texto):
    """Aísla identidad: descripción (años), aunque el OCR anteponga los ejes.

    La ausencia de ese patrón deja el título vacío. No se promueven etiquetas
    de ejes ni notas al papel de título; el texto completo sigue disponible.
    """
    lines = [' '.join(line.split()) for line in texto.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not _INICIO.match(line) or line.split(':', 1)[0].strip().casefold() in _NO_IDENTIDAD:
            continue
        pieces = []
        for fragment in lines[index:index + 8]:
            if pieces and _INICIO.match(fragment):
                break
            pieces.append(fragment)
            candidate = ' '.join(pieces)
            period = _PERIODO.search(candidate)
            if period:
                return candidate[:period.end()]
    return ''


def _entorno_tesseract():
    executable = shutil.which('tesseract')
    if executable is None:
        return ('no_disponible', '', 'tesseract', '', 'Tesseract no está instalado.')
    try:
        version = subprocess.run([executable, '--version'], capture_output=True,
                                 text=True, timeout=TIMEOUT, check=True)
        lines = version.stdout.splitlines()
        motor = lines[0].strip() if lines else 'tesseract (versión desconocida)'
        languages = subprocess.run([executable, '--list-langs'], capture_output=True,
                                   text=True, timeout=TIMEOUT, check=True)
        installed = {line.strip() for line in languages.stdout.splitlines()}
    except (OSError, subprocess.SubprocessError) as error:
        return ('error', executable, 'tesseract', '',
                f'No se pudo consultar el motor OCR: {type(error).__name__}.')
    language = 'spa' if 'spa' in installed else 'eng' if 'eng' in installed else ''
    if not language:
        return ('no_disponible', executable, motor, '',
                'Tesseract no dispone de los idiomas spa o eng.')
    return ('disponible', executable, motor, language, '')


@lru_cache(maxsize=128)
def _ocr(raw, executable, motor, language):
    """La versión y el idioma forman parte de la caché, además de los bytes."""
    result = subprocess.run([executable, 'stdin', 'stdout', '-l', language],
                            input=raw, capture_output=True, timeout=TIMEOUT, check=True)
    return result.stdout.decode('utf-8', errors='replace').strip()


def leer_graficas(catalogue, rutas):
    """Devuelve una lectura auditable por imagen, sin modificar el catálogo.

    ``rutas`` relaciona el nombre documental con su ruta local. Las huellas
    incorrectas interrumpen la lectura; la falta o falla del OCR se registra
    como tal y nunca como ausencia de información en el documento.
    """
    if not catalogue:
        return []
    status, executable, motor, language, diagnostic = _entorno_tesseract()
    verified = {}
    readings = {}
    result = []
    for spec in catalogue:
        source_name = spec['fuente']
        if source_name not in rutas:
            raise ValueError(f'No se encontró la fuente de la gráfica: {source_name}.')
        source = Path(rutas[source_name])
        if source.name != source_name:
            raise ValueError('La ruta no corresponde al nombre documental de la gráfica.')
        source_key = (str(source), spec['fuente_sha256'])
        if source_key not in verified:
            try:
                checksum = sha256(source)
            except OSError as error:
                raise ValueError(f'No se pudo leer la fuente de la gráfica: {source_name}.') from error
            if checksum != spec['fuente_sha256']:
                raise ValueError('Cambió la fuente de una lectura gráfica.')
            verified[source_key] = True
        part = PurePosixPath(spec['parte'])
        if (part.is_absolute() or '..' in part.parts or not str(part).startswith('word/media/')
                or part.suffix.lower() not in ('.png', '.jpg', '.jpeg')):
            raise ValueError('La lectura gráfica requiere una imagen original de word/media.')
        try:
            with zipfile.ZipFile(source) as archive:
                raw = archive.read(spec['parte'])
        except (OSError, KeyError, zipfile.BadZipFile) as error:
            raise ValueError('No se pudo recuperar la imagen de su fuente documental.') from error
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum != spec['sha256']:
            raise ValueError('La imagen no coincide con la huella de la lectura gráfica.')
        if checksum not in readings:
            reading = {'estado': status, 'texto': '', 'titulo': '',
                       'idioma': language, 'motor': motor}
            if diagnostic:
                reading['diagnostico'] = diagnostic
            if status == 'disponible':
                try:
                    text = _ocr(raw, executable, motor, language)
                    reading.update(estado='leida' if text else 'sin_texto', texto=text,
                                   titulo=extraer_titulo(text))
                except (OSError, subprocess.SubprocessError) as error:
                    reading.update(estado='error',
                                   diagnostico=f'La lectura OCR falló: {type(error).__name__}.')
            readings[checksum] = reading
        result.append({**deepcopy(spec), 'lectura': deepcopy(readings[checksum])})
    return result


def validar_lecturas(lecturas, catalogue, rutas):
    """Recalcula los resultados y rechaza lecturas o procedencias modificadas."""
    expected = leer_graficas(catalogue, rutas)
    if lecturas != expected:
        raise ValueError('Las lecturas de las gráficas no corresponden a sus imágenes y al motor OCR actual.')
    return expected
