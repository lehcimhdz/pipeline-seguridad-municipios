#!/usr/bin/env python3
"""Extrae tablas y calcula los criterios implementados de ambos periodos."""
import argparse
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from documentos import leer_docx, seccion_seguridad, sha256
from calificar import agregar, calificar_indicador, definir_periodos, dependencias
from datos_externos import fuente, leer_csv, seleccionar, serie, serie_estatal, validar_campos
from inegi import consultar_poblacion, guardar_respuestas
from componer_documento import componer
from salidas import limpiar_salidas
from contrato import huellas, cargar_contrato
from investigacion import validar_aporte

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = (' Anexo.docx', ' PAQUETE SEGURIDAD.docx',
            ' PAQUETE GOBIERNO ABIERTO Y BUEN GOBIERNO.docx',
            ' PAQUETE DESARROLLO URBANO SOSTENIBLE Y DERECHOS HUMANOS CONEXOS.docx')


def slug(value):
    value = ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                    if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '_', value).strip('_')


def discover(input_dir):
    documents = {}
    prefixes = set()
    for suffix in SUFFIXES:
        matches = sorted(input_dir.glob('*' + suffix))
        if len(matches) != 1:
            raise ValueError(f'Se requiere exactamente un archivo con sufijo {suffix!r}; encontrados: {len(matches)}')
        documents[suffix] = matches[0]
        prefixes.add(matches[0].name[:-len(suffix)])
    if len(prefixes) != 1 or not next(iter(prefixes)).strip():
        raise ValueError('Las cuatro entradas deben compartir un municipio.')
    return prefixes.pop(), documents


def cargar_externos(args, run):
    config_path = ROOT / 'config/fuentes_externas.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    external = {}
    provenance = []
    supplied = [args.population_csv, args.incidence_csv, args.inegi_population]
    if any(supplied) and (not args.cve_ent or not args.cve_mun):
        raise ValueError('Las fuentes externas requieren --cve-ent y --cve-mun.')
    if args.population_csv and args.inegi_population:
        raise ValueError('Elige una sola fuente de población: --population-csv o --inegi-population.')
    if args.population_csv:
        rows = leer_csv(args.population_csv)
        definition = config['poblacion']
        validar_campos(rows, definition['campos_normalizados'], 'población')
        years = {int(row['año']) for row in rows}
        municipal = seleccionar(rows, (args.cve_ent, args.cve_mun), years)
        external['poblacion_municipal'] = serie(municipal, 'poblacion')
        external['poblacion_estatal'] = serie_estatal(rows, args.cve_ent, 'poblacion')
        provenance.append(fuente(args.population_csv, definition))
    if args.inegi_population:
        definition = config['poblacion']['inegi_api']
        token = os.environ.get('INEGI_TOKEN', '')
        population, source, responses = consultar_poblacion(
            token=token,
            cve_ent=args.cve_ent,
            cve_mun=args.cve_mun,
            definition=definition,
            timeout=args.inegi_timeout,
        )
        external.update(population)
        source['archivos_respuesta_original'] = guardar_respuestas(
            responses, args.inegi_raw_dir, run, args.cve_ent, args.cve_mun
        )
        provenance.append(source)
    if args.incidence_csv:
        rows = leer_csv(args.incidence_csv)
        definition = config['incidencia_delictiva']
        validar_campos(rows, definition['campos_normalizados'], 'incidencia delictiva')
        years = {int(row['año']) for row in rows}
        municipal = seleccionar(rows, (args.cve_ent, args.cve_mun), years)
        external['incidencia_municipal'] = serie(municipal, 'delitos_fuero_comun')
        external['incidencia_estatal'] = serie_estatal(rows, args.cve_ent, 'delitos_fuero_comun')
        provenance.append(fuente(args.incidence_csv, definition))
    return external, provenance, config_path


