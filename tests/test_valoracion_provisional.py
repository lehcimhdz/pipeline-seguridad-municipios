"""Inferencias acotadas, sin confundir presencia temática con cobertura policial."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from valoracion_provisional import provisional

DEFINITIONS = json.loads((ROOT / 'config/definiciones_cngmd.json').read_text())
MAPPINGS = json.loads((ROOT / 'config/normalizaciones.json').read_text())


def section(number, header, rows, state=None):
    tables = [{'tabla': 11, 'ambito': 'municipal', 'filas': [header, *rows]}]
    if state is not None:
        tables.append({'tabla': 12, 'ambito': 'estatal', 'filas': [header, *state]})
    return {'numero': number, 'tablas': tables}


def evaluate(number, source, years=(2022, 2024), obs=None, data=None):
    return provisional(number, source, years, obs or {}, 'Falta evidencia definitiva.',
                       DEFINITIONS, MAPPINGS, data)


class ValoracionProvisionalTests(unittest.TestCase):
    def test_temas_nucleo_homologados_sin_sumar_personas(self):
        source = section(10, ['Año', 'Tema', 'Total', 'Porcentaje'], [
            ['2024', 'Derechos humanos y uso legítimo de la fuerza', '90', '12.2'],
            ['2024', 'Uso legítimo de la fuerza', '90', '12.2'],
            ['2024', 'Informe Policial Homologado', '90', '12.2'],
            ['2024', 'Proximidad social: mediación', '90', '12.2']])
        before = deepcopy(source)
        result = evaluate(10, source)
        self.assertEqual(result['nivel_indicativo'], 3)
        self.assertEqual(len(result['grupos_acreditados']), 3)
        self.assertFalse(result['computa_en_agregacion'])
        self.assertEqual(result['anio_referencia'], 2024)
        self.assertEqual(source, before)
        self.assertEqual(result['evidencias'][0], {
            'ambito': 'municipal', 'anio': 2024, 'tabla': 11, 'fila': 2,
            'columna': 'Tema', 'valor': 'Derechos humanos y uso legítimo de la fuerza'})

    def test_no_promueve_temas_desconocidos_ni_profesionalizacion(self):
        source = section(10, ['Año', 'Tema', 'Total', 'Porcentaje'], [
            ['2024', 'Actualización en primer respondiente', '90', '12.2'],
            ['2024', 'Otro curso sin homologar', '90', '12.2'],
            ['2024', 'Informe Policial Homologado', '90', '12.2']])
        result = evaluate(10, source)
        self.assertEqual(result['nivel_indicativo'], 2)
        self.assertEqual(result['grupos_acreditados'], ['informe_policial_homologado'])
        self.assertEqual(len(result['profesionalizacion_excluida']), 1)
        self.assertEqual(result['temas_no_homologados'], ['Otro curso sin homologar'])

    def test_porcentaje_positivo_sin_total_acredita_tema_no_personas(self):
        source = section(10, ['Año', 'Tema', 'Total', 'Porcentaje'], [
            ['2024', 'Primer respondiente', '', '25']])
        self.assertEqual(evaluate(10, source)['nivel_indicativo'], 2)

    def test_ceros_y_desconocidos_no_acreditan_ausencia(self):
        for total, percentage in [('0', '0'), ('', ''), ('no disponible', 'ND')]:
            source = section(10, ['Año', 'Tema', 'Total', 'Porcentaje'], [
                ['2024', 'Primer respondiente', total, percentage]])
            self.assertIsNone(evaluate(10, source)['nivel_indicativo'])

    def test_contradicciones_y_porcentajes_invalidos_no_acreditan(self):
        for total, percentage in [('0', '20'), ('90', '101'), ('-90', '20'), ('90', '-20')]:
            source = section(10, ['Año', 'Tema', 'Total', 'Porcentaje'], [
                ['2024', 'Primer respondiente', total, percentage]])
            result = evaluate(10, source)
            self.assertIsNone(result['nivel_indicativo'])
            self.assertTrue(result['conflictos'])

    def test_conteo_positivo_y_porcentaje_cero_preservan_presencia_con_reserva(self):
        source = section(10, ['Año', 'Tema', 'Total', 'Porcentaje'], [
            ['2024', 'Primer respondiente', '3', '0.0']])
        result = evaluate(10, source)
        self.assertEqual(result['nivel_indicativo'], 2)
        self.assertEqual(result['grupos_acreditados'], ['primer_respondiente'])
        self.assertFalse(result['conflictos'])
        self.assertEqual(result['advertencias'][0]['tabla'], 11)
        self.assertEqual(result['advertencias'][0]['fila'], 2)
        self.assertIn('podría obedecer a redondeo', result['advertencias'][0]['motivo'])
        self.assertIn('no se afirma esa causa', ' '.join(result['condiciones']))

    def test_no_se_elige_anio_antiguo_para_ocultar_vacio_reciente(self):
        source = section(10, ['Año', 'Tema', 'Total'], [['2022', 'Primer respondiente', '90']])
        self.assertIsNone(evaluate(10, source)['nivel_indicativo'])

    def test_ausencia_requiere_confirmacion_no_solo_inferencia(self):
        source = section(10, ['Año', 'Tema', 'Total'], [['2024', 'Ninguno', '0']])
        observations = {'2024': {'ausencia_temas_nucleo_acreditada': True, 'revision': 'inferida'}}
        self.assertIsNone(evaluate(10, source, obs=observations)['nivel_indicativo'])
        observations['2024']['revision'] = 'verificada'
        self.assertEqual(evaluate(10, source, obs=observations)['nivel_indicativo'], 1)

    def test_pc_no_inventa_catalogo_a_partir_de_temas_impartidos(self):
        source = section(3, ['Año', 'Tema impartido'], [['2024', 'Primeros auxilios'], ['2024', 'Simulacros']])
        result = evaluate(3, source, years=[2024])
        self.assertIsNone(result['nivel_indicativo'])
        self.assertEqual(len(result['grupos_por_anio'][0]['grupos_acreditados']), 2)
        self.assertIsNone(result['grupos_por_anio'][0]['grupos_captados'])

    def test_plantilla_total_no_es_razon_por_habitantes(self):
        source = section(4, ['Año', 'Total'], [['2024', '1000']])
        result = evaluate(4, source)
        self.assertIsNone(result['nivel_indicativo'])
        self.assertTrue(result['base'])

    def test_camaras_preserva_continuidad_sin_afirmar_funcionamiento(self):
        source = section(14, ['Año', 'Total'], [['2022', '161'], ['2024', '177']])
        self.assertEqual(evaluate(14, source)['nivel_indicativo'], 3)
        source['tablas'][0]['filas'][1][1] = '0'
        self.assertEqual(evaluate(14, source)['nivel_indicativo'], 2)
        source['tablas'][0]['filas'][1][1] = ''
        self.assertIsNone(evaluate(14, source)['nivel_indicativo'])

    def test_llamadas_condiciona_lectura_sin_afirmar_operador(self):
        source = section(15, ['Año', 'Llamadas procedentes'], [['2022', '56638'], ['2024', '69446']])
        result = evaluate(15, source)
        self.assertEqual(result['nivel_indicativo'], 3)
        self.assertIn('No identifica al operador', result['condiciones'][0])
        self.assertFalse(result['computa_en_agregacion'])
        self.assertIsNone(evaluate(15, source, obs={'2024': {'registro_municipal': False}})['nivel_indicativo'])
        self.assertIsNone(evaluate(15, source, obs={'2024': {'ausencia_registro_acreditada': True}})['nivel_indicativo'])

    def test_llamadas_vacias_no_son_falta_de_registro_acreditada(self):
        source = section(15, ['Año', 'Llamadas procedentes'], [['2022', ''], ['2024', '69446']])
        self.assertIsNone(evaluate(15, source)['nivel_indicativo'])

    def test_equipo_exige_policias_y_naturaleza_y_no_elige_lectura_favorable(self):
        source = section(9, ['Año', 'Total'], [])
        observations = {'2024': {'personal_policial': 100, 'chalecos': 100}}
        self.assertIsNone(evaluate(9, source, years=[2024], obs=observations)['nivel_indicativo'])
        observations['2024']['naturaleza_del_dato'] = 'inventario_al_cierre'
        self.assertEqual(evaluate(9, source, years=[2024], obs=observations)['nivel_indicativo'], 4)
        observations['2024']['chalecos_asignados'] = 20
        self.assertIsNone(evaluate(9, source, years=[2024], obs=observations)['nivel_indicativo'])

    def test_equipo_describe_conteos_aunque_falte_denominador(self):
        source = section(9, ['Año', 'Equipamiento', 'Total'], [['2024', 'Chaleco balístico', '500']])
        result = evaluate(9, source, years=[2024])
        self.assertIsNone(result['nivel_indicativo'])
        self.assertIn('500 unidades', result['base'][0])
        self.assertTrue(result['evidencias'])

    def test_personas_se_describen_sin_inferir_destino(self):
        source = section(18, ['Año', 'Total de personas'], [['2024', '7475']])
        result = evaluate(18, source, years=[2024])
        self.assertIsNone(result['nivel_indicativo'])
        self.assertIn('7475 personas', result['base'][0])
        self.assertIn('no se presume su destino', result['base'][0])

    def test_remisiones_poblacionales_no_son_incidente_delictivo(self):
        source = section(18, ['Año', 'Total'], [['2024', '10']], state=[['2024', '100']])
        population = {'poblacion': [
            {'anio': 2024, 'ambito': scope, 'valor': value, 'serie': 'prueba',
             'metodo': 'proyeccion', 'fecha_referencia': '2024-07-01'}
            for scope, value in [('municipal', 1000), ('estatal', 10000)]]}
        observations = {'2024': {'remisiones_comparables': True, 'universo_remisiones': 'ministerio_publico'}}
        self.assertIsNone(evaluate(18, source, years=[2024], data=population)['nivel_indicativo'])
        result = evaluate(18, source, years=[2024], obs=observations, data=population)
        self.assertEqual(result['nivel_indicativo'], 3)
        self.assertFalse(result['computa_en_agregacion'])
        self.assertIn('No sustituye la incidencia', result['condiciones'][0])


if __name__ == '__main__':
    unittest.main()
