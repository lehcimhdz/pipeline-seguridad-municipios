"""Pruebas de las decisiones nuevas, además de la regresión de las reglas base."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ponderacion import agregar_ponderado
from calificar import agregar
from evidencia_complementaria import validar, vacia, huella_objeto, tasas_comparables
from evaluacion_v23 import evaluar, revisar_ficha
from ejemplo_estudio import ejemplo
from test_redaccion import ejemplo_editorial
from redaccion_editorial import validar_redaccion, huella_evaluacion

RULES = json.loads((ROOT / 'reglas_calificacion.json').read_text())


def scores(value=4):
    return {i: {'puntaje': value} for i in range(1, 19)}


class PonderacionTests(unittest.TestCase):
    def test_promedio_y_coeficientes_completos(self):
        result = agregar_ponderado(scores(), RULES)
        self.assertEqual(Decimal(result['promedio_tres_dimensiones']), 4)
        weights = {int(i): Decimal(v) for i, v in result['pesos_efectivos'].items()}
        self.assertAlmostEqual(sum(weights.values()), Decimal(1))
        self.assertEqual(weights[2], Decimal('.125'))
        priorities = RULES['ponderacion_config']['ponderacion']['prioritarios']
        self.assertLessEqual(max(weights[i] for i in priorities) / min(weights[i] for i in priorities), 2)

    def test_monotonia_y_margen_prioritario(self):
        base = scores(3)
        value = Decimal(agregar_ponderado(base, RULES)['promedio_tres_dimensiones'])
        increases = {}
        for i in base:
            changed = deepcopy(base); changed[i]['puntaje'] = 4
            result = agregar_ponderado(changed, RULES)
            increases[i] = Decimal(result['promedio_tres_dimensiones']) - value
            self.assertGreater(increases[i], 0)
        self.assertGreater(increases[2], increases[1])
        self.assertGreater(increases[4], increases[6])
        self.assertGreater(increases[14], increases[15])

    def test_comparacion_aritmetica_no_reproduce_todos_los_candados(self):
        values = {i: {'puntaje': 1 + i % 5} for i in range(1, 19)}
        a = agregar_ponderado(values, RULES, esquema='dimensiones_iguales')
        b = agregar(values, RULES)
        self.assertAlmostEqual(Decimal(a['promedio_tres_dimensiones']), Decimal(b['promedio_tres_dimensiones']))

    def test_candado_7(self):
        values = scores(5); values[2]['puntaje'] = 3
        result = agregar_ponderado(values, RULES)
        self.assertEqual(result['calificacion_final'], 'MUY BIEN')
        self.assertIn(7, [c['regla_id'] for c in result['candados_aplicados']])

    def test_candado_8_no_exige_falta_de_respuesta(self):
        values = scores(5); values[4]['puntaje'] = 1
        self.assertEqual(agregar_ponderado(values, RULES)['calificacion_final'], 'REGULAR')

    def test_candado_9_exige_falta_de_respuesta_acreditada(self):
        values = scores(5)
        for i in (4, 5, 10, 14): values[i]['puntaje'] = 1
        self.assertEqual(agregar_ponderado(values, RULES)['calificacion_final'], 'REGULAR')
        for i in (4, 5, 10, 14): values[i]['sin_respuesta_municipal'] = True
        self.assertEqual(agregar_ponderado(values, RULES)['calificacion_final'], 'MAL')

    def test_prioritarios_insuficientes_aunque_cumpla_dimensiones(self):
        values = scores()
        for i in (4, 10, 14): values[i]['puntaje'] = None
        result = agregar_ponderado(values, RULES, modo='evaluables')
        self.assertEqual(result['cobertura']['prioritarios_evaluables'], 5)
        self.assertIsNone(result['calificacion_final'])

    def test_sensibilidad_y_provisional_no_imputan(self):
        values = scores(5); values[9]['puntaje'] = None
        values[9]['valoracion_provisional'] = {'nivel_indicativo': 3}
        before = deepcopy(values)
        result = agregar_ponderado(values, RULES, modo='evaluables')
        self.assertEqual(result['calificacion_final'], 'MUY BIEN')
        self.assertFalse(result['escenario_intermedio']['reduce_intervalo'])
        self.assertEqual(values, before)
        for value, key in ((1, 'promedio_minimo'), (5, 'promedio_maximo')):
            complete = deepcopy(values); complete[9]['puntaje'] = value
            self.assertEqual(result['intervalo_completo'][key], agregar_ponderado(complete, RULES)['promedio_tres_dimensiones'])

    def test_no_aplicable_no_es_cero_ni_incumplimiento(self):
        values = scores(); values[4] = {'puntaje': None, 'estado_dato': 'no_aplicable'}
        result = agregar_ponderado(values, RULES, modo='evaluables')
        self.assertIsNone(result['calificacion_final'])
        self.assertNotIn('intervalo_completo', result)

    def test_global_y_pesos_invalidos(self):
        result = agregar_ponderado(scores(), RULES, esquema='global')
        self.assertEqual(Decimal(result['promedio_tres_dimensiones']), 4)
        rules = deepcopy(RULES); rules['ponderacion_config']['ponderacion']['pesos']['2'] = 0
        with self.assertRaises(ValueError): agregar_ponderado(scores(), rules)


class EvidenciaTests(unittest.TestCase):
    def test_fixture_completa_y_sin_metadatos(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory)
            data = validar(result['evidencia_complementaria'], result['municipio'], result['estado'])
            self.assertEqual(huella_objeto(data), result['evidencia_complementaria_sha256'])
            mappings = json.loads((ROOT / 'config/normalizaciones.json').read_text())
            evaluations = evaluar(result['indicadores'], RULES, mappings, result['periodos_evaluacion'], vacia(result['municipio'], result['estado']))
            for n in (2, 3, 5, 7, 10, 15):
                self.assertIsNone(evaluations['general'][n]['puntaje'])
            self.assertIsNone(agregar_ponderado(evaluations['general'], RULES, modo='evaluables')['calificacion_final'])

    def test_fuente_modificada_y_localizador_ausente(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory); data = result['evidencia_complementaria']
            changed = deepcopy(data); changed['fuentes'][0]['sha256'] = '0' * 64
            with self.assertRaises(ValueError): validar(changed, result['municipio'], result['estado'])
            changed = deepcopy(data); del changed['poblacion'][0]['localizador']
            with self.assertRaises(ValueError): validar(changed, result['municipio'], result['estado'])

    def test_poblacion_no_positiva_rechazada(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory)
            for value in (0, -1, True, 'NaN', 'Infinity'):
                data = deepcopy(result['evidencia_complementaria']); data['poblacion'][0]['valor'] = value
                with self.subTest(value=value), self.assertRaises(ValueError):
                    validar(data, result['municipio'], result['estado'])

    def test_series_poblacionales_no_comparables(self):
        data = {'poblacion': [
            {'ambito': scope, 'anio': 2024, 'valor': 1000, 'serie': series, 'metodo': 'proyeccion', 'fecha_referencia': '2024-07-01'}
            for scope, series in (('municipal', 'a'), ('estatal', 'b'))]}
        self.assertIsNone(tasas_comparables(data, 2024, 10, 10))

    def test_llamadas_no_usan_porcentaje_como_eficacia(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory)
            self.assertEqual(result['indicadores'][14]['evaluaciones']['general']['puntaje'], 4)

    def test_llamadas_no_exigen_porcentaje_estatal_y_100_limita_a_tres(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory)
            section = result['indicadores'][14]
            section['tablas'] = [section['tablas'][0]]
            mappings = json.loads((ROOT / 'config/normalizaciones.json').read_text())
            values = evaluar(result['indicadores'], RULES, mappings, result['periodos_evaluacion'], result['evidencia_complementaria'])
            self.assertEqual(values['ultimo_periodo'][15]['puntaje'], 4)
            for row in section['tablas'][0]['filas'][1:]: row[1] = '100'
            values = evaluar(result['indicadores'], RULES, mappings, result['periodos_evaluacion'], result['evidencia_complementaria'])
            self.assertEqual(values['ultimo_periodo'][15]['puntaje'], 3)

    def test_pc_no_acumula_temas_de_años_distintos(self):
        defs = RULES['definiciones_config']
        groups = defs['normalizacion_proteccion_civil']['grupos']
        names = list(groups)
        rows = [['Año', 'Tema impartido']]
        rows.extend([str(y), groups[g][0]] for y, selected in ((2022, names[:3]), (2024, names[3:])) for g in selected)
        section = {'numero': 3, 'tablas': [{'ambito': 'municipal', 'tabla': 1, 'filas': rows}]}
        entries = [{'revision': 'verificada', 'grupos_captados': names, 'catalogo_completo': True} for _ in (2022, 2024)]
        result = revisar_ficha(3, section, {}, [2022, 2024], entries, {}, defs)
        self.assertEqual(result['puntaje'], 3)

    def test_mando_unico_no_equivale_a_sin_institucion(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory)
            data = result['evidencia_complementaria']
            data['observaciones']['4'] = {str(y): {'revision': 'verificada', 'mando_unico': True} for y in (2022, 2024)}
            mappings = json.loads((ROOT / 'config/normalizaciones.json').read_text())
            values = evaluar(result['indicadores'], RULES, mappings, result['periodos_evaluacion'], data)
            self.assertEqual(values['general'][11]['puntaje'], 5)
            for item in data['observaciones']['4'].values(): item['institucion_propia'] = False
            values = evaluar(result['indicadores'], RULES, mappings, result['periodos_evaluacion'], data)
            self.assertIsNone(values['general'][11]['puntaje'])
            self.assertEqual(values['general'][11]['estado_dato'], 'no_aplicable')

    def test_plantilla_menor_de_quince_tope_cuatro(self):
        section = {'numero': 4, 'tablas': []}
        data = {'poblacion': [{'anio': 2024, 'ambito': 'municipal', 'valor': 1000}]}
        result = revisar_ficha(4, section, {'años_evaluados': [2024]}, [2024],
            [{'revision': 'verificada', 'personal_policial': 10}], data, RULES['definiciones_config'])
        self.assertEqual(result['puntaje'], 4)


class EditorialTests(unittest.TestCase):
    def test_cambio_de_pesos_definiciones_textos_o_complemento_rechaza_prosa(self):
        for key in ('ponderacion_sha256', 'definiciones_sha256', 'textos_narrativos_sha256', 'evidencia_complementaria_sha256'):
            result, artifact, _, _ = ejemplo_editorial()
            artifact['vinculos'][key] = '0' * 64
            with self.subTest(key=key), self.assertRaises(ValueError): validar_redaccion(result, artifact)

    def test_sin_revision_semantica_o_con_marcadores(self):
        result, artifact, _, _ = ejemplo_editorial()
        artifact['seleccion_editorial']['1']['revision_semantica'] = False
        with self.assertRaises(ValueError): validar_redaccion(result, artifact)
        artifact['seleccion_editorial']['1']['revision_semantica'] = True
        artifact['bloques']['analisis_indicador_01'][0]['texto'] += ' {AÑOS}'
        with self.assertRaises(ValueError): validar_redaccion(result, artifact)

    def test_prioritario_bajo_no_se_omite_de_la_sintesis(self):
        result, artifact, _, _ = ejemplo_editorial()
        result['indicadores'][13]['evaluaciones']['general']['puntaje'] = 1
        artifact['vinculos']['evaluacion_sha256'] = huella_evaluacion(result)
        with self.assertRaisesRegex(ValueError, 'prioritario'): validar_redaccion(result, artifact)

    def test_cambio_de_evaluacion_invalida_la_redaccion(self):
        result, artifact, _, _ = ejemplo_editorial()
        result['calculos']['general']['promedio_tres_dimensiones'] = '4.00'
        with self.assertRaisesRegex(ValueError, 'evaluación'): validar_redaccion(result, artifact)


if __name__ == '__main__':
    unittest.main()
