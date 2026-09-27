"""Casos que pueden producir afirmaciones engañosas al describir la evidencia."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analisis_evidencia import analizar_indicador


def section(number, rows, headers=('Año', 'Total'), state=None):
    tables = [{'tabla': 1, 'ambito': 'municipal', 'filas': [list(headers), *rows]}]
    if state is not None:
        tables.append({'tabla': 2, 'ambito': 'estatal', 'filas': [list(headers), *state]})
    return {'numero': number, 'nombre': 'Ejemplo', 'tablas': tables}


class AnalisisTests(unittest.TestCase):
    def test_hallazgo_territorial_y_cambio_reciente_sin_inferir_suficiencia(self):
        data = section(4, [['2020', '1,005'], ['2022', '1,080'], ['2024', '736']])
        result = analizar_indicador(data, 'Apodaca', 'Nuevo León')
        self.assertIn('En Apodaca', result['parrafos'][0])
        self.assertIn('736 en 2024', result['parrafos'][0])
        self.assertIn('disminución de 344', result['parrafos'][0])
        self.assertIn('sin población', result['cierre'])
        self.assertNotIn('insuficiente', result['parrafos'][0])
        self.assertEqual(result['evidencia'][0]['filas'], [2, 3, 4])

    def test_faltante_reciente_no_se_sustituye_por_cero_o_por_el_ultimo_dato(self):
        data = section(14, [['2022', '161'], ['2024', '']])
        result = analizar_indicador(data, 'Apodaca', 'Nuevo León')
        self.assertIn('no hay información', result['parrafos'][0])
        self.assertIn('para 2024', result['parrafos'][0])
        self.assertIn('2022: 161', result['parrafos'][0])
        self.assertNotIn('a 0', result['parrafos'][0])
        self.assertNotIn('pasó de', result['parrafos'][0])

    def test_porcentajes_son_puntos_porcentuales_y_tienen_comparacion_estatal(self):
        data = section(7, [['2022', '72.8'], ['2024', '94.0']], ('Año', 'Porcentaje'),
                       [['2022', '66.5'], ['2024', '61.8']])
        text = ' '.join(analizar_indicador(data, 'Apodaca', 'Nuevo León')['parrafos'])
        self.assertIn('21.2 puntos porcentuales', text)
        self.assertIn('32.2 puntos porcentuales por encima', text)

    def test_conteos_municipales_y_estatales_no_se_comparan_como_cobertura(self):
        data = section(14, [['2022', '161'], ['2024', '177']], state=[['2022', '8,471'], ['2024', '12,896']])
        text = ' '.join(analizar_indicador(data, 'Apodaca', 'Nuevo León')['parrafos'])
        self.assertNotIn('por debajo', text)
        self.assertNotIn('por habitante', text)
        self.assertIn('12,896', text)

    def test_duplicados_impiden_elegir_una_cifra_arbitraria(self):
        data = section(4, [['2022', '100'], ['2024', '120'], ['2024', '140']])
        result = analizar_indicador(data, 'Apodaca', 'Nuevo León')
        self.assertIn('varias observaciones para 2024', result['parrafos'][0])
        self.assertNotIn('pasó', result['parrafos'][0])

    def test_no_infiere_tendencia_con_porcentaje_fuera_de_rango(self):
        data = section(17, [['2020', '187.9'], ['2023', '62.6'], ['2024', '42.6']], ('Año', 'Porcentaje'))
        text = ' '.join(analizar_indicador(data, 'Apodaca', 'Nuevo León')['parrafos'])
        self.assertIn('187.9%', text)
        self.assertIn('fuera del intervalo', text)
        self.assertNotIn('145.3', text)
        self.assertIn('disminución de 20 puntos porcentuales', text)

    def test_categorias_no_suman_personas_y_distinguen_cero(self):
        data = section(10, [['2024', 'Curso A', '90', '12.2'], ['2024', 'Curso B', '90', '12.2'],
                            ['2024', 'Curso C', '0', '0']], ('Año', 'Tema', 'Total', 'Porcentaje'))
        text = ' '.join(analizar_indicador(data, 'Apodaca', 'Nuevo León')['parrafos'])
        self.assertNotIn('180', text)
        self.assertIn('1 tema se reportan cero participantes', text)
        self.assertIn('no representa personas distintas', text)

    def test_fallecimientos_cero_en_desglose_no_prueban_cero_fallecidos(self):
        data = section(17, [['2024', 'Evento A', '0'], ['2024', 'Evento B', '']], ('Año', 'Evento', 'Total'))
        text = ' '.join(analizar_indicador(data, 'Apodaca', 'Nuevo León')['parrafos'])
        self.assertIn('debe cotejarse con el total de fallecimientos', text)
        self.assertIn('sin una cantidad disponible', text)
        self.assertNotIn('no hubo fallecimientos', text)

    def test_binarios_con_no_y_faltante_no_se_confunden(self):
        data = section(1, [['2020', 'Sí'], ['2022', 'No'], ['2024', '']], ('Año', 'Existencia'))
        text = ' '.join(analizar_indicador(data, 'Apodaca', 'Nuevo León')['parrafos'])
        self.assertIn('ausencia en 2022', text)
        self.assertIn('2024 no está confirmada', text)
        self.assertNotIn('ausencia en 2022 y 2024', text)

    def test_sin_cambio_reciente_tiene_concordancia(self):
        data = section(14, [['2020', '10'], ['2022', '20'], ['2024', '20']])
        text = ' '.join(analizar_indicador(data, 'Apodaca', 'Nuevo León')['parrafos'])
        self.assertIn('El valor de 2024 coincide con el de 2022.', text)
        self.assertNotIn('representa sin cambio', text)
        self.assertNotIn('supone sin cambio', text)

    def test_categorias_de_eventos_no_se_presentan_como_eventos_ocurridos(self):
        data = section(17, [['2024', 'Evento A', '2'], ['2024', 'Evento B', '0']], ('Año', 'Evento', 'Total'))
        text = ' '.join(analizar_indicador(data, 'Apodaca', 'Nuevo León')['parrafos'])
        self.assertIn('2 tipos de evento', text)
        self.assertNotIn('reporta 2 eventos', text)

    def test_prioridad_contextual_no_duplica_la_apertura_generica(self):
        data = section(7, [['2022', '72.8'], ['2024', '94.0']], ('Año', 'Porcentaje'))
        text = analizar_indicador(data, 'Apodaca', 'Nuevo León')['cierre']
        self.assertIn('avance reciente', text)
        self.assertEqual(text.count('vencimientos'), 1)


if __name__ == '__main__':
    unittest.main()
