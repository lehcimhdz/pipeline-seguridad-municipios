from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from calificacion_documental import (
    POLITICA_DOCUMENTAL, agregar_documental, asignar_calificaciones, validar_politica,
)
from calificar import agregar, calificar_indicador


def reglas():
    rules = json.loads((ROOT / 'reglas_calificacion.json').read_text())
    rules['calificacion_documental'] = deepcopy(POLITICA_DOCUMENTAL)
    return rules


def resultados(score=5):
    return {number: {'puntaje': score, 'criterio_aplicado': f'Ficha {number}',
                     **({'motivo': 'Falta evidencia comparable.'} if score is None else {})}
            for number in range(1, 19)}


class CalificacionDocumentalTests(unittest.TestCase):
    def setUp(self):
        self.rules = reglas()

    def test_missing_stays_null_but_receives_documental_floor(self):
        results = resultados()
        results[18] = {'puntaje': None, 'motivo': 'Falta denominador.', 'años_evaluados': [2023, 2024]}
        original = deepcopy(results[18])
        asignar_calificaciones(results, self.rules)
        self.assertEqual({key: results[18][key] for key in original}, original)
        self.assertEqual(results[18]['puntaje_asignado'], 1)
        self.assertEqual(results[18]['base_calificacion'], 'no_acreditado')
        self.assertIn('Falta denominador.', results[18]['motivo_asignacion'])
        self.assertIn('No demuestra mal desempeño', results[18]['motivo_asignacion'])
        self.assertEqual(results[1]['base_calificacion'], 'observado')

    def test_all_missing_produces_grade_but_not_performance(self):
        result = agregar_documental(asignar_calificaciones(resultados(None), self.rules), self.rules)
        self.assertEqual(result['calificacion_final'], 'NO ACREDITADO')
        self.assertIsNone(result['categoria_desempeno'])
        self.assertEqual(result['sensibilidad'], {'minimo': '1', 'maximo': '5'})
        self.assertEqual(result['cobertura']['observados'], 0)
        self.assertEqual(result['cobertura']['asignados'], 18)
        self.assertEqual(result['cobertura']['ponderada_porcentaje'], '0')
        self.assertNotIn(4, [item['regla_id'] for item in result['candados_aplicados']])

    def test_full_observations_retain_legacy_performance_and_caps(self):
        results = resultados()
        results[18]['puntaje'] = 1
        legacy = agregar(results, self.rules)
        result = agregar_documental(asignar_calificaciones(results, self.rules), self.rules)
        self.assertEqual(result['categoria_desempeno'], legacy['calificacion_final'])
        self.assertEqual(result['candados_aplicados'], legacy['candados_aplicados'])
        self.assertEqual(result['calificacion_final'], 'ACREDITACIÓN ALTA')
        self.assertEqual(result['sensibilidad']['minimo'], result['sensibilidad']['maximo'])
        self.assertEqual(Decimal(result['cobertura']['porcentaje']), 100)

    def test_equal_dimension_weights_are_not_equal_indicator_weights(self):
        results = resultados(3)
        for number in (4, 8, 9, 14, 17, 18):
            results[number]['puntaje'] = None
        result = agregar_documental(asignar_calificaciones(results, self.rules), self.rules)
        self.assertEqual(result['cobertura']['observados'], 12)
        self.assertAlmostEqual(float(result['cobertura']['porcentaje']), 66.6666666667)
        self.assertAlmostEqual(float(result['cobertura']['ponderada_porcentaje']), 73.2142857143)
        self.assertIsNone(result['categoria_desempeno'])

    def test_custom_weights_and_caps_are_consumed(self):
        results = resultados(5)
        for number in (1, 2, 3):
            results[number]['puntaje'] = 1
        asignar_calificaciones(results, self.rules)
        before = agregar_documental(results, self.rules)
        self.rules['calificacion_documental']['pesos_dimension']['proteccion_civil'] = 10
        after = agregar_documental(results, self.rules)
        self.assertLess(Decimal(after['promedio_tres_dimensiones']), Decimal(before['promedio_tres_dimensiones']))
        results = resultados(4)
        results[1]['puntaje'] = 1
        asignar_calificaciones(results, self.rules)
        before = agregar_documental(results, self.rules)
        self.rules['calificacion_documental']['candados']['dimension_colapsada_minimo'] = 4
        after = agregar_documental(results, self.rules)
        self.assertNotEqual(before['candados_aplicados'], after['candados_aplicados'])

    def test_assignment_tampering_is_rejected(self):
        for field, value in (('puntaje_asignado', 5), ('base_calificacion', 'observado'), ('motivo_asignacion', 'Aprobado')):
            results = asignar_calificaciones(resultados(None), self.rules)
            results[1][field] = value
            with self.assertRaisesRegex(ValueError, 'inconsistente'):
                agregar_documental(results, self.rules)

    def test_assigned_boolean_and_float_do_not_pass_as_integers(self):
        for value in (True, 1.0, '1'):
            results = asignar_calificaciones(resultados(None), self.rules)
            results[1]['puntaje_asignado'] = value
            with self.assertRaisesRegex(ValueError, 'integer'):
                agregar_documental(results, self.rules)

    def test_unspecified_training_topic_is_not_observed_failure(self):
        mappings = json.loads((ROOT / 'config/normalizaciones.json').read_text())
        for value in ('No especificado', 'No identificado', 'N/D', 'S/D'):
            section = {'numero': 10, 'tablas': [{'ambito': 'municipal', 'tabla': 1,
                'filas': [['Año', 'Tema', 'Total', 'Porcentaje'], ['2024', value, '10', '50']]}]}
            result = calificar_indicador(section, self.rules['fichas'][9], 'general', mappings)
            self.assertIsNone(result['puntaje'])

    def test_courses_require_consistent_nonnegative_integer_counts(self):
        for courses, staff in (('1.5', '2'), ('1', '2.5'), ('0', '5'), ('-1', '0')):
            section = {'numero': 2, 'tablas': [{'ambito': 'municipal', 'tabla': 1,
                'filas': [['Año', 'Número de cursos', 'Número de servidores capacitados'],
                          ['2024', courses, staff]]}]}
            result = calificar_indicador(section, self.rules['fichas'][1], 'general')
            self.assertIsNone(result['puntaje'])

    def test_score_and_presence_validation(self):
        for score in (True, 0, 6, 3.5, '3'):
            with self.assertRaisesRegex(ValueError, 'Puntaje observado inválido'):
                asignar_calificaciones(resultados(score), self.rules)
        results = resultados()
        results.pop(18)
        with self.assertRaisesRegex(ValueError, '1–18'):
            asignar_calificaciones(results, self.rules)
        results = resultados()
        results[1]['cobertura_temporal_insuficiente'] = True
        with self.assertRaisesRegex(ValueError, 'cobertura temporal'):
            asignar_calificaciones(results, self.rules)

    def test_policy_rejects_bad_weights_and_changed_floor(self):
        for bad in (0, -1, True, 'NaN', 'Infinity'):
            rules = reglas()
            rules['calificacion_documental']['pesos_dimension']['proteccion_civil'] = bad
            with self.assertRaises(ValueError):
                validar_politica(rules)
        self.rules['calificacion_documental']['piso_no_acreditado'] = 3
        with self.assertRaisesRegex(ValueError, 'extremo 1'):
            validar_politica(self.rules)

    def test_missing_data_is_not_nonresponse(self):
        results = asignar_calificaciones(resultados(None), self.rules)
        with self.assertRaisesRegex(ValueError, 'faltante no basta'):
            agregar_documental(results, self.rules, range(1, 11))
        results = asignar_calificaciones(resultados(1), self.rules)
        result = agregar_documental(results, self.rules, range(1, 11))
        self.assertIn(4, [item['regla_id'] for item in result['candados_aplicados']])

    def test_historical_threshold_gap_remains_unobserved(self):
        section = {'numero': 7, 'tablas': [{'ambito': 'municipal', 'tabla': 1,
                                          'filas': [['Año', 'Porcentaje'], ['2024', '84.95']]}]}
        results = resultados()
        results[7] = calificar_indicador(section, self.rules['fichas'][6], 'general')
        asignar_calificaciones(results, self.rules)
        self.assertIsNone(results[7]['puntaje'])
        self.assertEqual(results[7]['puntaje_asignado'], 1)

    def test_assignment_is_idempotent(self):
        results = asignar_calificaciones(resultados(None), self.rules)
        original = deepcopy(results)
        self.assertEqual(asignar_calificaciones(results, self.rules), original)

    def test_blank_topics_do_not_become_observed_low_performance(self):
        mappings = json.loads((ROOT / 'config/normalizaciones.json').read_text())
        for number, fields in ((3, ['Tema impartido']), (10, ['Tema', 'Total', 'Porcentaje'])):
            section = {'numero': number, 'tablas': [{'ambito': 'municipal', 'tabla': 1,
                'filas': [['Año'] + fields, ['2024'] + [''] * len(fields)]}]}
            result = calificar_indicador(section, self.rules['fichas'][number - 1], 'general', mappings)
            self.assertIsNone(result['puntaje'])

    def test_calls_invalid_or_incomplete_are_not_observed_scores(self):
        for value in ('', '-1', '101', 'NaN'):
            section = {'numero': 15, 'tablas': [
                {'ambito': 'municipal', 'tabla': 1,
                 'filas': [['Año', 'Porcentaje'], ['2023', value], ['2024', '60']]},
                {'ambito': 'estatal', 'tabla': 2,
                 'filas': [['Año', 'Porcentaje'], ['2023', '50'], ['2024', '50']]},
            ]}
            self.assertIsNone(calificar_indicador(section, self.rules['fichas'][14], 'general')['puntaje'])

    def test_zero_state_referrals_never_divides_by_zero(self):
        external = {'incidencia_municipal': {2024: Decimal('100')},
                    'incidencia_estatal': {2024: Decimal('1000')}}
        section = {'numero': 18, 'tablas': [
            {'ambito': 'municipal', 'tabla': 1, 'filas': [['Año', 'Total de personas'], ['2024', '10']]},
            {'ambito': 'estatal', 'tabla': 2, 'filas': [['Año', 'Total'], ['2024', '0']]},
        ]}
        result = calificar_indicador(section, self.rules['fichas'][17], 'general', external=external)
        self.assertIsNone(result['puntaje'])

    def test_negative_personnel_is_not_observed_low_performance(self):
        section = {'numero': 4, 'tablas': [{'ambito': 'municipal', 'tabla': 1,
                                          'filas': [['Año', 'Total'], ['2024', '-1']]}]}
        result = calificar_indicador(section, self.rules['fichas'][3], 'general',
                                    external={'poblacion_municipal': {2024: Decimal('1000')}})
        self.assertIsNone(result['puntaje'])


if __name__ == '__main__':
    unittest.main()
