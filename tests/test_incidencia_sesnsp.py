"""La incidencia se audita por fuente y territorio, nunca se infiere de remisiones."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from incidencia_sesnsp import total_anual
from evidencia_complementaria import validar

MONTHS = 'Enero,Febrero,Marzo,Abril,Mayo,Junio,Julio,Agosto,Septiembre,Octubre,Noviembre,Diciembre'


class IncidenciaTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.municipal = root / 'municipal.csv'
        self.estatal = root / 'estatal.csv'
        self.municipal.write_text(
            f'Año,Clave_Ent,Cve. Municipio,Tipo de delito,{MONTHS}\n'
            '2024,19,19006,Robo,1,2,0,0,0,0,0,0,0,0,0,0\n'
            '2024,19,19006,Lesiones,3,0,0,0,0,0,0,0,0,0,0,0\n'
            '2024,19,19039,Robo,99,0,0,0,0,0,0,0,0,0,0,0\n', encoding='utf-8')
        self.estatal.write_text(
            f'Año,Clave_Ent,Tipo de delito,{MONTHS}\n'
            '2024,19,Robo,10,10,0,0,0,0,0,0,0,0,0,0\n', encoding='utf-8')

    def test_ambitos_y_sha(self):
        local = total_anual(self.municipal, 2024, '19', '19006')
        state = total_anual(self.estatal, 2024, '19')
        self.assertEqual((local['valor'], local['filas']), (6, 2))
        self.assertEqual(state['valor'], 20)
        self.assertEqual(local['sha256'], hashlib.sha256(self.municipal.read_bytes()).hexdigest())

    def test_no_sumar_municipios_para_estado(self):
        with self.assertRaisesRegex(ValueError, 'CSV estatal'):
            total_anual(self.municipal, 2024, '19')

    def test_celda_faltante_no_es_cero(self):
        self.municipal.write_text(self.municipal.read_text().replace('Robo,1,2', 'Robo,NA,2'))
        with self.assertRaisesRegex(ValueError, 'no numérica'):
            total_anual(self.municipal, 2024, '19', '19006')

    def test_procedencia_por_campo_obligatoria_al_mezclar_fuentes(self):
        paths = [self.municipal, self.estatal]
        sources = [{'id': str(i), 'titulo': str(i), 'archivo': str(p),
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                   for i, p in enumerate(paths)]
        record = {'personas_mp': 4, 'delitos_municipales': 6,
                  'fuente': '0', 'localizador': 'm3s2p19, 2024', 'revision': 'verificada',
                  'evidencias_campos': {
                      'personas_mp': {'fuente': '0', 'localizador': 'm3s2p19, 2024', 'revision': 'verificada'},
                      'delitos_municipales': {'fuente': '1', 'localizador': 'CSV SESNSP, 2024', 'revision': 'verificada'}}}
        data = {'version': '1.0', 'municipio': 'Apodaca', 'estado': 'Nuevo León',
                'fuentes': sources, 'poblacion': [], 'observaciones': {'18': {'2024': record}}}
        self.assertEqual(validar(data, 'Apodaca', 'Nuevo León')['observaciones']['18']['2024'], record)
        record['evidencias_campos'].pop('delitos_municipales')
        with self.assertRaisesRegex(ValueError, 'Cada campo'):
            validar(data, 'Apodaca', 'Nuevo León')


if __name__ == '__main__':
    unittest.main()
