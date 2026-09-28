import json
from decimal import Decimal
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from calificar import agregar, calificar_indicador, categoria, dependencias, definir_periodos
from documentos import sha256
from estructurar_reglas import construir

RULES = json.loads((ROOT / 'reglas_calificacion.json').read_text())
MAPPINGS = json.loads((ROOT / 'config/normalizaciones.json').read_text())


def section(number, rows, header=None):
    return {'numero': number, 'tablas': [{'ambito': 'municipal', 'tabla': 1,
                                        'filas': [header or ['Año', 'Existencia']] + rows}]}


def section_with_state(number, municipal, state, header):
    return {'numero': number, 'tablas': [
        {'ambito': 'municipal', 'tabla': 1, 'filas': [header] + municipal},
        {'ambito': 'estatal', 'tabla': 2, 'filas': [header] + state},
    ]}


def score(number, rows, period='general', header=None):
    return calificar_indicador(section(number, rows, header), RULES['fichas'][number - 1], period)


class CalificacionTests(unittest.TestCase):
    def test_rules_reproduce_source(self):
        self.assertEqual(construir(), RULES)
        self.assertEqual(sum(len(f['criterios']) for f in RULES['fichas']), 90)
        self.assertEqual(RULES['fuente']['sha256'], sha256(ROOT / RULES['fuente']['archivo']))

    def test_recent_period_is_calculated_from_data(self):
        rows = [['2020', 'No'], ['2023', 'Sí'], ['2024', 'Sí']]
        self.assertEqual(score(1, rows)['puntaje'], 4)
        self.assertEqual(score(1, rows, 'ultimo_periodo')['puntaje'], 5)

    def test_abandonment_precedes_intermittence(self):
        rows = [['2020', 'Sí'], ['2022', 'No'], ['2024', 'No']]
        self.assertEqual(score(1, rows)['puntaje'], 2)

    def test_blank_is_not_zero_and_not_skipped(self):
        rows = [['2020', 'Sí'], ['2023', 'Sí'], ['2024', '']]
        result = score(1, rows, 'ultimo_periodo')
        self.assertIsNone(result['puntaje'])
        self.assertEqual(result['años_evaluados'], [2023, 2024])

    def test_duplicate_year_needs_review(self):
        self.assertIsNone(score(1, [['2024', 'Sí'], ['2024', 'No']])['puntaje'])

    def test_percent_five_requires_minimum(self):
        header = ['Año', 'Porcentaje']
        self.assertEqual(score(5, [['2022', '95'], ['2024', '95']], header=header)['puntaje'], 5)
        rows = [[str(2014 + 2 * i), str(value)] for i, value in enumerate([80, 100, 100, 100, 100])]
        self.assertIsNone(score(5, rows, header=header)['puntaje'])

    def test_percent_gap_is_not_interpolated(self):
        self.assertIsNone(score(7, [['2022', '84.95']], header=['Año', 'Porcentaje'])['puntaje'])

    def test_invalid_percent_not_scored(self):
        for value in ('NaN', '101', '-2', ''):
            self.assertIsNone(score(5, [['2024', value]], header=['Año', 'Porcentaje'])['puntaje'])

    def test_courses_and_staff(self):
        header = ['Año', 'Número de cursos', 'Número de servidores capacitados']
        rows = [['2020', '0', '0'], ['2023', '60', '2,451'], ['2024', '52', '2,553']]
        self.assertEqual(score(2, rows, header=header)['puntaje'], 3)
        self.assertEqual(score(2, rows, 'ultimo_periodo', header)['puntaje'], 5)

    def test_protection_civil_topic_mapping(self):
        rows = [
            ['2023', 'Primeros auxilios'],
            ['2023', 'Evacuación, búsqueda y rescate'],
            ['2024', 'Prevención y combate de incendios, y manejo de extintores'],
            ['2024', 'Identificación y análisis de riesgos'],
        ]
        result = calificar_indicador(section(3, rows, ['Año', 'Tema impartido']), RULES['fichas'][2], 'ultimo_periodo', MAPPINGS)
        self.assertEqual(result['puntaje'], 4)

    def test_police_topic_mapping(self):
        rows = [
            ['2023', 'Derechos humanos y uso legítimo de la fuerza', '100', '60'],
            ['2023', 'Informe Policial Homologado', '100', '60'],
            ['2024', 'Primer respondiente', '50', '60'],
            ['2024', 'Informe Policial Homologado', '50', '60'],
        ]
        result = calificar_indicador(section(10, rows, ['Año', 'Tema', 'Total', 'Porcentaje']), RULES['fichas'][9], 'ultimo_periodo', MAPPINGS)
        self.assertEqual(result['puntaje'], 5)

    def test_calls_compare_state(self):
        item = section_with_state(
            15,
            [['2023', '50', '10'], ['2024', '60', '10']],
            [['2023', '40', '10'], ['2024', '50', '10']],
            ['Año', 'Porcentaje', 'Llamadas procedentes'],
        )
        result = calificar_indicador(item, RULES['fichas'][14], 'ultimo_periodo', MAPPINGS)
        self.assertEqual(result['puntaje'], 5)

    def test_invalid_or_missing_calls_are_not_assigned_a_score(self):
        for value in ('', '101', '-1'):
            item = section_with_state(15, [['2023', value], ['2024', '60']],
                                      [['2023', '50'], ['2024', '50']], ['Año', 'Porcentaje'])
            result = calificar_indicador(item, RULES['fichas'][14], 'ultimo_periodo')
            self.assertIsNone(result['puntaje'])

    def test_missing_police_topic_is_not_no_training(self):
        item = section(10, [['2023', '', '20', '50'], ['2024', '', '20', '50']],
                       ['Año', 'Tema', 'Total', 'Porcentaje'])
        result = calificar_indicador(item, RULES['fichas'][9], 'ultimo_periodo', MAPPINGS)
        self.assertIsNone(result['puntaje'])

    def test_unavailable_topic_markers_are_not_zero_topics(self):
        markers = ('N/D', 'ND', 'n.d.', 'S/D', 'sin información', 'no disponible',
                   'no especificado', 'no identificado', 'sin dato', 'sin datos',
                   'no se reporta', 'no aplica', '  SIN   INFORMACIÓN.  ')
        for number, header, extra in (
                (3, ['Año', 'Tema impartido'], []),
                (10, ['Año', 'Tema', 'Total', 'Porcentaje'], ['20', '50'])):
            for marker in markers:
                for period in ('general', 'ultimo_periodo'):
                    with self.subTest(indicador=number, valor=marker, periodo=period):
                        item = section(number, [[year, marker, *extra] for year in ('2023', '2024')], header)
                        result = calificar_indicador(item, RULES['fichas'][number - 1], period, MAPPINGS)
                        self.assertIsNone(result['puntaje'])
                        self.assertIn('Falta identificar', result['motivo'])
                        self.assertEqual(result['años_evaluados'], [2023, 2024])

    def test_known_topics_do_not_hide_a_missing_topic(self):
        for number, header, valid, extra in (
                (3, ['Año', 'Tema impartido'], 'Primeros auxilios', []),
                (10, ['Año', 'Tema', 'Total', 'Porcentaje'], 'Primer respondiente', ['20', '60'])):
            with self.subTest(indicador=number):
                item = section(number, [['2023', valid, *extra], ['2024', valid, *extra],
                                        ['2024', 'N/D', *extra]], header)
                result = calificar_indicador(item, RULES['fichas'][number - 1], 'ultimo_periodo', MAPPINGS)
                self.assertIsNone(result['puntaje'])

    def test_explicit_no_topics_and_noncore_topics_are_not_missing_markers(self):
        for number, header, extra in (
                (3, ['Año', 'Tema impartido'], []),
                (10, ['Año', 'Tema', 'Total', 'Porcentaje'], ['0', '0'])):
            for topic in ('Ninguno', 'Administración documental'):
                with self.subTest(indicador=number, tema=topic):
                    item = section(number, [[year, topic, *extra] for year in ('2023', '2024')], header)
                    result = calificar_indicador(item, RULES['fichas'][number - 1], 'ultimo_periodo', MAPPINGS)
                    self.assertEqual(result['puntaje'], 1)

    def test_historical_missing_topic_does_not_contaminate_complete_recent_period(self):
        for number, header, topic, extra, expected in (
                (3, ['Año', 'Tema impartido'], 'Primeros auxilios', [], 2),
                (10, ['Año', 'Tema', 'Total', 'Porcentaje'], 'Primer respondiente', ['20', '60'], 3)):
            with self.subTest(indicador=number):
                item = section(number, [['2022', 'N/D', *extra], ['2023', topic, *extra],
                                        ['2024', topic, *extra]], header)
                general = calificar_indicador(item, RULES['fichas'][number - 1], 'general', MAPPINGS)
                recent = calificar_indicador(item, RULES['fichas'][number - 1], 'ultimo_periodo', MAPPINGS)
                self.assertIsNone(general['puntaje'])
                self.assertEqual(recent['puntaje'], expected)

    def test_contextual_indicators_do_not_invent_external_evidence(self):
        for number in (4, 8, 9, 14, 18):
            item = section(number, [['2023', '2'], ['2024', '2']], ['Año', 'Total'])
            result = calificar_indicador(item, RULES['fichas'][number - 1], 'ultimo_periodo', MAPPINGS)
            self.assertIsNone(result['puntaje'])

    def test_census_recent_period_uses_two_editions_not_calendar_years(self):
        result = score(1, [['2022', 'Sí'], ['2024', 'Sí']], 'ultimo_periodo')
        self.assertEqual(result['puntaje'], 5)
        self.assertEqual(result['años_evaluados'], [2022, 2024])

    def test_recent_period_is_common_even_when_one_series_ends_earlier(self):
        sections = [section(1, [['2023', 'Sí'], ['2024', 'Sí']]),
                    section(16, [['2021', 'Sí'], ['2022', 'Sí']])]
        years = definir_periodos(sections)['ultimo_periodo']['por_indicador']['16']
        self.assertEqual(years, [2023, 2024])
        result = calificar_indicador(sections[1], RULES['fichas'][15], 'ultimo_periodo', años_objetivo=years)
        self.assertIsNone(result['puntaje'])
        self.assertEqual(result['años_evaluados'], years)

    def test_recent_comparison_requires_state_coverage(self):
        item = section_with_state(15, [['2023', '60', '10'], ['2024', '60', '10']],
                                  [['2022', '50', '10'], ['2024', '50', '10']],
                                  ['Año', 'Porcentaje', 'Llamadas procedentes'])
        result = calificar_indicador(item, RULES['fichas'][14], 'ultimo_periodo')
        self.assertIsNone(result['puntaje'])
        self.assertEqual(result['años_faltantes_por_ambito']['estatal'], [2023])

    def test_dependency_does_not_override_missing_period(self):
        results = {i: {'puntaje': 5} for i in range(1, 19)}
        results[2]['puntaje'] = 1
        results[3] = {'puntaje': None, 'cobertura_temporal_insuficiente': True}
        dependencias(results)
        self.assertIsNone(results[3]['puntaje'])

    def test_external_sources_require_explicit_review(self):
        self.assertTrue(RULES['politica_evidencia']['fuentes_externas'])
        self.assertIn('localizador', RULES['politica_evidencia']['condiciones_fuentes_externas'])

    def test_periods_distinguish_census_editions_from_annual_series(self):
        sections = [section(1, [['2020', 'Sí'], ['2022', 'Sí'], ['2024', 'Sí']]),
                    section(17, [['2020', '0'], ['2023', '1'], ['2024', '2']], ['Año', 'Total'])]
        periods = definir_periodos(sections)['ultimo_periodo']
        self.assertEqual(periods['por_indicador']['1'], [2022, 2024])
        self.assertEqual(periods['por_indicador']['16'], [2022, 2024])
        self.assertEqual(periods['por_indicador']['17'], [2023, 2024])
        self.assertEqual(periods['por_indicador']['18'], [2023, 2024])
        with self.assertRaises(ValueError):
            calificar_indicador(sections[1], RULES['fichas'][16], 'ultimo_periodo', años_objetivo=[2022, 2024])

    def test_five_topics_without_risk_analysis_is_ambiguous_not_catastrophic(self):
        topics = ['Sistema de Comando de Incidentes', 'Mapas de riesgo y alerta temprana',
                  'Evacuación, búsqueda y rescate', 'Primeros auxilios', 'Prevención y combate de incendios']
        item = section(3, [['2024', topic] for topic in topics], ['Año', 'Tema impartido'])
        result = calificar_indicador(item, RULES['fichas'][2], 'general', MAPPINGS)
        self.assertIsNone(result['puntaje'])
        self.assertEqual(len(result['temas_nucleo']), 5)

    def test_one_police_topic_does_not_count_as_two_core_groups(self):
        item = section(10, [[str(year), 'Proximidad social - Derechos humanos y uso legítimo de la fuerza', '100', '60']
                            for year in (2022, 2024)], ['Año', 'Tema', 'Total', 'Porcentaje'])
        result = calificar_indicador(item, RULES['fichas'][9], 'ultimo_periodo', MAPPINGS)
        self.assertEqual(result['puntaje'], 3)
        self.assertTrue(all(len(topics) == 1 for topics in result['cobertura_por_año'].values()))

    def test_uniform_groups_do_not_double_count_equivalent_garments(self):
        items = ['Camisola', 'Camisa', 'Botas', 'Zapatos tipo choclo', 'Pantalón', 'Gorra']
        rows = [[item, 'Si', 'Semestral', str(year)] for year in (2022, 2024) for item in items]
        item = section(8, rows, ['Elementos del uniforme', 'Otorgado', 'Frecuencia', 'Año'])
        result = calificar_indicador(item, RULES['fichas'][7], 'ultimo_periodo', MAPPINGS)
        self.assertEqual(result['puntaje'], 3)
        self.assertEqual(len(result['dotacion_por_edicion']['2024']['prendas_basicas']), 3)

    def test_complete_semiannual_uniforms_satisfy_annual_minimum(self):
        rows = [[item, 'Si', 'Semestral', str(year)] for year in (2022, 2024)
                for item in ['Camisola', 'Pantalón', 'Botas', 'Chamarra', 'Chaleco táctico']]
        item = section(8, rows, ['Elementos del uniforme', 'Otorgado', 'Frecuencia', 'Año'])
        self.assertEqual(calificar_indicador(item, RULES['fichas'][7], 'ultimo_periodo', MAPPINGS)['puntaje'], 5)
        item['tablas'][0]['filas'][-1][2] = ''
        self.assertIsNone(calificar_indicador(item, RULES['fichas'][7], 'ultimo_periodo', MAPPINGS)['puntaje'])

    def test_deaths_majority_is_established_without_imputing_blanks(self):
        rows = [['2019', '3'], ['2020', '1'], ['2021', ''], ['2022', ''], ['2023', '1'], ['2024', '2']]
        item = section(17, rows, ['Año', 'Total'])
        item['tablas'].append({'ambito': 'municipal', 'tabla': 2,
                              'filas': [['Año', 'Porcentaje'], ['2020', '187.9']]})
        general = calificar_indicador(item, RULES['fichas'][16], 'general')
        recent = calificar_indicador(item, RULES['fichas'][16], 'ultimo_periodo')
        self.assertEqual(general['puntaje'], 1)
        self.assertEqual(recent['puntaje'], 1)
        self.assertIsNone(general['fallecimientos_por_año']['2021'])
        self.assertFalse(general['sin_respuesta_municipal'])

    def test_missing_annual_rows_are_not_removed_from_death_majority(self):
        item = section(17, [['2020', '1'], ['2024', '1']], ['Año', 'Total'])
        result = calificar_indicador(item, RULES['fichas'][16], 'general')
        self.assertIsNone(result['puntaje'])
        self.assertEqual(result['años_sin_conteo'], [2021, 2022, 2023])

    def test_zero_deaths_and_isolated_cases_have_different_evidence_requirements(self):
        item = section(17, [['2022', '1'], ['2023', '0'], ['2024', '0']], ['Año', 'Total'])
        self.assertEqual(calificar_indicador(item, RULES['fichas'][16], 'general')['puntaje'], 4)
        self.assertEqual(calificar_indicador(item, RULES['fichas'][16], 'ultimo_periodo')['puntaje'], 5)
        item['tablas'][0]['filas'][1][1] = ''
        self.assertIsNone(calificar_indicador(item, RULES['fichas'][16], 'general')['puntaje'])

    def test_specific_dependencies(self):
        results = {i: {'puntaje': 5} for i in range(1, 19)}
        results[2]['puntaje'] = 1
        results[6]['puntaje'] = 1
        results[11]['puntaje'] = 1
        dependencias(results)
        self.assertEqual([results[i]['puntaje'] for i in (3, 6, 12)], [1, 3, 3])

    def test_document_example_and_cap_record(self):
        values = [1, 1, 1, 5, 5, 3, 4, 4, 4, 2, 1, 1, 1, 3, 3, 1, 3, 3]
        result = agregar({i: {'puntaje': v} for i, v in enumerate(values, 1)}, RULES)
        self.assertEqual(result['calificacion_final'], 'MAL')
        self.assertEqual(result['candados_aplicados'], [{'regla_id': 1, 'modifica_calificacion': False}])

    def test_no_partial_aggregate(self):
        results = {i: {'puntaje': 5} for i in range(1, 19)}
        results[18]['puntaje'] = None
        self.assertIsNone(agregar(results, RULES)['calificacion_final'])

    def test_optional_evaluable_method_has_equal_dimension_weights_and_discloses_coverage(self):
        scores = [3, 3, 5, None, 3, 5, 3, 3, None, 3, 5, 5, 5, None, 3, 5, 1, None]
        results = {i: {'puntaje': value} for i, value in enumerate(scores, 1)}
        summary = agregar(results, RULES, modo='evaluables')
        self.assertEqual(summary['estado'], 'calculado_parcial')
        self.assertEqual(summary['cobertura']['evaluables'], 14)
        self.assertEqual(summary['calificacion_final'], 'MUY BIEN')
        self.assertEqual(summary['indicadores_pendientes'], [4, 9, 14, 18])
        self.assertEqual(summary['promedios_dimension']['condiciones_del_personal'], '3.4')
        self.assertEqual(summary['intervalo_completo']['calificacion_minima'], 'REGULAR')
        self.assertEqual(summary['intervalo_completo']['calificacion_maxima'], 'MUY BIEN')
        self.assertIsNone(results[4]['puntaje'])

    def test_partial_aggregate_requires_two_thirds_in_each_dimension(self):
        results = {i: {'puntaje': 5} for i in range(1, 19)}
        for i in (4, 8, 9):
            results[i]['puntaje'] = None
        result = agregar(results, RULES, modo='evaluables')
        self.assertIsNone(result['calificacion_final'])
        self.assertEqual(result['dimensiones_con_cobertura_insuficiente'], ['condiciones_del_personal'])

    def test_partial_cannot_be_excellent_and_preserves_collapsed_dimension_cap(self):
        results = {i: {'puntaje': 5} for i in range(1, 19)}
        results[18]['puntaje'] = None
        result = agregar(results, RULES, modo='evaluables')
        self.assertEqual(result['calificacion_final'], 'MUY BIEN')
        self.assertIn({'regla_id': 'cobertura_parcial', 'modifica_calificacion': True}, result['candados_aplicados'])
        for i in (1, 2, 3):
            results[i]['puntaje'] = 1
        self.assertEqual(agregar(results, RULES, modo='evaluables')['calificacion_final'], 'REGULAR')

    def test_excellent_restriction_and_missing_response(self):
        results = {i: {'puntaje': 5} for i in range(1, 19)}
        results[18]['puntaje'] = 1
        self.assertEqual(agregar(results, RULES)['calificacion_final'], 'MUY BIEN')
        for i in range(1, 11):
            results[i]['puntaje'] = 1
        self.assertEqual(agregar(results, RULES, range(1, 11))['calificacion_final'], 'CATASTRÓFICO')

    def test_explicit_rounding(self):
        self.assertEqual(categoria(Decimal('3.495'), RULES), 'MUY BIEN')
        self.assertEqual(categoria(Decimal('3.494'), RULES), 'REGULAR')


if __name__ == '__main__':
    unittest.main()
