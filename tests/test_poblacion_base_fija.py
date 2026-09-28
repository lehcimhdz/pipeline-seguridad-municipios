"""La base censal fija no se confunde con una población anual observada."""
from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from evidencia_complementaria import validar, tasas_comparables


class BaseFijaTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        source = Path(directory.name) / 'censo.txt'
        source.write_text('Población censal 2020', encoding='utf-8')
        records = []
        for year in (2022, 2024):
            for scope, value in (('municipal', 656464), ('estatal', 5784442)):
                records.append({'ambito': scope, 'anio': year, 'valor': value,
                                'serie': 'Censo de Población 2020', 'metodo': 'censo_base_fija',
                                'fecha_referencia': '2020-03-15', 'anio_referencia_poblacion': 2020,
                                'uso_como_base_fija': True, 'fuente': 'censo',
                                'localizador': f'{scope}, 2020', 'revision': 'verificada'})
        self.data = {'version': '1.0', 'municipio': 'Apodaca', 'estado': 'Nuevo León',
                     'fuentes': [{'id': 'censo', 'titulo': 'Censo 2020', 'archivo': str(source),
                                  'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
                     'poblacion': records, 'observaciones': {}}

    def test_censo_2020_y_tasas_de_referencia(self):
        data = validar(self.data, 'Apodaca', 'Nuevo León')
        municipal, estatal = tasas_comparables(data, 2024, 736, 736)
        self.assertEqual(municipal, Decimal(736) * 1000 / Decimal(656464))
        self.assertEqual(estatal, Decimal(736) * 1000 / Decimal(5784442))
        self.assertEqual(data['poblacion'][2]['anio_referencia_poblacion'], 2020)

    def test_no_se_acepta_censo_antiguo_sin_declaracion(self):
        data = deepcopy(self.data)
        record = next(r for r in data['poblacion'] if r['ambito'] == 'municipal' and r['anio'] == 2024)
        record.pop('uso_como_base_fija')
        with self.assertRaises(ValueError):
            validar(data, 'Apodaca', 'Nuevo León')

    def test_no_se_acepta_base_censal_futura(self):
        data = deepcopy(self.data)
        record = next(r for r in data['poblacion'] if r['ambito'] == 'municipal' and r['anio'] == 2022)
        record['anio'] = 2018
        with self.assertRaises(ValueError):
            validar(data, 'Apodaca', 'Nuevo León')


if __name__ == '__main__':
    unittest.main()
