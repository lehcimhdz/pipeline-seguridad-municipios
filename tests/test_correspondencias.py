"""Las homologaciones eliminan trámites, no inventan estadísticas."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from correspondencias import resolver
from evaluacion_v23 import evaluar
from evidencia_complementaria import vacia
from ejemplo_estudio import ejemplo
from renderizar_word import validar_resultado

RULES = json.loads((ROOT / 'reglas_calificacion.json').read_text())
MAPPINGS = json.loads((ROOT / 'config/normalizaciones.json').read_text())


def section(number, title, columns, details):
    return {'numero': number, 'nombre': title, 'tablas': [{
        'tabla': number, 'ambito': 'municipal', 'filas': [['Año', *columns], ['2024', *details]]}]}


class CorrespondenciasTests(unittest.TestCase):
    def resolve(self, sections, complemento=None):
        return resolver(sections, MAPPINGS, RULES['definiciones_config'], complemento or {})

    def test_cup_explicito_sin_complemento_es_homologacion_no_revision_humana(self):
        source = section(7, 'Certificado Único Policial vigente', ['Porcentaje'], ['94'])
        before = deepcopy(source)
        entry = self.resolve([source])['7']['2024']
        self.assertEqual(entry['definicion'], 'cup_vigente')
        self.assertEqual(entry['universo'], 'corporaciones_policiales')
        self.assertNotIn('revision', entry)
        trace = entry['_trazabilidad']['definicion']
        self.assertEqual(trace['tipo'], 'homologacion')
        self.assertEqual(trace['evidencias'][-1]['fila'], 2)
        self.assertEqual(source, before)

    def test_cup_invalido_o_generico_no_se_homologa(self):
        for title, percentage in [('CUP', '94'), ('Certificado Único Policial vigente', '101'),
                                  ('Certificado Único Policial vigente', 'ND')]:
            entry = self.resolve([section(7, title, ['Porcentaje'], [percentage])])['7']['2024']
            self.assertNotIn('definicion', entry)

    def test_confianza_y_personal_total_no_reciben_semantica_inventada(self):
        entries = self.resolve([section(5, 'Evaluaciones de control de confianza', ['Porcentaje'], ['89.9']),
                                section(4, 'Personal', ['Total'], ['736'])])
        self.assertNotIn('definicion', entries['5']['2024'])
        self.assertNotIn('personal_policial', entries['4']['2024'])
        self.assertEqual(entries['4']['2024']['total_personal_reportado'], '736')

    def test_solo_personal_policial_explicito_pasa_a_equipo(self):
        values = self.resolve([section(4, 'Personal', ['Personal policial'], ['50']),
                               section(9, 'Equipo', ['Equipamiento', 'Total'], ['Chaleco balístico', '60'])])
        equipment = values['9']['2024']
        self.assertEqual(equipment['personal_policial'], '50')
        self.assertEqual(equipment['chalecos'], '60')
        self.assertNotIn('radios', equipment)
        self.assertNotIn('naturaleza_del_dato', equipment)
        self.assertEqual(equipment['_trazabilidad']['personal_policial']['evidencias'][0]['tabla'], 4)

    def test_conflicto_no_sobrescribe_fuente_ni_se_vuelve_puntaje(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory)
            sections = result['indicadores']
            sections[6]['nombre'] = 'Certificado Único Policial vigente'
            data = deepcopy(result['evidencia_complementaria'])
            data['observaciones']['7']['2024']['definicion'] = 'cup_no_vigente'
            before = deepcopy(data)
            values = evaluar(sections, RULES, MAPPINGS, result['periodos_evaluacion'], data)
            for period in values.values():
                self.assertIsNone(period[7]['puntaje'])
                self.assertEqual(period[7]['estado_dato'], 'en_conflicto')
                self.assertIsNone(period[7]['valoracion_provisional']['nivel_indicativo'])
                self.assertTrue(period[7]['correspondencias']['2024']['conflictos'])
            self.assertEqual(data, before)

    def test_representaciones_equivalentes_no_crean_conflictos(self):
        data = {'observaciones': {'4': {'2024': {'revision': 'verificada', 'personal_policial': 50.0}}}}
        values = self.resolve([section(4, 'Personal', ['Personal policial'], ['50'])], data)
        self.assertFalse(values['4']['2024']['_conflictos'])

    def test_columnas_policiales_contradictorias_no_se_propaguen_a_equipo(self):
        values = self.resolve([section(4, 'Personal',
                               ['Personal de corporaciones policiales', 'Personal policial'], ['60', '50']),
                               section(9, 'Equipo', ['Equipamiento', 'Total'], ['Chaleco balístico', '60'])])
        self.assertTrue(values['4']['2024']['_conflictos'])
        self.assertNotIn('personal_policial', values['9']['2024'])

    def test_sin_complemento_recupera_cup_y_detalla_pendientes_reales(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory)
            result['indicadores'][6]['nombre'] = 'Certificado Único Policial vigente'
            values = evaluar(result['indicadores'], RULES, MAPPINGS, result['periodos_evaluacion'],
                             vacia(result['municipio'], result['estado']))
            for period in values.values():
                self.assertIsNotNone(period[7]['puntaje'])
                self.assertIn('poblacion_municipal_documentada', period[4]['requisitos_pendientes']['2024'])
                self.assertIn('personal_policial', period[4]['requisitos_pendientes']['2024'])
                self.assertEqual(period[10]['valoracion_provisional']['nivel_indicativo'], 3)
                self.assertEqual(period[15]['valoracion_provisional']['nivel_indicativo'], 3)
                self.assertIsNone(period[10]['puntaje'])
                self.assertIsNone(period[15]['puntaje'])

    def test_render_recalcula_correspondencias_y_rechaza_manipulacion(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(directory)
            entry = result['indicadores'][6]['evaluaciones']['general']['correspondencias']['2024']
            entry['campos']['definicion']['valor'] = 'inventada'
            with self.assertRaisesRegex(ValueError, 'evaluación difiere'):
                validar_resultado(result)


if __name__ == '__main__':
    unittest.main()
