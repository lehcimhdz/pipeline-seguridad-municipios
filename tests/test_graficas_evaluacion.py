"""Una gráfica puede aclarar un concepto sin acreditar datos que no expresa."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from correspondencias import resolver, requisitos_pendientes
from evaluacion_v23 import revisar_ficha
from valoracion_provisional import provisional

DEFS = json.loads((ROOT / 'config/definiciones_cngmd.json').read_text())
MAPPINGS = json.loads((ROOT / 'config/normalizaciones.json').read_text())


def graphic(n, title, scope='municipal'):
    return {'fuente': 'Villa Prueba PAQUETE SEGURIDAD.docx', 'fuente_sha256': 'f' * 64,
            'parte': f'word/media/{scope}.png', 'sha256': 'a' * 64,
            'indicador': n, 'ambito': scope, 'bloque': 3,
            'lectura': {'estado': 'leida', 'titulo': title, 'texto': title,
                        'idioma': 'spa', 'motor': 'Tesseract de prueba'}}


def section(n, readings):
    column = 'Porcentaje' if n == 5 else 'Total'
    return {'numero': n, 'nombre': 'Indicador de prueba', 'lecturas_graficas': readings,
            'tablas': [{'tabla': 1, 'ambito': 'municipal',
                        'filas': [['Año', column], ['2024', '90']]},
                       {'tabla': 2, 'ambito': 'estatal',
                        'filas': [['Año', column], ['2024', '900']]}]}


class GraficasEvaluacionTests(unittest.TestCase):
    def resolve(self, source, data=None):
        return resolver([source], MAPPINGS, DEFS, data or {})[str(source['numero'])]['2024']

    def test_aprobacion_no_se_convierte_en_vigencia(self):
        source = section(5, [graphic(5, 'Villa Prueba: Porcentaje de elementos de seguridad pública que '
                                     'aprobó las evaluaciones de control de confianza, (2016-2025)')])
        obs = self.resolve(source)
        self.assertEqual(obs['estatus_evaluaciones'], 'aprobadas')
        self.assertNotIn('definicion', obs)
        result = revisar_ficha(5, source, {'puntaje': 4}, [2024], [obs], {}, DEFS)
        self.assertIsNone(result['puntaje'])
        self.assertIn('vigencia', result['motivo'])
        self.assertIn('vigencia_de_las_evaluaciones_aprobadas', requisitos_pendientes(5, [2024], {'2024': obs}, {})['2024'])

    def test_camaras_en_ambos_ambitos_resuelven_funcionamiento_no_poblacion(self):
        source = section(14, [graphic(14, 'Villa Prueba: Número de cámaras en funcionamiento (2016-2024)'),
                              graphic(14, 'Entidad: Número de cámaras en funcionamiento (2016-2024)', 'estatal')])
        obs = self.resolve(source)
        self.assertEqual(obs['universo'], 'camaras_en_servicio')
        result = revisar_ficha(14, source, {}, [2024], [obs], {}, DEFS)
        self.assertIsNone(result['puntaje'])
        self.assertIn('poblaciones', result['motivo'])
        trace = obs['_trazabilidad']['universo']
        self.assertEqual(trace['tipo'], 'lectura_grafica')
        self.assertEqual({e['ambito'] for e in trace['evidencias']}, {'municipal', 'estatal'})
        reading = provisional(14, source, [2024], {'2024': obs}, result['motivo'], DEFS, MAPPINGS, {})
        self.assertIn('identifica cámaras en servicio', reading['condiciones'][0])
        self.assertNotIn('no acredita cámaras en servicio', reading['condiciones'][0])

    def test_un_ambito_no_acredita_el_otro(self):
        obs = self.resolve(section(14, [graphic(14, 'Villa Prueba: Número de cámaras en funcionamiento (2016-2024)')]))
        self.assertEqual(obs['universo_municipal'], 'camaras_en_servicio')
        self.assertNotIn('universo', obs)

    def test_fuera_de_periodo_o_municipio_no_se_transfiere(self):
        for title in ('Otro Municipio: Número de cámaras en funcionamiento (2016-2024)',
                      'Villa Prueba: Número de cámaras en funcionamiento (2016-2022)',
                      'Villa Prueba: Número de cámaras en funcionamiento'):
            with self.subTest(title=title):
                self.assertNotIn('universo_municipal', self.resolve(section(14, [graphic(14, title)])))

    def test_personal_no_excluye_administrativos(self):
        obs = self.resolve(section(4, [graphic(4, 'Villa Prueba: Número de elementos de seguridad pública (2014-2024)')]))
        self.assertEqual(obs['descripcion_personal'], 'elementos_seguridad_publica')
        self.assertNotIn('personal_policial', obs)

    def test_dos_titulos_incompatibles_se_conservan_como_conflicto(self):
        source = section(14, [graphic(14, 'Villa Prueba: Número de cámaras en funcionamiento (2016-2024)'),
                              graphic(14, 'Villa Prueba: Número de cámaras fuera de servicio (2016-2024)')])
        obs = self.resolve(source)
        self.assertTrue(obs['_conflictos'])
        self.assertNotIn('universo', obs)

    def test_sin_ocr_no_hay_homologacion(self):
        item = graphic(14, 'Villa Prueba: Número de cámaras en funcionamiento (2016-2024)')
        item['lectura']['estado'] = 'no_disponible'
        before = deepcopy(item)
        self.assertNotIn('universo_municipal', self.resolve(section(14, [item])))
        self.assertEqual(item, before)

    def test_otra_entidad_no_acredita_camaras_estatales(self):
        source = section(14, [graphic(14, 'Otra Entidad: Número de cámaras en funcionamiento (2016-2024)', 'estatal')])
        self.assertNotIn('universo_estatal', self.resolve(source, {'estado': 'Entidad de prueba'}))

    def test_complemento_no_revierte_equipos_fuera_de_servicio(self):
        source = section(14, [graphic(14, 'Villa Prueba: Número de cámaras fuera de servicio (2016-2024)')])
        data = {'observaciones': {'14': {'2024': {'revision': 'verificada', 'universo': 'camaras_en_servicio'}}}}
        self.assertTrue(self.resolve(source, data)['_conflictos'])


if __name__ == '__main__':
    unittest.main()
