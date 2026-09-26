"""Contenido consultivo sin fugas técnicas y con evidencia numérica intacta."""
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
from componer_documento import componer, textos_metodologia
from redaccion_consultoria import comprobar_texto, motivo_publico, validar_publicacion
from renderizar_word import auditar, renderizar, texto, W
from test_word import ejemplo, DICTIONARY, RULES


class RedaccionTests(unittest.TestCase):
    def test_coverage_prose_handles_empty_and_complete_evidence(self):
        result = ejemplo()
        rules = json.loads(RULES.read_text())
        for period in ('general', 'ultimo_periodo'):
            result['calculos'][period]['cobertura'].update(observados=0, porcentaje=0, ponderada_porcentaje=0)
        values = textos_metodologia(result, rules)
        self.assertIn('ninguno de los 18 indicadores', values['cobertura_general'])
        self.assertEqual(values['cobertura_general'].count('%'), 1)
        for period in ('general', 'ultimo_periodo'):
            result['calculos'][period]['cobertura'].update(observados=18, porcentaje=100, ponderada_porcentaje=100)
            result['calculos'][period]['sensibilidad'].update(minimo=5, maximo=5)
        values = textos_metodologia(result, rules)
        self.assertIn('se reduce a 5.00/5', values['sensibilidad_general'])
        self.assertNotIn('indicadores sin evidencia suficiente', values['sensibilidad_general'])

    def compose(self, result):
        return componer(result, json.loads(DICTIONARY.read_text()), json.loads(RULES.read_text()))

    def test_internal_trace_is_retained_but_not_copied_into_narrative(self):
        result = ejemplo(research=True)
        result['fuentes'] = [{'archivo': 'Municipio de prueba PAQUETE SEGURIDAD.docx', 'sha256': 'a' * 64}]
        result['validaciones'].append({'codigo': 'REVISION_TECNICA', 'nivel': 'revision',
                                      'detalle': 'Consultar /Users/usuario/output/datos.json; SHA-256: ' + 'b' * 64})
        evidence = deepcopy({key: result[key] for key in ('indicadores', 'calculos', 'fuentes', 'investigacion_aportada')})
        self.compose(result)
        for key, expected in evidence.items():
            self.assertEqual(result[key], expected, key)
        self.assertIn('/Users/', result['validaciones'][-1]['detalle'])
        self.assertIn('Compendio de seguridad municipal', result['valores_plantilla']['bibliografia'])
        self.assertNotIn('SHA-256', result['valores_plantilla']['bibliografia'])
        self.assertNotIn('.docx', result['valores_plantilla']['bibliografia'])
        self.assertNotIn('revisado_por', result['valores_plantilla']['bibliografia'])
        self.assertEqual(validar_publicacion(result)['referencias_tecnicas_en_textos'], 0)

    def test_rejects_local_paths_files_codes_and_self_references(self):
        for fragment in ('El JSON fuente', 'reglas_calificacion.json', 'METODOLOGIA_CALIFICACION.md',
                         '/Users/persona/output/documento', 'C:\\trabajo\\datos',
                         'SHA-256: ' + 'a' * 64, 'PUNTAJE_NO_ACREDITADO',
                         'analisis_indicador_01', 'Como modelo de inteligencia artificial'):
            with self.subTest(fragment=fragment), self.assertRaisesRegex(ValueError, 'no publicable'):
                comprobar_texto(fragment)

    def test_public_citations_and_substantive_ai_topic_remain_allowed(self):
        comprobar_texto('Fuente: https://example.org/datos.json?script=referencia')
        comprobar_texto('El uso de inteligencia artificial en tareas policiales requiere evaluación y supervisión.')

    def test_incoming_research_is_not_silently_sanitized(self):
        result = ejemplo(research=True)
        line = result['investigacion_aportada']['lineas'][0]
        line['analisis'] += ' Consultar /Users/usuario/fuente.json.'
        original = deepcopy(result['investigacion_aportada'])
        with self.assertRaisesRegex(ValueError, 'no publicable'):
            self.compose(result)
        self.assertEqual(result['investigacion_aportada'], original)

    def test_table_cells_are_checked_without_rewriting_source_data(self):
        result = ejemplo()
        result['indicadores'][0]['tablas'][0]['filas'][1][1] = 'Consultar output/datos.json'
        original = deepcopy(result['indicadores'])
        with self.assertRaisesRegex(ValueError, 'no publicable'):
            self.compose(result)
        self.assertEqual(result['indicadores'], original)

    def test_pending_content_does_not_expose_variable_names(self):
        result = ejemplo()
        self.assertIsNone(result['valores_plantilla']['benchmark_proteccion_civil'])
        pending = result['contenido_word']['textos_pendientes']
        self.assertIn('referencias', pending['benchmark_proteccion_civil'])
        for key, value in pending.items():
            self.assertNotIn(key, value)
        validar_publicacion(result)

    def test_temporal_and_substantive_limits_are_not_erased(self):
        note = motivo_publico({'años_faltantes_por_ambito': {'estatal': [2023]}, 'puntaje': None}, 14)
        self.assertIn('estatales de 2023', note)
        self.assertNotIn('municipales', note)
        self.assertIn('población', motivo_publico({'motivo': 'Requiere homologación, denominadores o interpretación de la ficha.'}, 4))

    def test_recomposition_is_stable_for_narrative_and_controls(self):
        result = ejemplo(research=True)
        once = deepcopy(result)
        self.compose(result)
        self.assertEqual(result['valores_plantilla'], once['valores_plantilla'])
        self.assertEqual(result['contenido_word'], once['contenido_word'])
        self.assertEqual(result['control_redaccion'], once['control_redaccion'])

    def test_rendered_text_has_no_internal_trace_but_keeps_grades_and_sources(self):
        result = ejemplo(research=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prueba.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            report = renderizar(path, Path(directory) / 'word')
            self.assertTrue(report['sin_referencias_tecnicas_visibles_verificado'])
            with zipfile.ZipFile(report['archivo']) as archive:
                root = ET.fromstring(archive.read('word/document.xml'))
                body = '\n'.join(texto(p) for p in root.iter(W + 'p'))
            comprobar_texto(body)
            self.assertIn('NO ACREDITADO por información insuficiente', body)
            self.assertIn('https://example.org/proteccion_civil', body)
            self.assertIn('Alcance y aspectos por completar', body)
            self.assertNotIn('REVISION_EDITORIAL_WORD', body)
            self.assertNotIn('criterio_aplicado', body)

    def test_bad_narrative_does_not_overwrite_existing_word(self):
        result = ejemplo()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prueba.json'
            output = Path(directory) / 'word'
            output.mkdir()
            dest = output / 'municipio_de_prueba_seguridad_medicion_borrador.docx'
            dest.write_bytes(b'Existing output must survive validation failure')
            result['valores_plantilla']['analisis_indicador_01'] = 'Consulte datos.json para interpretar este indicador.'
            path.write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'no publicable'):
                renderizar(path, output)
            self.assertEqual(dest.read_bytes(), b'Existing output must survive validation failure')

    def test_stale_writing_contract_blocks_rendering(self):
        result = ejemplo()
        result['contrato']['redaccion_sha256'] = 'outdated'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prueba.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'redaccion_sha256'):
                renderizar(path, Path(directory) / 'word')


if __name__ == '__main__':
    unittest.main()
