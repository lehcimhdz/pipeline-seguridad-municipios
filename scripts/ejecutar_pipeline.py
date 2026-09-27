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

from documentos import leer_docx, registros, seccion_seguridad, sha256
from calificar import agregar, calificar_indicador, dependencias, definir_periodos
from componer_documento import componer
from salidas import limpiar_salidas
from contrato import huellas

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = (' Anexo.docx', ' PAQUETE SEGURIDAD.docx')


def slug(value):
    value = ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                    if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '_', value).strip('_')


def discover(input_dir):
    documents = {}
    prefixes = set()
    for suffix in SUFFIXES:
        matches = sorted(p for p in input_dir.glob('*' + suffix) if not p.name.startswith('~$'))
        if len(matches) != 1:
            raise ValueError(f'Se requiere exactamente un archivo con sufijo {suffix!r}; encontrados: {len(matches)}')
        documents[suffix] = matches[0]
        prefixes.add(matches[0].name[:-len(suffix)])
    if len(prefixes) != 1 or not next(iter(prefixes)).strip():
        raise ValueError('Las dos entradas deben compartir un municipio.')
    return prefixes.pop(), documents


def publicar(result, output, mode):
    """Validar toda la entrega antes de sustituir los archivos publicados."""
    from renderizar_word import renderizar, guardar_recibo
    directory = output / 'json'
    word_directory = output / 'word'
    name = slug(result['municipio'])
    dest = directory / f'{name}_diagnostico_seguridad_municipal.json'
    word = word_directory / f'{name}_seguridad_medicion_{mode}.docx'
    receipt = directory / f'{word.stem}_renderizado.json'
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


