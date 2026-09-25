import json
from decimal import Decimal
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from calificar import agregar, calificar_indicador, categoria, dependencias
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

    def test_recent_period_is_calculated_from_data(self):
        rows = [['2020', 'No'], ['2022', 'Sí'], ['2024', 'Sí']]
        self.assertEqual(score(1, rows)['puntaje'], 4)
        self.assertEqual(score(1, rows, 'ultimo_periodo')['puntaje'], 5)

    def test_abandonment_precedes_intermittence(self):
        rows = [['2020', 'Sí'], ['2022', 'No'], ['2024', 'No']]
        self.assertEqual(score(1, rows)['puntaje'], 2)

    def test_blank_is_not_zero_and_not_skipped(self):
        rows = [['2020', 'Sí'], ['2022', 'Sí'], ['2024', '']]
        result = score(1, rows, 'ultimo_periodo')
        self.assertIsNone(result['puntaje'])
        self.assertEqual(result['años_evaluados'], [2022, 2024])

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
        rows = [['2020', '0', '0'], ['2022', '60', '2,451'], ['2024', '52', '2,553']]
        self.assertEqual(score(2, rows, header=header)['puntaje'], 3)
        self.assertEqual(score(2, rows, 'ultimo_periodo', header)['puntaje'], 5)

    def test_protection_civil_topic_mapping(self):
        rows = [
            ['2022', 'Primeros auxilios'],
            ['2022', 'Evacuación, búsqueda y rescate'],
            ['2024', 'Prevención y combate de incendios, y manejo de extintores'],
            ['2024', 'Identificación y análisis de riesgos'],
        ]
        result = calificar_indicador(section(3, rows, ['Año', 'Tema impartido']), RULES['fichas'][2], 'ultimo_periodo', MAPPINGS)
        self.assertEqual(result['puntaje'], 4)

    def test_police_topic_mapping(self):
        rows = [
            ['2022', 'Derechos humanos y uso legítimo de la fuerza', '100', '60'],
            ['2022', 'Informe Policial Homologado', '100', '60'],
            ['2024', 'Primer respondiente', '50', '60'],
            ['2024', 'Informe Policial Homologado', '50', '60'],
        ]
        result = calificar_indicador(section(10, rows, ['Año', 'Tema', 'Total', 'Porcentaje']), RULES['fichas'][9], 'ultimo_periodo', MAPPINGS)
        self.assertEqual(result['puntaje'], 4)

    def test_calls_compare_state(self):
        item = section_with_state(
            15,
            [['2022', '50', '10'], ['2024', '60', '10']],
            [['2022', '40', '10'], ['2024', '50', '10']],
            ['Año', 'Porcentaje', 'Llamadas procedentes'],
        )
        result = calificar_indicador(item, RULES['fichas'][14], 'ultimo_periodo', MAPPINGS)
        self.assertEqual(result['puntaje'], 4)

    def test_population_and_incidence_adapters(self):
        external = {
            'poblacion_municipal': {2022: Decimal('1000'), 2024: Decimal('1000')},
            'poblacion_estatal': {2022: Decimal('10000'), 2024: Decimal('10000')},
            'incidencia_municipal': {2022: Decimal('100'), 2024: Decimal('100')},
            'incidencia_estatal': {2022: Decimal('1000'), 2024: Decimal('1000')},
        }
        personnel = section(4, [['2022', '2'], ['2024', '2']], ['Año', 'Total'])
        self.assertEqual(calificar_indicador(personnel, RULES['fichas'][3], 'ultimo_periodo', MAPPINGS, external)['puntaje'], 4)
        cameras = section_with_state(14, [['2022', '2'], ['2024', '2']], [['2022', '10'], ['2024', '10']], ['Año', 'Total'])
        self.assertEqual(calificar_indicador(cameras, RULES['fichas'][13], 'ultimo_periodo', MAPPINGS, external)['puntaje'], 5)
        referrals = {
            'numero': 18,
            'tablas': [
                {'ambito': 'municipal', 'tabla': 1,
                 'filas': [['Año', 'Total de personas'], ['2022', '20'], ['2024', '20']]},
                {'ambito': 'estatal', 'tabla': 2,
                 'filas': [['Año', 'Total'], ['2022', '100'], ['2024', '100']]},
            ],
        }
        self.assertEqual(calificar_indicador(referrals, RULES['fichas'][17], 'ultimo_periodo', MAPPINGS, external)['puntaje'], 4)

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
