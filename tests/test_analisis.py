"""La narrativa debe poder rastrearse a valores, campos, años y tablas."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analisis_evidencia import analizar_indicador
from calificacion_documental import agregar_documental, asignar_calificaciones
from componer_documento import componer


def indicador(name, header, rows, number=1):
    return {'numero': number, 'nombre': name,
            'tablas': [{'tabla': number, 'ambito': 'municipal', 'filas': [header] + rows}],
            'evaluaciones': {'general': {'puntaje': 5, 'años_evaluados': [2022, 2024], 'criterio_aplicado': 'Prueba'},
                             'ultimo_periodo': {'puntaje': None, 'años_evaluados': [2023, 2024],
                                               'años_faltantes': [2023], 'motivo': 'Falta 2023.'}},
            'control_cruzado_anexo': {'tablas_identicas': True, 'calificacion_reportada_coincide': True}}


class AnalisisTests(unittest.TestCase):
    def test_zero_categories_do_not_highlight_an_arbitrary_maximum(self):
        section = indicador('Fallecimientos', ['Año', 'Evento', 'Total'],
                            [['2024', 'Enfrentamiento', '0'], ['2024', 'Accidente', '0'],
                             ['2024', 'Otra causa', '']])
        section['tablas'].append(deepcopy(section['tablas'][0]))
        reading = analizar_indicador(section)
        self.assertIn('2 observaciones con valor numérico de «Total» registran cero', reading['cierre'])
        self.assertNotIn('máximo', reading['cierre'])
        self.assertIn('no se interpretan como cero', reading['cierre'])
        self.assertEqual(reading['cierre'].count('Las cifras por categoría no se suman'), 1)

    def test_large_differences_use_thousands_separator(self):
        section = indicador('Recursos', ['Año', 'Total'], [['2022', '100,000'], ['2024', '43,087']])
        reading = analizar_indicador(section)
        self.assertIn('−56,913', reading['parrafos'][0])
        self.assertIn('−56,913', reading['cierre'])

    def test_known_magnitudes_are_named_without_relabeling_ambiguous_totals(self):
        for number, name in ((4, 'personal'), (14, 'cámaras'), (18, 'personas')):
            section = indicador('Indicador', ['Año', 'Total'], [['2022', '161'], ['2024', '177']], number)
            reading = analizar_indicador(section)
            self.assertIn(name, reading['parrafos'][0])
            self.assertNotIn('«Total»', reading['parrafos'][0])
            self.assertEqual(reading['evidencia'][0]['campos'], ['Total'])
        section = indicador('Egresos y fallecimientos', ['Año', 'Total'], [['2022', '3'], ['2024', '7']], 17)
        self.assertIn('«Total»', analizar_indicador(section)['parrafos'][0])

    def test_public_prose_keeps_source_paths_only_in_evidence(self):
        section = indicador('Personal', ['Año', 'Total'], [['2022', '10'], ['2024', '20']])
        before = deepcopy(section)
        source = '/Users/consultoria/input/word/Municipio PAQUETE SEGURIDAD.docx'
        reading = analizar_indicador(section, source)
        visible = ' '.join(reading['parrafos']) + ' ' + reading['cierre']
        for fragment in ('/Users/', 'input/', '.docx', 'JSON', 'etiquetas',
                         'unidad del campo', 'celdas', 'la evidencia municipal muestra lo siguiente'):
            self.assertNotIn(fragment, visible)
        self.assertTrue(reading['parrafos'][0].startswith('«Total» pasó de 10'))
        self.assertEqual(section, before)
        self.assertEqual(reading['evidencia'], [{'tabla': 1, 'ambito': 'municipal',
                          'años_observados': [2022, 2024], 'campos': ['Total'], 'fuente': source}])

    def test_closing_summarizes_without_copying_the_analysis(self):
        section = indicador('Personal', ['Año', 'Total'], [['2022', '10'], ['2024', '20']])
        reading = analizar_indicador(section)
        narrative = reading['parrafos'][0].split(' (Información municipal')[0]
        self.assertNotIn(narrative, reading['cierre'])
        self.assertIn('20 en 2024', reading['cierre'])
        self.assertIn('+10', reading['cierre'])
        self.assertNotIn('calificación reciente permanece pendiente', reading['cierre'])

    def test_recent_state_gaps_are_not_reported_as_municipal(self):
        section = indicador('Personal', ['Año', 'Total'], [['2023', '10'], ['2024', '20']])
        section['evaluaciones']['ultimo_periodo']['años_faltantes_por_ambito'] = {'estatal': [2023]}
        reading = analizar_indicador(section)
        self.assertIn('observaciones estatales de 2023', reading['cierre'])
        self.assertNotIn('observaciones municipales de 2023', reading['cierre'])

    def test_equal_endpoints_do_not_imply_a_continuous_trend(self):
        section = indicador('Personal', ['Año', 'Total'],
                            [['2020', '10.0'], ['2022', '4'], ['2024', '10']])
        reading = analizar_indicador(section)
        self.assertIn('10.0 en 2020 y 10 en 2024', reading['parrafos'][0])
        self.assertIn('sin cambio entre ambos extremos', reading['parrafos'][0])
        self.assertIn('frente a 4 en 2022', reading['cierre'])
        self.assertIn('+6', reading['cierre'])

    def test_unknown_unit_and_missing_latest_value_are_not_invented(self):
        section = indicador('Recursos', ['Año', 'Total'], [['2020', '5'], ['2022', '7'], ['2024', '']])
        reading = analizar_indicador(section)
        visible = ' '.join(reading['parrafos']) + reading['cierre']
        self.assertIn('No se dispone de un valor de «Total» para el año más reciente, 2024', reading['cierre'])
        self.assertIn('no equivale a cero', reading['cierre'])
        for inferred_unit in ('personas', 'equipos', 'pesos', 'unidades del campo'):
            self.assertNotIn(inferred_unit, visible)
        self.assertNotIn('variación de −7', visible)

    def test_presence_and_missing_values_remain_distinct(self):
        section = indicador('Plan', ['Año', 'Existencia'], [['2022', 'Sí'], ['2024', '']])
        reading = analizar_indicador(section)
        self.assertIn('no se dispone de una respuesta afirmativa o negativa en 2024', reading['parrafos'][0])
        self.assertIn('no acredita su funcionamiento efectivo', reading['cierre'])
        self.assertIn('no equivale a cero', reading['cierre'])

    def test_numeric_description_distinguishes_endpoints_from_latest_observations(self):
        section = indicador('Cámaras', ['Año', 'Total'],
                            [['2016', '0'], ['2018', '180'], ['2022', '161'], ['2024', '177']], 14)
        reading = analizar_indicador(section, 'Municipio PAQUETE SEGURIDAD.docx')
        body = ' '.join(reading['parrafos'])
        self.assertIn('0 en 2016 a 177 en 2024', body)
        self.assertIn('+177', body)
        self.assertIn('177 en 2024, frente a 161 en 2022', reading['cierre'])
        self.assertIn('+16', reading['cierre'])
        self.assertIn('2023–2024 es incompleta', reading['cierre'])
        self.assertIn('información de 2023', reading['cierre'])
        self.assertIn('Información municipal, cuadro 14; años 2016, 2018, 2022, 2024', body)
        self.assertEqual(reading['evidencia'][0]['fuente'], 'Municipio PAQUETE SEGURIDAD.docx')
        self.assertEqual(reading['evidencia'][0]['campos'], ['Total'])

    def test_percentage_difference_uses_percentage_points(self):
        section = indicador('Certificado', ['Año', 'Porcentaje'], [['2020', '70.9'], ['2024', '94.0']])
        reading = analizar_indicador(section)
        self.assertIn('+23.1 puntos porcentuales', reading['cierre'])
        self.assertNotIn('+23.1%', reading['cierre'])

    def test_presence_description_reports_absence_and_last_change(self):
        section = indicador('Plan', ['Año', 'Existencia'],
                            [['2018', 'Sí existe'], ['2020', 'No'], ['2022', 'No'], ['2024', 'Sí']])
        reading = analizar_indicador(section)
        body = ' '.join(reading['parrafos'])
        self.assertIn('existencia en 2018, 2024', body)
        self.assertIn('ausencia en 2020, 2022', body)
        self.assertIn('«Sí» en 2024, frente a «No» en 2022', reading['cierre'])
        self.assertIn('no acredita su funcionamiento efectivo', reading['cierre'])

    def test_empty_value_is_not_zero_and_does_not_create_change(self):
        section = indicador('Personal', ['Año', 'Total'], [['2022', ''], ['2024', '1,200']])
        reading = analizar_indicador(section)
        self.assertIn('no disponible', ' '.join(reading['parrafos']))
        self.assertIn('no equivale a cero', reading['cierre'])
        self.assertNotIn('variación de +', reading['cierre'])
        self.assertNotIn('0 en 2022', reading['cierre'])
        self.assertIn('1,200', reading['cierre'])

    def test_duplicate_year_is_not_averaged_or_subtracted(self):
        section = indicador('Personal', ['Año', 'Total'], [['2022', '10'], ['2024', '20'], ['2024', '30']])
        reading = analizar_indicador(section)
        self.assertIn('más de una observación para 2024', ' '.join(reading['parrafos']))
        self.assertIn('conciliar', reading['cierre'])
        self.assertNotIn('variación de', reading['cierre'])

    def test_category_values_are_cited_without_summing_people(self):
        section = indicador('Capacitación policial', ['Año', 'Tema', 'Total', 'Porcentaje'],
                            [['2022', 'Cadena de custodia', '100', '60'],
                             ['2024', 'Cadena de custodia', '100', '60'],
                             ['2024', 'Derechos humanos', '100', '60']])
        reading = analizar_indicador(section)
        self.assertIn('2 categorías distintas', ' '.join(reading['parrafos']))
        self.assertIn('uno de los valores máximos reportados de «Total»: 100', reading['cierre'])
        self.assertIn('porcentaje reportado para esta categoría es 60', reading['cierre'])
        self.assertIn('Las cifras por categoría no se suman', reading['cierre'])
        self.assertNotIn('200 personas', reading['cierre'])
        self.assertNotIn('120%', reading['cierre'])

    def test_category_maximum_uses_numeric_values_not_text_sort_order(self):
        section = indicador('Equipo', ['Equipamiento', 'Total', 'Año'],
                            [['Radios', '99', '2024'], ['Chalecos', '1,200', '2024']])
        reading = analizar_indicador(section)
        self.assertIn('«Chalecos» presenta el valor máximo reportado de «Total»: 1,200', reading['cierre'])

    def test_topic_names_and_uniform_frequency_are_preserved(self):
        topics = indicador('Temas', ['Año', 'Tema impartido'],
                           [['2022', 'Rescate'], ['2024', 'Rescate'], ['2024', 'Primeros auxilios']])
        self.assertIn('«Rescate», «Primeros auxilios»', analizar_indicador(topics)['cierre'])
        uniforms = indicador('Uniformes', ['Elementos del uniforme', 'Otorgado', 'Frecuencia', 'Año'],
                             [['Botas', 'Sí', 'Semestral', '2024']])
        closing = analizar_indicador(uniforms)['cierre']
        self.assertIn('«Botas»', closing)
        self.assertIn('«Frecuencia»: «Semestral»', closing)

    def test_state_totals_do_not_become_municipal_changes_or_ranking(self):
        section = indicador('Personal', ['Año', 'Total'], [['2022', '10'], ['2024', '20']])
        section['tablas'].append({'tabla': 20, 'ambito': 'estatal',
                                  'filas': [['Año', 'Total'], ['2022', '1,000'], ['2024', '2,000']]})
        reading = analizar_indicador(section)
        self.assertIn('1,000 en 2022 a 2,000 en 2024', ' '.join(reading['parrafos']))
        self.assertNotIn('2,000', reading['cierre'])
        self.assertIn('20 en 2024', reading['cierre'])
        self.assertIn('respecto de 10 en 2022', reading['cierre'])
        self.assertNotIn('supera al estado', reading['cierre'])

    def test_composition_preserves_visual_data_and_populates_specific_closings(self):
        dictionary = json.loads((ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json').read_text())
        rules = json.loads((ROOT / 'reglas_calificacion.json').read_text())
        sections = [indicador(ficha['nombre'], ['Año', 'Total'],
                              [['2022', str(ficha['id'])], ['2024', str(ficha['id'] * 10)]], ficha['id'])
                    for ficha in rules['fichas']]
        source_tables = deepcopy([section['tablas'] for section in sections])
        calculations = {}
        for period in ('general', 'ultimo_periodo'):
            evaluations = {section['numero']: section['evaluaciones'][period] for section in sections}
            asignar_calificaciones(evaluations, rules)
            calculations[period] = agregar_documental(evaluations, rules)
        result = {'municipio': 'Municipio de prueba', 'estado': 'Estado de prueba',
                  'valores_plantilla': {key: None for key in dictionary['variables_documento']},
                  'indicadores': sections, 'validaciones': [],
                  'fuentes': [{'archivo': 'Municipio PAQUETE SEGURIDAD.docx', 'sha256': 'Prueba'}],
                  'periodos_evaluacion': {'ultimo_periodo': {'años_objetivo': [2023, 2024]}},
                  'calculos': calculations}
        composed = componer(result, dictionary, rules)
        values = composed['valores_plantilla']
        self.assertIn('10 en 2024', values['cierre_indicador_01'])
        self.assertIn('respecto de 1 en 2022', values['cierre_indicador_01'])
        self.assertIn('180 en 2024', values['cierre_indicador_18'])
        self.assertIn('respecto de 18 en 2022', values['cierre_indicador_18'])
        self.assertIn('último periodo (2023–2024)', values['resumen_ultimo_periodo'])
        self.assertIn('2023–2024', composed['contenido_word']['periodo'])
        self.assertEqual(len({values[f'cierre_indicador_{number:02d}'] for number in range(1, 19)}), 18)
        for number, expected in enumerate(source_tables, 1):
            self.assertEqual(values[f'tablas_indicador_{number:02d}'][0]['filas'], expected[0]['filas'])
            self.assertEqual(values[f'graficas_indicador_{number:02d}'][0]['valores'], [5, 1])
            self.assertIn('información insuficiente', values[f'graficas_indicador_{number:02d}'][0]['fuente'])
            self.assertIsNone(sections[number - 1]['evaluaciones']['ultimo_periodo']['puntaje'])
        self.assertEqual(sections[0]['tablas'], source_tables[0])
        self.assertEqual(composed['contenido_word']['analisis'][0]['evidencia'][0]['tabla'], 1)


if __name__ == '__main__':
    unittest.main()