def evaluar_periodos(sections, rules, mappings=None, external=None):
    periods = definir_periodos(sections)
    evaluations = {}
    for period in ('general', 'ultimo_periodo'):
        target_years = periods[period]['años_objetivo'] if period == 'ultimo_periodo' else None
        calculations = {
            section['numero']: calificar_indicador(
                section, ficha, period, mappings, external, años_objetivo=target_years)
            for section, ficha in zip(sections, rules['fichas'])
        }
        dependencias(calculations)
        evaluations[period] = calculations
    return periods, evaluations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT / 'input/word')
    parser.add_argument('--output', type=Path, default=ROOT / 'output')
    parser.add_argument('--population-csv', type=Path)
    parser.add_argument('--incidence-csv', type=Path)
    parser.add_argument('--investigacion-json', type=Path,
                        help='Benchmarks y mínimos con fuentes y revisión declarada; no cambia las reglas de puntuación.')
    parser.add_argument('--inegi-population', action='store_true',
                        help='Consulta población total en la API INEGI usando INEGI_TOKEN.')
    parser.add_argument('--inegi-timeout', type=float, default=30.0)
    parser.add_argument('--inegi-raw-dir', type=Path, default=ROOT / 'input/datos_externos',
                        help='Destino ignorado por Git para respuestas originales de INEGI.')
    parser.add_argument('--cve-ent')
    parser.add_argument('--cve-mun')
    parser.add_argument('--word', choices=('borrador', 'final', 'ninguno'), default='borrador',
                        help='Genera Word de revisión por defecto; final exige un JSON validado.')
    args = parser.parse_args()
    try:
        cargar_contrato()
        research_input = (validar_aporte(json.loads(args.investigacion_json.read_text(encoding='utf-8')))
                          if args.investigacion_json else None)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    municipality, documents = discover(args.input)
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid4().hex[:8]
    try:
        external, external_sources, external_config_path = cargar_externos(args, run)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    evidence = {suffix: leer_docx(path) for suffix, path in documents.items()}
    sections = seccion_seguridad(evidence[SUFFIXES[1]])
    annex_sections = seccion_seguridad(evidence[SUFFIXES[0]])
    rules_path = ROOT / 'reglas_calificacion.json'
    rules = json.loads(rules_path.read_text(encoding='utf-8'))
    mappings_path = ROOT / 'config/normalizaciones.json'
    mappings = json.loads(mappings_path.read_text(encoding='utf-8'))
    template = ROOT / rules['fuente']['archivo']
    if sha256(template) != rules['fuente']['sha256']:
        raise ValueError('El DOCX cambió: revisar y regenerar reglas_calificacion.json.')
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
    periods, evaluations = evaluar_periodos(sections, rules, mappings, external)
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
    years = periods['general']['años_objetivo']
    values = {key: None for key in dictionary['variables_documento']}
    values.update(municipio=municipality, estado=state)
    if years:
        values.update({'año_inicial': years[0], 'año_final': years[-1]})
    if periods['ultimo_periodo']['años_objetivo']:
        values.update({'año_ultimo_periodo_inicial': periods['ultimo_periodo']['año_inicial'],
                       'año_ultimo_periodo_final': periods['ultimo_periodo']['año_final']})
    validations.append({'nivel': 'revision', 'codigo': 'COBERTURA_EDICIONES',
                        'detalle': 'Los años son etiquetas de las tablas. El último periodo exige los mismos dos años calendario consecutivos en los 18 indicadores. Confirmar la relación entre esas etiquetas y los años de referencia de cada edición censal antes de cerrar el diagnóstico.'})
    aggregates = {period: agregar(results, rules) for period, results in evaluations.items()}
    result = {
        'version': '3.1', 'ejecucion_id': run, 'municipio': municipality, 'estado': state,
        'estado_ejecucion': 'requiere_revision',
        'contrato': {**huellas(), 'normalizaciones_sha256': sha256(mappings_path),
                     'fuentes_externas_sha256': sha256(external_config_path)},
        'fuentes': [{'archivo': path.name, 'sha256': sha256(path),
                     'rol': 'primaria' if suffix == SUFFIXES[1] else 'control_cruzado_o_contexto'}
                    for suffix, path in documents.items()] + external_sources,
        'identidad_evidencia': title, 'valores_plantilla': values,
        'indicadores': sections, 'calculos': aggregates, 'periodos_evaluacion': periods,
        'evidencia_documental': {documents[suffix].name: blocks for suffix, blocks in evidence.items()},
        'validaciones': validations,
    }
    if research_input is not None:
        result['investigacion_aportada'] = research_input
        result['fuentes_investigacion'] = {'archivo': args.investigacion_json.name,
                                         'sha256': sha256(args.investigacion_json)}
    componer(result, dictionary, rules)
    directory = args.output / 'json'
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f'{slug(municipality)}_diagnostico_seguridad_municipal_{run}.json'
    receipt = directory / f'{slug(municipality)}_seguridad_medicion_{args.word}_renderizado.json'
    result['salida_word'] = {'modo_solicitado': args.word,
                            'recibo_renderizado': str(receipt) if args.word != 'ninguno' else None}
    temporary = dest.with_suffix('.json.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
            target.write('\n')
        temporary.replace(dest)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'JSON: {dest}')
    for period, results in evaluations.items():
        print(f'{period}: {sum(value["puntaje"] is not None for value in results.values())}/18 indicadores calculados.')
    print('Estado: requiere_revision. Los motivos específicos constan en validaciones.')
    if args.word != 'ninguno':
        from renderizar_word import renderizar, guardar_recibo
        try:
            report = renderizar(dest, args.output / 'word', args.word)
            guardar_recibo(report, receipt)
        except (ValueError, OSError) as error:
            parser.error(f'JSON conservado; no se completó la salida Word: {error}')
        print(f"Word ({args.word}): {report['archivo']}")
        print(f"Resaltado amarillo verificado: {report['segmentos_json']} segmentos. Recibo: {receipt}")
        removidos = limpiar_salidas(directory, args.output / 'word', json_actual=dest,
                                    word_actual=Path(report['archivo']), recibo_actual=receipt)
    else:
        removidos = limpiar_salidas(directory, args.output / 'word', json_actual=dest)
    print(f"Limpieza de salidas: {removidos['json']} JSON y {removidos['word']} Word anteriores eliminados.")


if __name__ == '__main__':
    main()