def main():
    parser = argparse.ArgumentParser(description='Diagnóstico de SEGURIDAD con el paquete y su anexo; un documento de medición.')
    parser.add_argument('--input', type=Path, default=ROOT / 'input/word')
    parser.add_argument('--output', type=Path, default=ROOT / 'output')
    parser.add_argument('--word', choices=('borrador', 'final', 'ninguno'), default='borrador',
                        help='Genera Word de revisión por defecto; final exige un JSON validado.')
    args = parser.parse_args()
    try:
        municipality, documents = discover(args.input)
        contract_hashes = huellas()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid4().hex[:8]
    evidence = {suffix: leer_docx(path) for suffix, path in documents.items()}
    sections = seccion_seguridad(evidence[SUFFIXES[1]])
    annex_sections = seccion_seguridad(evidence[SUFFIXES[0]])
    rules_path = ROOT / 'reglas_calificacion.json'
    rules = json.loads(rules_path.read_text(encoding='utf-8'))
    mappings_path = ROOT / 'config/normalizaciones.json'
    mappings = json.loads(mappings_path.read_text(encoding='utf-8'))
    template = ROOT / rules['fuente']['archivo']
    if sha256(template) != rules['fuente']['sha256']:
        raise ValueError('La metodología cambió: revisar y regenerar reglas_calificacion.json.')
    dictionary_path = ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json'
    dictionary = json.loads(dictionary_path.read_text(encoding='utf-8'))
    title = next((block for block in evidence[SUFFIXES[0]]
                  if block['tipo'] == 'parrafo' and 'Medición del municipio' in block['texto']), None)
    identity = re.search(r'municipio de\s+(.+?),\s+([^,\n]+)', title['texto']) if title else None
    validations = []
    state = None
    if identity and identity[1].strip().casefold() == municipality.casefold():
        state = identity[2].strip()
    else:
        validations.append({'codigo': 'IDENTIDAD_NO_CONFIRMADA', 'nivel': 'bloqueante'})
    evaluations = {}
    periods = definir_periodos(sections)
    for period in ('general', 'ultimo_periodo'):
        target_years = periods[period]['años_objetivo'] if period == 'ultimo_periodo' else None
        calculations = {section['numero']: calificar_indicador(section, ficha, period, mappings, años_objetivo=target_years)
                        for section, ficha in zip(sections, rules['fichas'])}
        dependencias(calculations)
        evaluations[period] = calculations
    for section, annex in zip(sections, annex_sections):
        number = section['numero']
        section['evaluaciones'] = {period: values[number] for period, values in evaluations.items()}
        raw = lambda item: [(t['ambito'], t['filas']) for t in item['tablas']]
        section['control_cruzado_anexo'] = {
            'tablas_identicas': raw(section) == raw(annex),
            'calificacion_reportada_coincide': section['calificacion_general_reportada'] == annex['calificacion_general_reportada'],
            'tablas_anexo': [t['tabla'] for t in annex['tablas']],
        }
        if not all(section['control_cruzado_anexo'][key] for key in ('tablas_identicas', 'calificacion_reportada_coincide')):
            validations.append({'nivel': 'revision', 'codigo': 'DIFERENCIA_ANEXO', 'indicador': number,
                                'detalle': 'Diferencia documental detectada; revisar si es sustantiva o de formato.'})
        for period, calculation in section['evaluaciones'].items():
            if calculation['puntaje'] is None:
                validations.append({'nivel': 'bloqueante', 'codigo': 'INDICADOR_PENDIENTE',
                                    'indicador': number, 'periodo': period, 'detalle': calculation['motivo']})
    years = sorted({row['año'] for section in sections for table in section['tablas']
                    if table['ambito'] == 'municipal' for row in registros(table)})
    values = {key: None for key in dictionary['variables_documento']}
    values.update(municipio=municipality, estado=state)
    if years:
        values.update({'año_inicial': years[0], 'año_final': years[-1]})
    if periods['ultimo_periodo']['años_objetivo']:
        values.update({'año_ultimo_periodo_inicial': periods['ultimo_periodo']['año_inicial'],
                       'año_ultimo_periodo_final': periods['ultimo_periodo']['año_final']})
    validations.append({'nivel': 'revision', 'codigo': 'COBERTURA_EDICIONES',
                        'detalle': 'Confirmar el año de referencia de las tablas. El último periodo exige los mismos dos años calendario consecutivos en los 18 indicadores.'})
    aggregates = {period: agregar(results, rules) for period, results in evaluations.items()}
    result = {
        'version': '2.1', 'ejecucion_id': run, 'municipio': municipality, 'estado': state,
        'estado_ejecucion': 'requiere_revision',
        'contrato': {**contract_hashes, 'normalizaciones_sha256': sha256(mappings_path)},
        'fuentes': [{'archivo': path.name, 'sha256': sha256(path),
                     'rol': 'primaria' if suffix == SUFFIXES[1] else 'control_cruzado'}
                    for suffix, path in documents.items()],
        'identidad_evidencia': title, 'valores_plantilla': values,
        'indicadores': sections, 'calculos': aggregates, 'periodos_evaluacion': periods,
        'evidencia_documental': {documents[suffix].name: blocks for suffix, blocks in evidence.items()},
        'validaciones': validations,
    }
    try:
        componer(result, dictionary, rules)
    except ValueError as error:
        parser.error(f'No se publicaron resultados: {error}')
    try:
        dest, report, removidos = publicar(result, args.output, args.word)
    except (ValueError, OSError) as error:
        parser.error(f'No se completó la publicación: {error}')
    print(f'JSON: {dest}')
    for period, results in evaluations.items():
        print(f'{period}: {sum(value["puntaje"] is not None for value in results.values())}/18 indicadores calculados.')
    print('Estado: requiere_revision. Los motivos específicos constan en validaciones.')
    if report:
        print(f"Word (medicion, {args.word}): {report['archivo']}")
        print(f"Formato y redacción verificados: {report['segmentos_json']} segmentos.")
    print(f"Limpieza de salidas: {removidos['json']} JSON y {removidos['word']} Word anteriores eliminados.")


if __name__ == '__main__':
    main()
