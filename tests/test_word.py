"""Pruebas con datos sintéticos; no necesitan los archivos de un municipio."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from calificar import definir_periodos
from calificacion_documental import agregar_documental, asignar_calificaciones
from componer_documento import componer
from documentos import sha256
from contrato import huellas, cargar_contrato
from investigacion import validar_aporte
from fuentes_word import FONTS
from unittest.mock import patch
from renderizar_word import (DICTIONARY, RULES, TEMPLATE, W, STYLE, auditar,
                             parrafo, reemplazar, renderizar, run, texto, validar_resultado)


def investigacion_sintetica():
    """Referencias ficticias, sólo para probar estructura, nunca para un municipio."""
    config = json.loads((ROOT / 'config/investigacion_seguridad.json').read_text())
    lines = []
    for definition in config['lineas']:
        url = 'https://example.org/' + definition['id']
        lines.append({'id': definition['id'], 'estado': 'verificado',
                      'analisis': 'Análisis sintético de pruebas. Fuente: ' + url,
                      'apartados': {p['id']: 'Evidencia sintética. Fuente: ' + url for p in definition.get('apartados', [])},
                      'referencias': [{'titulo': 'Fuente sintética', 'url': url,
                                      'fecha_consulta': '2026-09-25', 'localizador': 'Sección de prueba',
                                      'aplicabilidad': 'Sólo prueba', 'revisado_por': 'Prueba automatizada'}]})
    url = lines[0]['referencias'][0]['url']
    return {'version': '1.0', 'lineas': lines, 'minimos_indicadores': {
        f'{i:02d}': {'texto': 'Mínimo sintético de pruebas. Fuente: ' + url,
                    'referencias': [url]} for i in range(1, 4)}}


def ejemplo(pending=True, research=None):
    dictionary = json.loads(DICTIONARY.read_text(encoding='utf-8'))
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    sections = []
    for ficha in rules['fichas']:
        number = ficha['id']
        evaluation = {'puntaje': None if pending and number == 4 else 5,
                      'años_evaluados': [2021, 2022], 'criterio_aplicado': f'Ficha {number}, criterio 5'}
        if evaluation['puntaje'] is None:
            evaluation['motivo'] = 'Falta población comparable.'
        sections.append({'numero': number, 'nombre': ficha['nombre'],
                         'evaluaciones': {p: deepcopy(evaluation) for p in ('general', 'ultimo_periodo')},
                         'control_cruzado_anexo': {'tablas_identicas': True, 'calificacion_reportada_coincide': True},
                         'tablas': [{'tabla': number, 'ambito': 'municipal',
                                     'filas': [['Año', 'Valor'], ['2021', 'Sí & válido < 100'], ['2022', '']]}]})
        if number in (14, 15, 18):
            sections[-1]['tablas'].append({'tabla': 100 + number, 'ambito': 'estatal',
                                           'filas': [['Año', 'Valor'], ['2021', '30'], ['2022', '40']]})
    values = {k: None for k in dictionary['variables_documento']}
    values.update(municipio='Municipio de prueba', estado='Entidad de prueba', año_inicial=2021, año_final=2022)
    calculations = {}
    for period in ('general', 'ultimo_periodo'):
        evaluations = {section['numero']: section['evaluaciones'][period] for section in sections}
        asignar_calificaciones(evaluations, rules)
        calculations[period] = agregar_documental(evaluations, rules)
    result = {'municipio': values['municipio'], 'estado': values['estado'], 'estado_ejecucion': 'requiere_revision',
              'contrato': huellas(),
              'periodos_evaluacion': definir_periodos(sections),
              'valores_plantilla': values, 'indicadores': sections,
              'calculos': calculations,
              'validaciones': [{'nivel': 'bloqueante', 'codigo': 'COMPOSICION_WORD_PENDIENTE'},
                               {'nivel': 'bloqueante', 'codigo': 'VARIABLES_PENDIENTES'}]}
    if pending:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'INDICADOR_PENDIENTE', 'indicador': 4})
    include_research = research if research is not None else not pending
    if include_research:
        result['investigacion_aportada'] = investigacion_sintetica()
    return componer(result, dictionary, rules)


class WordTests(unittest.TestCase):
    def test_fragmented_marker_preserves_surrounding_style(self):
        p = ET.Element(W + 'p')
        for text in ('Antes {muni', 'cipio} después'):
            r = run(text, generated=False)
            ET.SubElement(r.find(W + 'rPr'), W + 'i')
            p.append(r)
        reemplazar(p, '{municipio}', 'A & B < C')
        self.assertEqual(texto(p), 'Antes A & B < C después')
        runs = list(p.iter(W + 'r'))
        self.assertEqual(len(runs), 3)
        for r in runs:
            self.assertIsNotNone(r.find(W + 'rPr/' + W + 'i'))
        self.assertIsNone(runs[0].find(W + 'rPr/' + W + 'highlight'))
        self.assertIsNone(runs[2].find(W + 'rPr/' + W + 'highlight'))
        self.assertIsNone(runs[1].find(W + 'rPr/' + W + 'highlight'))
        self.assertIsNone(runs[1].find(W + 'rPr/' + W + 'shd'))
        self.assertEqual(runs[1].find(W + 'rPr/' + W + 'rStyle').get(W + 'val'), STYLE)

    def test_generated_run_preserves_editorial_colors_without_yellow_marks(self):
        model = run('Marcador', generated=False)
        props = model.find(W + 'rPr')
        ET.SubElement(props, W + 'color', {W + 'val': '1F4E78'})
        ET.SubElement(props, W + 'shd', {W + 'fill': 'DAE3F3'})
        ET.SubElement(props, W + 'highlight', {W + 'val': 'yellow'})
        generated = run('Texto JSON', model)
        self.assertEqual(generated.find(W + 'rPr/' + W + 'color').get(W + 'val'), '1F4E78')
        self.assertEqual(generated.find(W + 'rPr/' + W + 'shd').get(W + 'fill'), 'DAE3F3')
        self.assertIsNone(generated.find(W + 'rPr/' + W + 'highlight'))
        self.assertIsNotNone(model.find(W + 'rPr/' + W + 'highlight'))
        props.find(W + 'shd').set(W + 'fill', 'ffff00')
        self.assertIsNone(run('Texto JSON', model).find(W + 'rPr/' + W + 'shd'))

    def test_composition_keeps_missing_scores_and_inactive_variables(self):
        result = ejemplo()
        self.assertIn('4', result['valores_plantilla']['resumen_general'])
        self.assertNotIn('condicion_critica', result['valores_plantilla'])
        self.assertEqual(result['contenido_word']['variables_no_aplicables'], [])
        self.assertIsNotNone(result['calculos']['general']['calificacion_final'])
        self.assertIsNone(result['indicadores'][3]['evaluaciones']['general']['puntaje'])
        self.assertEqual(result['indicadores'][3]['evaluaciones']['general']['puntaje_asignado'], 1)
        codes = {v['codigo'] for v in result['validaciones']}
        self.assertNotIn('COMPOSICION_WORD_PENDIENTE', codes)
        self.assertIn('INDICADOR_PENDIENTE', codes)
        self.assertIn('REVISION_EDITORIAL_WORD', codes)

    def test_draft_roundtrip_no_highlight_hashes_and_replaces_current_output(self):
        result = ejemplo()
        before = sha256(TEMPLATE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            report = renderizar(path, Path(directory) / 'word')
            word = Path(report['archivo'])
            self.assertEqual(word.name, 'municipio_de_prueba_seguridad_medicion_borrador.docx')
            self.assertEqual(report['json_sha256'], sha256(path))
            self.assertEqual(report['sha256'], sha256(word))
            self.assertTrue(report['sin_resaltado_amarillo_verificado'])
            self.assertFalse(report['resaltado_amarillo'])
            with zipfile.ZipFile(word) as archive:
                root = ET.fromstring(archive.read('word/document.xml'))
                text = texto(root)
                self.assertIn('BORRADOR DE REVISIÓN', text)
                self.assertIn('Sí & válido < 100', text)
                self.assertIn('Falta población comparable', text)
                self.assertNotIn('TEXTOS BASE', text)
                self.assertNotIn('{', text)
                self.assertIn('Certificado', text)
                self.assertTrue(report['fidelidad_machote_verificada'])
                self.assertEqual(report['bloques_origen_verificados'], 101)
                self.assertTrue(text.startswith('SEGURIDAD'))
                self.assertNotIn('Mediciones de Funcionamiento Municipal — SEGURIDAD', text)
                self.assertEqual(len(root.findall('.//' + W + 'numPr')), 35)
                sections = root.findall('.//' + W + 'sectPr')
                self.assertEqual(len(sections), 1)
                for r in root.iter(W + 'r'):
                    style = r.find(W + 'rPr/' + W + 'rStyle')
                    if style is not None and style.get(W + 'val') == STYLE:
                        self.assertIsNone(r.find(W + 'rPr/' + W + 'highlight'))
                        shade = r.find(W + 'rPr/' + W + 'shd')
                        self.assertTrue(shade is None or shade.get(W + 'fill', '').upper() != 'FFFF00')
                        self.assertIn(r.find(W + 'rPr/' + W + 'rFonts').get(W + 'ascii'), ('Archivo Light', 'Archivo Medium', 'Archivo'))
                styles = ET.fromstring(archive.read('word/styles.xml'))
                trace_style = next(s for s in styles.findall(W + 'style') if s.get(W + 'styleId') == STYLE)
                self.assertIsNone(trace_style.find(W + 'rPr'))
            again = renderizar(path, word.parent)
            self.assertEqual(report['archivo'], again['archivo'])
            self.assertEqual(again['sha256'], sha256(word))
        self.assertEqual(before, sha256(TEMPLATE))

    def test_reviewed_final_keeps_documental_grade_separate_from_missing_observation(self):
        result = ejemplo(research=True)
        result['estado_ejecucion'] = 'validado'
        result['validaciones'] = []
        validar_resultado(result, 'final')
        self.assertEqual(result['calculos']['general']['cobertura']['asignados'], 18)
        self.assertEqual(result['calculos']['general']['cobertura']['observados'], 17)
        self.assertIsNone(result['calculos']['general']['categoria_desempeno'])

    def test_final_requires_review_and_accepts_complete_validated_json(self):
        result = ejemplo(pending=False)
        result['estado_ejecucion'] = 'validado'
        with self.assertRaisesRegex(ValueError, 'revisiones pendientes'):
            validar_resultado(result, 'final')
        result['validaciones'] = []  # Simula una revisión resuelta en el JSON sintético.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            report = renderizar(path, Path(directory) / 'word', 'final')
            with zipfile.ZipFile(report['archivo']) as archive:
                root = ET.fromstring(archive.read('word/document.xml'))
                text = texto(root)
            grade_run = next(r for r in root.iter(W + 'r') if texto(r) == '5.00/5 — ACREDITACIÓN MUY ALTA')
            self.assertEqual(grade_run.find(W + 'rPr/' + W + 'color').get(W + 'val'), '008000')
            self.assertNotIn('BORRADOR', text)
            self.assertNotIn('PENDIENTE', text)
            self.assertIn('CALIFICACIÓN GENERAL: 5.00/5 — ACREDITACIÓN MUY ALTA', text)

    def test_contract_mismatch_blocks_output(self):
        result = ejemplo()
        result['contrato']['plantilla_sha256'] = 'incorrecto'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'contrato actual'):
                renderizar(path, Path(directory) / 'word')
            self.assertFalse((Path(directory) / 'word').exists())

    def test_aggregate_and_worksheet_inconsistencies_block_output(self):
        for key in ('calculos', 'hoja'):
            result = ejemplo(pending=False)
            if key == 'calculos':
                result['calculos']['general']['calificacion_final'] = 'MAL'
            else:
                result['contenido_word']['hoja_computo'][0]['general'] = '1'
            with self.assertRaises(ValueError):
                validar_resultado(result, 'borrador')

    def test_assignment_tampering_is_rejected_even_when_editorial_views_match(self):
        rules = json.loads(RULES.read_text())
        dictionary = json.loads(DICTIONARY.read_text())
        for field, replacement in (('puntaje_asignado', 5), ('base_calificacion', 'observado'),
                                   ('motivo_asignacion', 'Desempeño excelente sin evidencia.')):
            result = ejemplo()
            result['indicadores'][3]['evaluaciones']['general'][field] = replacement
            # Rehacer las vistas no legitima una asignación que contradice
            # la política; el renderizador debe recalcular la anotación.
            componer(result, dictionary, rules)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Asignación documental inconsistente'):
                validar_resultado(result, 'borrador')

    def test_methodology_and_individual_grades_cannot_hide_missing_evidence(self):
        fields = ('metodologia_calificacion', 'cobertura_general', 'sensibilidad_ultimo_periodo',
                  'calificacion_indicador_04_general')
        for field in fields:
            result = ejemplo()
            result['valores_plantilla'][field] = 'Todos los datos están acreditados.'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'editorial inconsistente|Calificación individual'):
                validar_resultado(result, 'borrador')

    def test_graph_cannot_label_unobserved_scores_as_confirmed_performance(self):
        result = ejemplo()
        result['valores_plantilla']['graficas_indicador_04'][0]['fuente'] = 'Desempeño confirmado.'
        with self.assertRaisesRegex(ValueError, 'carácter documental'):
            validar_resultado(result, 'borrador')

    def test_audit_rejects_yellow_marks_in_generated_text(self):
        for tag, attributes in (('highlight', {'val': 'yellow'}), ('shd', {'fill': 'ffff00'})):
            p = parrafo('Texto procedente del JSON')
            props = p.find(W + 'r/' + W + 'rPr')
            ET.SubElement(props, W + tag, {W + k: v for k, v in attributes.items()})
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'bad.docx'
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('word/document.xml', ET.tostring(p))
                with self.assertRaisesRegex(ValueError, 'amarillo'):
                    auditar(path)

    def test_audit_rejects_automatic_highlight_in_trace_style(self):
        styles = ET.Element(W + 'styles')
        style = ET.SubElement(styles, W + 'style', {W + 'styleId': STYLE})
        ET.SubElement(ET.SubElement(style, W + 'rPr'), W + 'highlight', {W + 'val': 'yellow'})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.docx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('word/document.xml', ET.tostring(parrafo('Texto JSON')))
                archive.writestr('word/styles.xml', ET.tostring(styles))
            with self.assertRaisesRegex(ValueError, 'amarillo'):
                auditar(path)

    def test_audit_rejects_yellow_in_original_fixed_text(self):
        root = ET.Element(W + 'document')
        root.append(parrafo('Texto JSON'))
        original = parrafo('Texto original', generated=False)
        ET.SubElement(original.find(W + 'r/' + W + 'rPr'), W + 'highlight', {W + 'val': 'yellow'})
        root.append(original)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.docx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('word/document.xml', ET.tostring(root))
            with self.assertRaisesRegex(ValueError, 'amarillo'):
                auditar(path)

    def test_audit_rejects_yellow_background_or_highlight_in_generated_chart(self):
        c = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
        a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
        for tag in ('solidFill', 'highlight'):
            graph = ET.Element(c + 'chartSpace')
            ET.SubElement(ET.SubElement(graph, a + tag), a + 'srgbClr', {'val': 'FFFF00'})
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'bad.docx'
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('word/document.xml', ET.tostring(parrafo('Texto JSON')))
                    archive.writestr('word/charts/pipeline_1.xml', ET.tostring(graph))
                with self.assertRaisesRegex(ValueError, 'Gráfica JSON con'):
                    auditar(path)

    def test_measurement_uses_editorial_fonts_and_native_chart_relationships(self):
        result = ejemplo()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            report = renderizar(path, Path(directory) / 'word', perfil='medicion')
            with zipfile.ZipFile(report['archivo']) as archive:
                root = ET.fromstring(archive.read('word/document.xml'))
                self.assertNotIn('DESARROLLO SOCIAL', texto(root))
                self.assertNotIn('{', texto(root))
                table = root.find('.//' + W + 'tbl')
                header = table.find(W + 'tr/' + W + 'tc/' + W + 'p')
                self.assertEqual(header.find(W + 'r/' + W + 'rPr/' + W + 'rFonts').get(W + 'ascii'), 'Archivo Medium')
                self.assertEqual(header.find(W + 'r/' + W + 'rPr/' + W + 'sz').get(W + 'val'), '24')
                self.assertEqual(header.find(W + 'pPr/' + W + 'spacing').get(W + 'line'), '280')
                self.assertEqual(len([n for n in archive.namelist() if n.endswith('.odttf')]), len(FONTS))
                charts = [n for n in archive.namelist() if n.startswith('word/charts/pipeline_')]
                self.assertEqual(len(charts), 18)  # Incluye base documental, sin inventar observaciones.
                for name in charts:
                    graph = ET.fromstring(archive.read(name))
                    c = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
                    a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
                    self.assertIsNotNone(graph.find(c + 'spPr/' + a + 'noFill'))
                    self.assertIsNone(graph.find('.//' + a + 'highlight'))
                    self.assertTrue(all(color.get('val', '').upper() != 'FFFF00' for color in graph.iter(a + 'srgbClr')))
                relations = ET.fromstring(archive.read('word/_rels/document.xml.rels'))
                chart_targets = [r.get('Target') for r in relations if r.get('Type', '').endswith('/chart')]
                self.assertEqual(len(chart_targets), len(charts))
                self.assertTrue(all('word/' + target in archive.namelist() for target in chart_targets))

    def test_visual_data_tampering_is_rejected(self):
        for kind in ('graph', 'table', 'worksheet'):
            result = json.loads(json.dumps(ejemplo()))
            if kind == 'graph':
                result['valores_plantilla']['graficas_indicador_01'][0]['valores'][0] = 1
            elif kind == 'table':
                result['valores_plantilla']['tablas_indicador_01'][0]['filas'][1][1] = 'Inventado'
            else:
                result['contenido_word']['hoja_computo'][0]['general'] = '1'
            with self.assertRaises(ValueError):
                validar_resultado(result, 'borrador')

    def test_embedded_fonts_match_official_font_bytes(self):
        from uuid import UUID
        from fuentes_word import FONTS
        with zipfile.ZipFile(TEMPLATE) as archive:
            fonts = ET.fromstring(archive.read('word/fontTable.xml'))
            for i, (family, filename, variant) in enumerate(FONTS, 1):
                f = next(n for n in fonts if n.get(W + 'name') == family)
                embed = f.find(W + variant)
                mask = UUID(embed.get(W + 'fontKey').strip('{}')).bytes[::-1]
                raw = bytearray(archive.read(f'word/fonts/archivo_{i}.odttf'))
                for j in range(32):
                    raw[j] ^= mask[j % 16]
                self.assertEqual(bytes(raw), (ROOT / 'assets/fonts' / filename).read_bytes())

    def test_final_rejects_missing_research_even_after_clearing_reviews(self):
        result = ejemplo(pending=False, research=False)
        result['estado_ejecucion'] = 'validado'
        result['validaciones'] = []
        with self.assertRaisesRegex(ValueError, 'Variable pendiente'):
            validar_resultado(result, 'final')

    def test_research_requires_reviewed_citations_and_known_minimum_sources(self):
        for kind in ('references', 'reviewer', 'citation', 'minimum', 'duplicate'):
            aporte = investigacion_sintetica()
            if kind == 'references':
                aporte['lineas'][0]['referencias'] = []
            elif kind == 'reviewer':
                aporte['lineas'][0]['referencias'][0]['revisado_por'] = ''
            elif kind == 'citation':
                aporte['lineas'][0]['analisis'] = 'Sin cita'
                aporte['lineas'][0]['apartados'] = {}
            elif kind == 'minimum':
                aporte['minimos_indicadores']['01']['referencias'] = ['https://example.org/desconocida']
            else:
                aporte['lineas'].append(deepcopy(aporte['lineas'][0]))
            with self.assertRaises(ValueError):
                validar_aporte(aporte)

    def test_pending_benchmark_cannot_claim_verified_content(self):
        result = ejemplo()
        result['valores_plantilla']['benchmark_proteccion_civil'] = 'Conclusión sin evidencia'
        with self.assertRaisesRegex(ValueError, 'Benchmark pendiente'):
            validar_resultado(result, 'borrador')

    def test_research_cannot_redirect_its_template_variable(self):
        result = ejemplo(pending=False)
        result['investigacion']['lineas'][0]['variable'] = 'municipio'
        with self.assertRaisesRegex(ValueError, 'Variable de benchmark'):
            validar_resultado(result, 'borrador')

    def test_recent_period_cannot_use_two_nonconsecutive_observations(self):
        result = ejemplo()
        result['indicadores'][0]['evaluaciones']['ultimo_periodo']['años_evaluados'] = [2020, 2022]
        with self.assertRaisesRegex(ValueError, 'mismo último periodo'):
            validar_resultado(result, 'borrador')

    def test_missing_municipal_year_cannot_be_scored_even_without_missing_flags(self):
        for keep_flags in (True, False):
            for mode in ('borrador', 'final'):
                with self.subTest(keep_flags=keep_flags, mode=mode):
                    result = ejemplo(pending=False)
                    section = result['indicadores'][0]
                    section['tablas'][0]['filas'].pop(1)
                    evaluation = section['evaluaciones']['ultimo_periodo']
                    if keep_flags:
                        evaluation.update(cobertura_temporal_insuficiente=True, años_faltantes=[2021])
                    # Reconstruir las vistas: no basta detectar una gráfica o
                    # tabla desincronizada, se debe revisar cobertura real.
                    componer(result, json.loads(DICTIONARY.read_text()), json.loads(RULES.read_text()))
                    result['estado_ejecucion'] = 'validado'
                    result['validaciones'] = []
                    with self.assertRaisesRegex(ValueError, 'cobertura temporal insuficiente'):
                        validar_resultado(result, mode)

    def test_missing_state_year_blocks_comparative_indicator_score(self):
        for number in (14, 15, 18):
            with self.subTest(number=number):
                result = ejemplo(pending=False)
                section = result['indicadores'][number - 1]
                section['tablas'][1]['filas'].pop(1)
                componer(result, json.loads(DICTIONARY.read_text()), json.loads(RULES.read_text()))
                with self.assertRaisesRegex(ValueError, f'Indicador {number}: cobertura temporal insuficiente'):
                    validar_resultado(result, 'borrador')

    def test_temporal_block_flag_cannot_coexist_with_a_score(self):
        result = ejemplo(pending=False)
        result['indicadores'][0]['evaluaciones']['ultimo_periodo']['cobertura_temporal_insuficiente'] = True
        with self.assertRaisesRegex(ValueError, 'puntaje reciente debe ser null'):
            validar_resultado(result, 'borrador')

    def test_research_topic_cannot_diverge_from_its_cited_content(self):
        result = ejemplo(pending=False)
        result['valores_plantilla']['investigacion_inteligencia_policial_hotspots'] = 'Contenido sustituido'
        with self.assertRaisesRegex(ValueError, 'Apartado del machote'):
            validar_resultado(result, 'borrador')

    def test_changed_original_blocks_contract_without_touching_files(self):
        contract = cargar_contrato()
        origin = ROOT / contract['plantillas']['medicion']['origen']
        def altered_hash(path):
            return 'cambio simulado' if path == origin else sha256(path)
        with patch('contrato.sha256', side_effect=altered_hash):
            with self.assertRaisesRegex(ValueError, 'machote de origen'):
                cargar_contrato()


if __name__ == '__main__':
    unittest.main()
