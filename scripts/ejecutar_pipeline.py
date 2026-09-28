#!/usr/bin/env python3
"""Extrae tablas y calcula los criterios implementados de ambos periodos."""
import argparse
import json
import re
import shutil
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from documentos import leer_docx, seccion_seguridad, sha256
from ilustraciones_word import catalogar_graficas, seleccionar_graficas
from lectura_graficas import leer_graficas
from calificar import definir_periodos
from componer_documento import componer
from salidas import limpiar_salidas
from contrato import huellas
from evaluacion_v23 import evaluar
from ponderacion import agregar_ponderado
from evidencia_complementaria import cargar as cargar_complemento, huella_objeto
from redaccion_editorial import huella_evaluacion

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = (' Anexo.docx', ' PAQUETE SEGURIDAD.docx')


def slug(value):
    value = ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                    if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '_', value).strip('_')


def discover(input_dir):
    packages = sorted(p for p in input_dir.glob('* PAQUETE SEGURIDAD.docx') if not p.name.startswith('~$'))
    if len(packages) != 1:
        raise ValueError('Se requiere exactamente un PAQUETE SEGURIDAD del municipio.')
    package = packages[0]
    municipality = package.name.removesuffix(SUFFIXES[1]).strip()
    if not municipality:
        raise ValueError('El archivo debe identificar el municipio.')
    documents = {SUFFIXES[1]: package}
    annexes = sorted(p for p in input_dir.glob('* Anexo.docx') if not p.name.startswith('~$'))
    if annexes:
        if len(annexes) != 1 or annexes[0].name != municipality + SUFFIXES[0]:
            raise ValueError('El Anexo debe corresponder al municipio del Paquete Seguridad.')
        documents[SUFFIXES[0]] = annexes[0]
    return municipality, documents


def publicar(result, output, mode='final'):
    """Validar toda la entrega antes de sustituir los archivos publicados."""
    from renderizar_word import renderizar, guardar_recibo
    directory = output / 'json'
    word_directory = output / 'word'
    name = slug(result['municipio'])
    dest = directory / f'{name}_diagnostico_seguridad_municipal.json'
    word = word_directory / f'{result["municipio"]} Estudio Seguridad.docx'
    receipt = directory / f'{name}_estudio_seguridad_renderizado.json'
    result['salida_word'] = {
        'modo_solicitado': mode,
        'recibos_renderizado': {'medicion': str(receipt)} if mode != 'ninguno' else {},
    }
    output.mkdir(parents=True, exist_ok=True)
    report = None
    with tempfile.TemporaryDirectory(prefix='.publicacion-', dir=output) as temporary:
        stage = Path(temporary)
        staged_json = stage / dest.name
        staged_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if mode != 'ninguno':
            report = renderizar(staged_json, stage / 'word', mode)
            staged_word = Path(report['archivo'])
            report.update(archivo=str(word), json_fuente=str(dest))
            staged_receipt = stage / receipt.name
            guardar_recibo(report, staged_receipt)
        directory.mkdir(parents=True, exist_ok=True)
        replacements = []
        if report:
            word_directory.mkdir(parents=True, exist_ok=True)
            replacements.extend(((staged_word, word), (staged_receipt, receipt)))
        replacements.append((staged_json, dest))
        backups = {}
        backup_directory = stage / 'anteriores'
        backup_directory.mkdir()
        for index, (_, target) in enumerate(replacements):
            if target.exists():
                backup = backup_directory / str(index)
                shutil.copy2(target, backup)
                backups[target] = backup
        published = []
        try:
            for source, target in replacements:
                source.replace(target)
                published.append(target)
        except OSError as error:
            try:
                for target in reversed(published):
                    if target in backups:
                        backups[target].replace(target)
                    else:
                        target.unlink(missing_ok=True)
            except OSError as restoration_error:
                recovery = output / ('.recuperacion-' + uuid4().hex)
                stage.replace(recovery)
                raise OSError(f'No se pudo restaurar la entrega anterior; archivos de recuperación en {recovery}.') from restoration_error
            raise OSError('No se pudo publicar; se restauró la entrega anterior.') from error
    removed = limpiar_salidas(directory, word_directory, json_actual=dest,
                              word_actual=word if report else None,
                              recibo_actual=receipt if report else None)
    return dest, report, removed


