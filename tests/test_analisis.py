"""La interpretación es editorial; sus operaciones deben ser reproducibles."""
from copy import deepcopy
import unittest

from test_redaccion import ejemplo_editorial
from redaccion_editorial import validar_redaccion


class EvidenciaEditorialTests(unittest.TestCase):
    def test_admite_resta_documentada_sin_inventar_la_cifra(self):
        result, artifact, _, _ = ejemplo_editorial()
        artifact['hechos']['anterior'] = {'indicador': 1, 'tabla': 1, 'fila': 1, 'columna': 'Total', 'valor': '100'}
        artifact['hechos']['aumento'] = {'operacion': 'resta', 'operandos': ['h1', 'anterior'], 'decimales': 0, 'valor': '20'}
        artifact['bloques']['analisis_indicador_01'][0] = {
            'texto': 'El aumento fue de 20 unidades entre 2022 y 2024.', 'evidencia': ['h1', 'anterior', 'aumento']}
        self.assertEqual(validar_redaccion(result, artifact)['estado'], 'verificada')
        artifact['hechos']['aumento']['valor'] = '30'
        with self.assertRaisesRegex(ValueError, 'Cálculo editorial'):
            validar_redaccion(result, artifact)

    def test_variacion_porcentual_exige_denominador_y_valor_correctos(self):
        result, artifact, _, _ = ejemplo_editorial()
        artifact['hechos']['anterior'] = {'indicador': 1, 'tabla': 1, 'fila': 1, 'columna': 'Total', 'valor': '100'}
        artifact['hechos']['cambio'] = {'operacion': 'variacion_porcentual', 'operandos': ['h1', 'anterior'],
                                       'decimales': 1, 'valor': '20.0'}
        artifact['bloques']['analisis_indicador_01'][0] = {
            'texto': 'El crecimiento entre 2022 y 2024 fue de 20%.', 'evidencia': ['h1', 'anterior', 'cambio']}
        validar_redaccion(result, artifact)
        result['indicadores'][0]['tablas'][0]['filas'][1][1] = '0'
        artifact['hechos']['anterior']['valor'] = '0'
        with self.assertRaises(ValueError):
            validar_redaccion(result, artifact)

    def test_no_permite_usar_otro_indicador_como_unico_respaldo(self):
        result, artifact, _, _ = ejemplo_editorial()
        artifact['bloques']['analisis_indicador_01'][0]['evidencia'] = ['h2']
        with self.assertRaisesRegex(ValueError, 'su indicador'):
            validar_redaccion(result, artifact)

    def test_no_convierte_ausencia_en_cero(self):
        result, artifact, _, _ = ejemplo_editorial()
        result['indicadores'][0]['tablas'][0]['filas'][2][1] = ''
        artifact['hechos']['h1']['valor'] = ''
        artifact['bloques']['analisis_indicador_01'][0]['texto'] = 'En 2024 se registraron 0 unidades.'
        with self.assertRaisesRegex(ValueError, 'cifras sin respaldo'):
            validar_redaccion(result, artifact)

    def test_calculos_circulares_o_inexistentes_se_rechazan(self):
        for operands in (['h1', 'ausente'], ['ciclo', 'h1']):
            result, artifact, _, _ = ejemplo_editorial()
            artifact['hechos']['ciclo'] = {'operacion': 'resta', 'operandos': operands, 'valor': '0'}
            with self.assertRaisesRegex(ValueError, 'referencias inexistentes o circulares'):
                validar_redaccion(result, artifact)


if __name__ == '__main__':
    unittest.main()
