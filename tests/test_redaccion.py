"""Impide publicar textos desactualizados, cifras inventadas o detalles internos."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from componer_documento import componer
from redaccion_editorial import BLOQUES, cargar_redaccion, validar_redaccion
from redaccion_consultoria import comprobar_texto, validar_publicacion


def ejemplo_editorial():
    sources = [{'archivo': 'Municipio Prueba PAQUETE SEGURIDAD.docx', 'sha256': 'a' * 64}]
    contract = {'benchmark_sha256': 'b' * 64, 'reglas_sha256': 'c' * 64}
    sections, facts, blocks = [], {}, {}
    for number in range(1, 19):
        sections.append({'numero': number, 'nombre': 'Indicador', 'tablas': [
            {'tabla': number, 'ambito': 'municipal', 'filas': [['Año', 'Total'], ['2022', '100'], ['2024', '120']]}],
            'evaluaciones': {period: {'puntaje': 3 if number <= 14 else None}
                            for period in ('general', 'ultimo_periodo')}})
        facts[f'h{number}'] = {'indicador': number, 'tabla': number, 'fila': 2, 'columna': 'Total', 'valor': '120'}
        blocks[f'analisis_indicador_{number:02d}'] = [
            {'texto': 'En 2024 se registraron 120 unidades. La distribución requiere revisión por turno.',
             'evidencia': [f'h{number}']}]
    for key in ('resumen_general', 'resumen_ultimo_periodo'):
        blocks[key] = [
            {'texto': 'La operación municipal dispone de 120 unidades en 2024.', 'evidencia': ['h1']},
            {'texto': 'El inventario permite examinar la distribución de recursos.', 'evidencia': ['h2']},
            {'texto': 'La prioridad es verificar su funcionamiento y asignación.', 'evidencia': ['h3']}]
    blocks['bibliografia'] = [{'texto': 'Información estadística municipal proporcionada para este estudio.', 'evidencia': []}]
    artifact = {'version': '2.2', 'municipio': 'Municipio Prueba', 'estado': 'Entidad Prueba',
                'vinculos': {**contract, 'fuentes': deepcopy(sources)},
                'revision': {'estado': 'revisada', 'tipo_autor': 'agente_editorial'},
                'hechos': facts, 'bloques': blocks, 'ilustraciones': []}
    result = {'municipio': artifact['municipio'], 'estado': artifact['estado'], 'fuentes': sources,
              'contrato': contract, 'indicadores': sections, 'validaciones': [],
              'periodos_evaluacion': {'general': {'años_objetivo': [2022, 2024]}},
              'calculos': {period: {'calificacion_final': 'REGULAR', 'promedio_tres_dimensiones': '3.00'}
                           for period in ('general', 'ultimo_periodo')}}
    dictionary = {'variables_documento': {key: {} for key in BLOQUES | {
        'municipio', 'estado', 'calificacion_general', 'calificacion_ultimo_periodo'}}}
    rules = {'dimensiones': {'proteccion_civil': [1, 2, 3], 'personal': list(range(4, 11)),
                            'inteligencia': list(range(11, 19))}}
    return result, artifact, dictionary, rules


class RedaccionTests(unittest.TestCase):
    def test_compone_solo_texto_revisado_y_conserva_evidencia(self):
        result, artifact, dictionary, rules = ejemplo_editorial()
        original = deepcopy(result['indicadores'])
        componer(result, dictionary, rules, artifact)
        self.assertEqual(result['version'], '2.2')
        self.assertEqual(result['contenido_word']['perfil'], 'estudio_seguridad')
        self.assertEqual(set(result['valores_plantilla']), set(dictionary['variables_documento']))
        self.assertEqual(len(result['valores_plantilla']), 25)
        self.assertTrue(all(isinstance(value, str) for value in result['valores_plantilla'].values()))
        self.assertEqual(result['indicadores'], original)
        self.assertIn('14 de los 18', result['valores_plantilla']['resumen_general'])
        self.assertNotIn('aviso_borrador', result['contenido_word'])
        self.assertEqual(result['valores_plantilla']['analisis_indicador_01'], artifact['bloques']['analisis_indicador_01'][0]['texto'])

    def test_no_hay_prosa_alternativa_si_falta_la_revision(self):
        with self.assertRaisesRegex(ValueError, 'Falta la interpretación'):
            cargar_redaccion(ROOT / 'input/redaccion/no_existe_para_prueba.json', municipio='Prueba')

    def test_recomponer_no_duplica_la_nota_metodologica(self):
        result, artifact, dictionary, rules = ejemplo_editorial()
        componer(result, dictionary, rules, artifact)
        before = deepcopy(result['valores_plantilla'])
        componer(result, dictionary, rules, artifact)
        self.assertEqual(result['valores_plantilla'], before)

    def test_rechaza_fuente_obsoleta_duplicada_o_con_alias_de_ruta(self):
        for mutation in ('hash', 'duplicada', 'ruta', 'otra_fuente'):
            with self.subTest(mutation=mutation):
                result, artifact, _, _ = ejemplo_editorial()
                sources = artifact['vinculos']['fuentes']
                if mutation == 'hash':
                    sources[0]['sha256'] = 'd' * 64
                elif mutation == 'duplicada':
                    sources.append(deepcopy(sources[0]))
                elif mutation == 'ruta':
                    sources[0]['archivo'] = '../' + sources[0]['archivo']
                else:
                    sources.append({'archivo': 'Municipio Prueba Anexo.docx', 'sha256': 'd' * 64})
                with self.assertRaises(ValueError):
                    validar_redaccion(result, artifact)

    def test_rechaza_otro_municipio_benchmark_reglas_y_falsa_revision(self):
        for mutation in ('municipio', 'benchmark_sha256', 'reglas_sha256', 'revision'):
            with self.subTest(mutation=mutation):
                result, artifact, _, _ = ejemplo_editorial()
                if mutation == 'municipio':
                    artifact['municipio'] = 'Otro municipio'
                elif mutation == 'revision':
                    artifact['revision']['estado'] = 'por_revisar'
                else:
                    artifact['vinculos'][mutation] = 'd' * 64
                with self.assertRaises(ValueError):
                    validar_redaccion(result, artifact)

    def test_rechaza_cifra_sin_evidencia_y_celda_manipulada(self):
        for mutation in ('texto', 'hecho', 'fila', 'referencia'):
            with self.subTest(mutation=mutation):
                result, artifact, _, _ = ejemplo_editorial()
                paragraph = artifact['bloques']['analisis_indicador_01'][0]
                if mutation == 'texto':
                    paragraph['texto'] = 'En 2024 se registraron 999 unidades.'
                elif mutation == 'hecho':
                    artifact['hechos']['h1']['valor'] = '999'
                elif mutation == 'fila':
                    artifact['hechos']['h1']['fila'] = 0
                else:
                    paragraph['evidencia'] = ['hecho_ausente']
                with self.assertRaises(ValueError):
                    validar_redaccion(result, artifact)

    def test_guard_rechaza_textos_de_trabajo_y_referencias_tecnicas(self):
        for text in ('Versión borrador.', 'Usar el machote.', 'Llenar la plantilla.',
                     'Leer output/json/archivo.json', 'Periodo ultimo_periodo.',
                     'Calificación desde VARIABLE_INTERNA.', 'Como modelo de inteligencia artificial, recomiendo revisar.'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                comprobar_texto(text)

    def test_guard_no_inspecciona_los_metadatos_tecnicos(self):
        result, artifact, dictionary, rules = ejemplo_editorial()
        componer(result, dictionary, rules, artifact)
        result['validaciones'].append({'codigo': 'PRUEBA_INTERNA', 'detalle': '/Users/local/output/result.json'})
        self.assertGreater(validar_publicacion(result)['textos_publicables_verificados'], 0)

    def test_calificacion_ausente_no_se_inventa_para_presentar_documento_final(self):
        result, artifact, dictionary, rules = ejemplo_editorial()
        result['calculos']['general']['calificacion_final'] = None
        componer(result, dictionary, rules, artifact)
        self.assertEqual(result['valores_plantilla']['calificacion_general'], 'SIN VALORACIÓN CONJUNTA')
        self.assertIn('completar la evidencia', result['valores_plantilla']['resumen_general'])


if __name__ == '__main__':
    unittest.main()
