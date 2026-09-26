"""La investigación debe corresponder al municipio, periodo y temas del Word."""
from copy import deepcopy
import json
import unittest
from test_word import ejemplo, investigacion_sintetica, DICTIONARY, RULES
from investigacion import _indicadores, integrar, narrativas, referencia_visible, validar_aporte
from componer_documento import componer


class InvestigacionTests(unittest.TestCase):
    def test_complete_indicator_set_uses_collective_reference_without_expanding_numbers(self):
        for prep in ('', 'de', 'en', 'para'):
            with self.subTest(preposicion=prep):
                expected = (prep + ' ' if prep else '') + 'los 18 indicadores'
                self.assertEqual(_indicadores(range(1, 19), prep), expected)
                self.assertEqual(_indicadores(range(18, 0, -1), prep), expected)
        self.assertEqual(_indicadores([3, 4, 8], 'de'), 'de los indicadores 3, 4 y 8')
        self.assertEqual(_indicadores([4], 'de'), 'del indicador 4')
        self.assertNotIn('los 18 indicadores', _indicadores(range(2, 20)))

    def test_citations_can_be_in_the_corresponding_topic_without_duplicate_bibliography(self):
        aporte = investigacion_sintetica()
        aporte['lineas'][0]['analisis'] = 'Síntesis; las referencias se desarrollan en sus apartados.'
        validar_aporte(aporte)

    def test_rejects_research_for_another_municipality_or_period(self):
        for key, value in [('municipio', 'Otro municipio'), ('estado', 'Otra entidad'),
                           ('periodo_documental', {'desde': 2014, 'hasta': 2024})]:
            result = ejemplo(pending=False)
            result['investigacion_aportada'][key] = value
            with self.assertRaisesRegex(ValueError, 'otro'):
                integrar(result)

    def test_no_comparable_scores_is_not_reported_as_equal_performance(self):
        result = ejemplo(pending=False)
        for section in result['indicadores']:
            section['evaluaciones']['ultimo_periodo']['puntaje'] = None
            section['evaluaciones']['ultimo_periodo']['motivo'] = 'Falta un año.'
        narrativas(result, json.loads(RULES.read_text()))
        self.assertIn('no permite contrastar', result['valores_plantilla']['avances_municipales'])
        self.assertNotIn('coinciden', result['valores_plantilla']['avances_municipales'])

    def test_reader_facing_references_exclude_review_metadata_but_preserve_citations(self):
        result = ejemplo(pending=False)
        reference = result['investigacion_aportada']['lineas'][0]['referencias'][0]
        reference.update(autor='Autor académico', institucion='Institución de investigación',
                         revisado_por='Revisión documental asistida por IA', sha256='huella-tecnica-de-prueba',
                         fecha_revision='2026-09-26', aplicabilidad='Criterio técnico de aplicabilidad reservado')
        duplicate_line = result['investigacion_aportada']['lineas'][1]
        duplicate_line['referencias'].append(deepcopy(reference))
        duplicate_line['analisis'] += ' Fuente adicional: ' + reference['url']
        aporte_before = deepcopy(result['investigacion_aportada'])
        result['valores_plantilla']['bibliografia'] = 'Fuentes documentales municipales.'
        integrar(result)
        visible = result['valores_plantilla']['bibliografia']
        for text in ('Autor académico', 'Institución de investigación', reference['titulo'],
                     reference['url'], reference['localizador'], 'Consulta: ' + reference['fecha_consulta']):
            self.assertIn(text, visible)
        for text in (reference['revisado_por'], reference['sha256'], reference['fecha_revision'], reference['aplicabilidad']):
            self.assertNotIn(text, visible)
        self.assertEqual(visible.count('Autor académico'), 1)
        self.assertEqual(result['investigacion_aportada'], aporte_before)
        self.assertEqual(result['investigacion']['lineas'][0]['referencias'][0], reference)

    def test_reference_keeps_distinct_cited_locations_and_avoids_duplicate_authorship(self):
        result = ejemplo(pending=False)
        line = result['investigacion_aportada']['lineas'][0]
        reference = line['referencias'][0]
        reference.update(autor='Institución', titulo='Institución. Estudio consultado')
        self.assertEqual(referencia_visible(reference).count('Institución'), 1)
        other_location = deepcopy(reference)
        other_location['localizador'] = 'Sección complementaria, páginas 20–25'
        line['referencias'].append(other_location)
        result['valores_plantilla']['bibliografia'] = ''
        integrar(result)
        for cited in line['referencias']:
            self.assertIn(cited['localizador'], result['valores_plantilla']['bibliografia'])

    def test_supplied_research_is_preserved_literally_even_when_its_wording_is_not_editorial(self):
        result = ejemplo(pending=False)
        line = result['investigacion_aportada']['lineas'][0]
        line['analisis'] = 'Texto aportado: benchmark y puntaje interno. Fuente: ' + line['referencias'][0]['url']
        before = deepcopy(result['investigacion_aportada'])
        integrar(result)
        definition = result['investigacion']['lineas'][0]
        self.assertEqual(result['valores_plantilla'][definition['variable']], line['analisis'])
        self.assertEqual(result['investigacion_aportada'], before)
        for part in definition['apartados']:
            self.assertEqual(result['valores_plantilla'][part['variable']], line['apartados'][part['id']])

    def test_narratives_preserve_evidence_and_use_consulting_language(self):
        result = ejemplo()
        before_sections = deepcopy(result['indicadores'])
        before_calculations = deepcopy(result['calculos'])
        before_validations = deepcopy(result['validaciones'])
        before_research = deepcopy(result['investigacion'])
        narrativas(result, json.loads(RULES.read_text()))
        keys = ('introduccion_periodo_general', 'introduccion_ultimo_periodo', 'enfoque_gobierno',
                'criterio_lectura_graficas', 'bienes_a_proteger', 'comparacion_estatal_municipal',
                'avances_municipales', 'resumen_proteccion_civil', 'resumen_condiciones_personal',
                'resumen_inteligencia_eficiencia', 'tendencia_general', 'fortalezas_seguridad',
                'areas_mejora_seguridad', 'recomendaciones_gobierno', 'justificacion_prioridades')
        visible = '\n'.join(result['valores_plantilla'][key] for key in keys)
        for phrase in ('puntaje interno', 'benchmark', 'este bloque', 'JSON', 'sha256', 'revisado_por', 'pipeline'):
            self.assertNotIn(phrase.casefold(), visible.casefold())
        self.assertIn('6 de los 7 indicadores', result['valores_plantilla']['resumen_condiciones_personal'])
        self.assertIn('evidencia del indicador 4,', result['valores_plantilla']['recomendaciones_gobierno'])
        self.assertEqual(result['indicadores'], before_sections)
        self.assertEqual(result['calculos'], before_calculations)
        self.assertEqual(result['validaciones'], before_validations)
        self.assertEqual(result['investigacion'], before_research)
        self.assertIsNone(result['valores_plantilla']['benchmark_proteccion_civil'])

    def test_missing_recent_evidence_never_becomes_observed_strength_or_deficiency(self):
        result = ejemplo(pending=False)
        for section in result['indicadores']:
            section['evaluaciones']['ultimo_periodo']['puntaje'] = None
            section['evaluaciones']['ultimo_periodo']['puntaje_asignado'] = 5
        for dimension in result['contenido_word']['promedios_dimension']['ultimo_periodo']:
            result['contenido_word']['promedios_dimension']['ultimo_periodo'][dimension] = '1.00'
        narrativas(result, json.loads(RULES.read_text()))
        values = result['valores_plantilla']
        self.assertIn('no identifica indicadores', values['fortalezas_seguridad'])
        self.assertIn('no se identifican calificaciones observadas', values['areas_mejora_seguridad'].casefold())
        self.assertIn('Ninguno de los 3 indicadores', values['resumen_proteccion_civil'])
        self.assertIn('no ausencia de las capacidades', values['resumen_proteccion_civil'])
        self.assertIn('no un juicio de desempeño deficiente', values['introduccion_ultimo_periodo'])
        self.assertIn('No es posible establecer una trayectoria', values['tendencia_general'])

    def test_temporal_comparison_distinguishes_changed_and_equal_observed_scores(self):
        result = ejemplo(pending=False)
        rules = json.loads(RULES.read_text())
        narrativas(result, rules)
        self.assertIn('coinciden', result['valores_plantilla']['avances_municipales'])
        self.assertIn('no demuestra estabilidad', result['valores_plantilla']['tendencia_general'])
        result['indicadores'][0]['evaluaciones']['ultimo_periodo']['puntaje'] = 2
        narrativas(result, rules)
        self.assertIn('difieren', result['valores_plantilla']['avances_municipales'])
        self.assertIn('no bastan para establecer una tendencia', result['valores_plantilla']['tendencia_general'])
        self.assertIn('El indicador 1 registra', result['valores_plantilla']['areas_mejora_seguridad'])
        self.assertIn('Para el indicador 1, se recomienda', result['valores_plantilla']['recomendaciones_gobierno'])

    def test_unknown_dates_are_not_rendered_as_none_or_fabricated_years(self):
        result = ejemplo(pending=False)
        result['valores_plantilla'].update(año_inicial=None, año_final=None)
        narrativas(result, json.loads(RULES.read_text()))
        text = result['valores_plantilla']['introduccion_periodo_general']
        self.assertIn('requiere confirmar su delimitación temporal', text)
        self.assertNotIn('None', text)
        self.assertIsNone(result['valores_plantilla']['año_inicial'])
        self.assertIsNone(result['valores_plantilla']['año_final'])

    def test_recomposition_keeps_one_review_per_research_issue(self):
        result = ejemplo()
        dictionary = json.loads(DICTIONARY.read_text())
        rules = json.loads(RULES.read_text())
        componer(result, dictionary, rules)
        codes = [item['codigo'] for item in result['validaciones']]
        for code in ('INVESTIGACION_PENDIENTE', 'APARTADOS_INVESTIGACION_PENDIENTES',
                     'MINIMOS_PROTECCION_CIVIL_PENDIENTES'):
            self.assertEqual(codes.count(code), 1)

    def test_source_review_pending_is_preserved_and_not_duplicated(self):
        result = ejemplo(pending=False)
        result['investigacion_aportada']['pendientes_revision'] = ['Validar aplicabilidad municipal.']
        for _ in range(2):
            componer(result, json.loads(DICTIONARY.read_text()), json.loads(RULES.read_text()))
        reviews = [v for v in result['validaciones'] if v['codigo'] == 'REVISION_FUENTES_INVESTIGACION']
        self.assertEqual(len(reviews), 1)
        self.assertIn('aplicabilidad', reviews[0]['detalle'])


if __name__ == '__main__':
    unittest.main()
