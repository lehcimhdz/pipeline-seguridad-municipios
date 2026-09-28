"""La base censal fija no se confunde con una población anual observada."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from evidencia_complementaria import validar, tasas_comparables


class BaseFijaTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'input/complementos/apodaca.json').read_text())

    def test_censo_2020_y_tasas_de_referencia(self):
        data = validar(self.data, 'Apodaca', 'Nuevo León')
        municipal, estatal = tasas_comparables(data, 2024, 736, 736)
        self.assertEqual(municipal, Decimal(736) * 1000 / Decimal(656464))
        self.assertEqual(estatal, Decimal(736) * 1000 / Decimal(5784442))
        self.assertEqual(data['poblacion'][4]['anio_referencia_poblacion'], 2020)

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
