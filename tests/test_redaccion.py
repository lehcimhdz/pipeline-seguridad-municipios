"""Control del contenido público, sus fuentes y la separación de trazabilidad."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from componer_documento import componer
from redaccion_consultoria import comprobar_texto, validar_publicacion


def ejemplo_consultivo():
    keys = ['municipio', 'estado', 'calificacion_general', 'calificacion_ultimo_periodo',
            'resumen_general', 'resumen_ultimo_periodo', 'introduccion_seguridad', 'conclusiones_seguridad', 'bibliografia']
    keys += [f'{kind}_indicador_{number:02d}' for number in range(1, 19)
             for kind in ('analisis', 'tablas', 'graficas', 'cierre')]
    dictionary = {'variables_documento': {key: {'apariciones_por_documento': {'medicion': 1}} for key in keys}}
    sections = []
    for number in range(1, 19):
        evaluation = {'puntaje': None, 'años_evaluados': [2023, 2024], 'años_faltantes': [2023],
                      'motivo': 'MOTIVO_INTERNO'}
        section = {'numero': number, 'nombre': f'Indicador {number}',
                   'evaluaciones': {period: deepcopy(evaluation) for period in ('general', 'ultimo_periodo')},
                   'tablas': [{'tabla': number, 'ambito': 'municipal',
                               'filas': [['Año', 'Total'], ['2022', '100'], ['2024', '120']]}]}
        sections.append(section)
    rules = {'dimensiones': {'proteccion_civil': [1, 2, 3], 'condiciones_del_personal': list(range(4, 11)),
                             'inteligencia_y_eficiencia_policial': list(range(11, 19))}}
    result = {'municipio': 'Apodaca', 'estado': 'Nuevo León',
              'valores_plantilla': {'municipio': 'Apodaca', 'estado': 'Nuevo León',
                                   'año_inicial': 2022, 'año_final': 2024,
                                   'tabla_calificaciones': [], 'tablas_municipales_indicador_01': []},
              'fuentes': [{'archivo': 'Apodaca PAQUETE SEGURIDAD.docx', 'sha256': 'a' * 64},
                          {'archivo': 'Apodaca Anexo.docx', 'sha256': 'b' * 64}],
              'indicadores': sections,
              'calculos': {p: {'calificacion_final': None, 'promedio_tres_dimensiones': None}
                           for p in ('general', 'ultimo_periodo')},
              'validaciones': [{'codigo': 'INDICADOR_PENDIENTE', 'nivel': 'bloqueante', 'detalle': 'MOTIVO_INTERNO'}]}
    return result, dictionary, rules


class RedaccionTests(unittest.TestCase):
    def test_compone_solo_medicion_y_preserva_pendientes_y_evidencia(self):
        result, dictionary, rules = ejemplo_consultivo()
        original = deepcopy(result['indicadores'])
        componer(result, dictionary, rules)
        self.assertEqual(result['version'], '2.1')
        self.assertEqual(result['contenido_word']['perfil'], 'seguridad_medicion_v2')
        self.assertIn('2022–2024', result['contenido_word']['periodo'])
        self.assertIn('(2022–2024)', result['contenido_word']['titulo'])
        self.assertNotIn('ultimo_periodo', result['contenido_word']['periodo'])
        self.assertEqual(set(result['valores_plantilla']), set(dictionary['variables_documento']))
        self.assertEqual(len(result['valores_plantilla']), 81)
        self.assertEqual(result['indicadores'], original)
        self.assertEqual(result['valores_plantilla']['graficas_indicador_04'], [])
        self.assertEqual(result['valores_plantilla']['calificacion_general'], 'PENDIENTE')
        self.assertEqual(len({result['valores_plantilla'][f'cierre_indicador_{i:02d}'] for i in range(1, 19)}), 18)
        self.assertIn('Apodaca', result['valores_plantilla']['introduccion_seguridad'])
        self.assertIn('2023', result['valores_plantilla']['resumen_ultimo_periodo'])
        self.assertIn('prioridad', result['valores_plantilla']['conclusiones_seguridad'])
        self.assertNotIn('Juárez', str(result['valores_plantilla']))
        self.assertNotIn('MOTIVO_INTERNO', str(result['valores_plantilla']))
        self.assertEqual(result['fuentes'][0]['sha256'], 'a' * 64)
        self.assertEqual(result['contenido_word']['control_redaccion']['perfil_redaccion'], 'diagnostico_consultivo')

    def test_recomponer_es_estable_y_no_pierde_periodo(self):
        result, dictionary, rules = ejemplo_consultivo()
        componer(result, dictionary, rules)
        before = deepcopy(result['valores_plantilla'])
        componer(result, dictionary, rules)
        self.assertEqual(result['valores_plantilla'], before)

    def test_bibliografia_legible_y_fuentes_limitadas(self):
        result, dictionary, rules = ejemplo_consultivo()
        result['fuentes'].append({'archivo': 'Apodaca PAQUETE GOBIERNO ABIERTO Y BUEN GOBIERNO.docx'})
        componer(result, dictionary, rules)
        bibliography = result['valores_plantilla']['bibliografia']
        self.assertEqual(len(bibliography.split('\n\n')), 2)
        self.assertNotIn('GOBIERNO', bibliography)
        self.assertNotIn('sha', bibliography.lower())
        self.assertNotIn('docx', bibliography)

    def test_guard_rechaza_tecnicismos_en_prosa_tablas_graficas_y_notas(self):
        base, dictionary, rules = ejemplo_consultivo()
        componer(base, dictionary, rules)
        cases = [
            ('prosa', lambda r: r['valores_plantilla'].update(resumen_general='Leer output/json/archivo.json')),
            ('tabla', lambda r: r['valores_plantilla']['tablas_indicador_01'][0]['filas'][1].__setitem__(1, 'SHA-256: ' + 'a' * 64)),
            ('grafica', lambda r: r['valores_plantilla'].update(graficas_indicador_01=[{'titulo': 'Gráfica', 'fuente': 'Criterio aplicado: Ficha 1'}])),
            ('nota', lambda r: r['contenido_word']['notas_alcance'].append('VARIABLES_ACTIVAS_PENDIENTES')),
        ]
        for label, mutate in cases:
            with self.subTest(label=label):
                result = deepcopy(base)
                mutate(result)
                with self.assertRaises(ValueError):
                    validar_publicacion(result)

    def test_guard_no_inspecciona_la_bitacora_tecnica(self):
        result, dictionary, rules = ejemplo_consultivo()
        componer(result, dictionary, rules)
        result['validaciones'].append({'codigo': 'PRUEBA_INTERNA', 'detalle': '/Users/local/output/result.json'})
        self.assertGreater(validar_publicacion(result)['textos_publicables_verificados'], 0)

    def test_guard_acepta_prosa_sustantiva(self):
        comprobar_texto('En Apodaca, el porcentaje pasó de 72.8% en 2022 a 94% en 2024. Conviene anticipar las renovaciones.')

    def test_guard_rechaza_nombre_interno_de_periodo(self):
        for text in ('Periodo de observaciones: ultimo_periodo.', 'Análisis de periodo_general.'):
            with self.assertRaisesRegex(ValueError, 'periodo_interno'):
                comprobar_texto(text)

    def test_periodo_publico_2014_2024_no_se_sobrescribe_al_agregar_dimensiones(self):
        result, dictionary, rules = ejemplo_consultivo()
        result['valores_plantilla']['año_inicial'] = 2014
        result['indicadores'][0]['tablas'][0]['filas'].insert(1, ['2014', '80'])
        componer(result, dictionary, rules)
        self.assertEqual(result['contenido_word']['periodo'],
                         'Periodo de observaciones: 2014–2024. La cobertura varía entre indicadores.')
        self.assertIn('(2014–2024)', result['contenido_word']['titulo'])


if __name__ == '__main__':
    unittest.main()
