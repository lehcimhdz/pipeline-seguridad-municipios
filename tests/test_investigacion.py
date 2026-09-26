"""La investigación debe corresponder al municipio, periodo y temas del Word."""
from copy import deepcopy
import json
import unittest
from test_word import ejemplo, investigacion_sintetica, DICTIONARY, RULES
from investigacion import integrar, validar_aporte
from componer_documento import componer


class InvestigacionTests(unittest.TestCase):
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
        from investigacion import narrativas
        narrativas(result, json.loads(RULES.read_text()))
        self.assertIn('No hay pares', result['valores_plantilla']['avances_municipales'])
        self.assertNotIn('coinciden', result['valores_plantilla']['avances_municipales'])

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