def preparar(input_dir, redaccion=None, estado=None, modo_calificacion='evaluables', complemento=None, esquema=None):
    municipality, documents = discover(input_dir)
    contract_hashes = huellas()
    evidence = {suffix: leer_docx(path) for suffix, path in documents.items()}
    sections = seccion_seguridad(evidence[SUFFIXES[1]])
    annex_sections = seccion_seguridad(evidence[SUFFIXES[0]]) if SUFFIXES[0] in evidence else None
    rules = json.loads((ROOT / 'reglas_calificacion.json').read_text(encoding='utf-8'))
    mappings_path = ROOT / 'config/normalizaciones.json'
    mappings = json.loads(mappings_path.read_text(encoding='utf-8'))
    dictionary = json.loads((ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json').read_text(encoding='utf-8'))
    title = next((block for block in evidence.get(SUFFIXES[0], [])
                  if block['tipo'] == 'parrafo' and 'Medición del municipio' in block['texto']), None)
    identity = re.search(r'municipio de\s+(.+?),\s+([^,\n]+)', title['texto']) if title else None
    if identity and identity[1].strip().casefold() != municipality.casefold():
        raise ValueError('La identidad del Anexo no corresponde al municipio.')
    documented_state = identity[2].strip() if identity else None
    declared_state = estado or (redaccion or {}).get('estado')
    if documented_state and declared_state and documented_state.casefold() != declared_state.casefold():
        raise ValueError('La entidad declarada difiere del Anexo.')
    state = documented_state or declared_state
    periods = definir_periodos(sections)
    supplemental = cargar_complemento(complemento, municipality, state)
    catalogue = [image for path in documents.values() for image in catalogar_graficas(path)]
    readings = leer_graficas(catalogue, {p.name: str(p.resolve()) for p in documents.values()})
    for section in sections:
        section['lecturas_graficas'] = [item for item in readings if item['indicador'] == section['numero']]
    evaluations = evaluar(sections, rules, mappings, periods, supplemental)
    validations = [{'nivel': 'revision', 'codigo': 'LECTURA_GRAFICA_INCOMPLETA',
                    'indicador': item['indicador'], 'fuente': item['fuente'],
                    'parte': item['parte'], 'detalle': item['lectura']['estado']}
                   for item in readings if item['lectura']['estado'] in ('error', 'no_disponible')]
    for section in sections:
        number = section['numero']
        section['evaluaciones'] = {period: values[number] for period, values in evaluations.items()}
        if annex_sections:
            annex = annex_sections[number - 1]
            raw = lambda item: [(t['ambito'], t['filas']) for t in item['tablas']]
            section['control_cruzado_anexo'] = {
                'tablas_identicas': raw(section) == raw(annex),
                'calificacion_reportada_coincide': section['calificacion_general_reportada'] == annex['calificacion_general_reportada']}
            if not all(section['control_cruzado_anexo'].values()):
                validations.append({'nivel': 'revision', 'codigo': 'DIFERENCIA_ANEXO', 'indicador': number})
        for period, calculation in section['evaluaciones'].items():
            if calculation['puntaje'] is None:
                validations.append({'nivel': 'alcance', 'codigo': 'INDICADOR_NO_EVALUABLE',
                                    'indicador': number, 'periodo': period, 'detalle': calculation['motivo']})
    aggregates = {period: agregar_ponderado(values, rules, modo=modo_calificacion, esquema=esquema)
                  for period, values in evaluations.items()}
    result = {
        'version': '2.3', 'ejecucion_id': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid4().hex[:8],
        'municipio': municipality, 'estado': state, 'estado_ejecucion': 'requiere_redaccion',
        'contrato': {**contract_hashes, 'normalizaciones_sha256': sha256(mappings_path)},
        'fuentes': [{'archivo': path.name, 'sha256': sha256(path),
                     'rol': 'primaria' if suffix == SUFFIXES[1] else 'contraste_opcional'}
                    for suffix, path in documents.items()],
        'rutas_fuentes': {path.name: str(path.resolve()) for path in documents.values()},
        'identidad_evidencia': title or {'tipo': 'declaracion_editorial', 'estado': state},
        'valores_plantilla': {key: None for key in dictionary['variables_documento']},
        'indicadores': sections, 'calculos': aggregates, 'periodos_evaluacion': periods,
        'metodo_calificacion': modo_calificacion, 'catalogo_ilustraciones': catalogue,
        'lecturas_graficas': readings,
        'esquema_ponderacion': aggregates['general']['esquema'],
        'evidencia_complementaria': supplemental,
        'evidencia_complementaria_sha256': huella_objeto(supplemental),
        'evidencia_documental': {documents[suffix].name: blocks for suffix, blocks in evidence.items()},
        'validaciones': validations}
    result['evaluacion_sha256'] = huella_evaluacion(result)
    return result, dictionary, rules


def main():
    parser = argparse.ArgumentParser(description='Estudio de seguridad: evidencia, benchmark e interpretación editorial.')
    parser.add_argument('--input', type=Path, default=ROOT / 'input/word')
    parser.add_argument('--output', type=Path, default=ROOT / 'output')
    parser.add_argument('--redaccion', type=Path, help='Interpretación editorial del municipio vinculada a las fuentes.')
    parser.add_argument('--estado', help='Entidad federativa cuando el Anexo no esté disponible.')
    parser.add_argument('--preparar', action='store_true', help='Prepara evidencia y calificaciones para que el agente redacte el estudio.')
    parser.add_argument('--calificacion', choices=('evaluables', 'completo'), default='evaluables')
    parser.add_argument('--complemento', type=Path, help='Datos y definiciones revisados, con fuente y localizador por observación.')
    parser.add_argument('--esquema', choices=('dimensiones_ponderadas', 'dimensiones_iguales', 'global'))
    parser.add_argument('--graficas', choices=('originales', 'ninguna'), default='originales')
    args = parser.parse_args()
    try:
        municipality, _ = discover(args.input)
        writing_path = args.redaccion or ROOT / 'input/redaccion' / f'{slug(municipality)}.json'
        writing = json.loads(writing_path.read_text(encoding='utf-8')) if writing_path.is_file() else None
        result, dictionary, rules = preparar(args.input, writing, args.estado, args.calificacion,
                                            args.complemento, args.esquema)
        if args.preparar:
            directory = args.output / 'json'
            directory.mkdir(parents=True, exist_ok=True)
            dest = directory / f'{slug(municipality)}_evidencia_seguridad.json'
            from renderizar_word import guardar_recibo
            guardar_recibo(result, dest)
            print(f'Evidencia para interpretación editorial: {dest}')
            for period, calculation in result['calculos'].items():
                print(f'{period}: {calculation["cobertura"]["evaluables"]}/18 evaluables; '
                      f'{calculation["cobertura"]["prioritarios_evaluables"]}/8 prioritarios. '
                      f'Calificación: {calculation["calificacion_final"] or "pendiente"}.')
            return
        if any(c['calificacion_final'] is None for c in result['calculos'].values()):
            raise ValueError('La evidencia no alcanza la cobertura requerida tras resolver las correspondencias automáticas. Use --preparar para consultar los requisitos concretos pendientes; aporte sólo esas aclaraciones o datos mediante --complemento. La entrega anterior se conserva.')
        if writing is None:
            raise ValueError(f'Falta la interpretación editorial: {writing_path}. Use --preparar para revisar la evidencia y redactar sus apartados.')
        if not result['estado']:
            raise ValueError('Falta confirmar la entidad federativa en la interpretación editorial.')
        componer(result, dictionary, rules, redaccion=writing)
        choices = writing.get('ilustraciones', []) if args.graficas == 'originales' else []
        result['contenido_word']['ilustraciones'] = seleccionar_graficas(result['catalogo_ilustraciones'], choices)
        result['contenido_word']['politica_ilustraciones'] = args.graficas
        result['contenido_word']['ilustraciones_excluidas'] = writing.get('ilustraciones_excluidas', [])
        result['redaccion_editorial'] = {'archivo': str(writing_path), 'sha256': sha256(writing_path)}
        result['estado_ejecucion'] = 'compuesto'
        dest, report, removed = publicar(result, args.output)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(f'JSON: {dest}')
    print(f'Word: {report["archivo"]}')
    for period, calculation in result['calculos'].items():
        print(f'{period}: {calculation["calificacion_final"]}; alcance {calculation.get("alcance", "completo")}.')
    print(f'Limpieza de salidas anteriores: {removed}.')


if __name__ == '__main__':
    main()
