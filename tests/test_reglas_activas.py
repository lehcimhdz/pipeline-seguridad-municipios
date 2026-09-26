"""Regenerar el contrato editorial no debe restablecer parámetros metodológicos."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from estructurar_reglas import construir
from calificacion_documental import agregar_documental, asignar_calificaciones


class ReglasActivasTests(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads((ROOT / 'reglas_calificacion.json').read_text())

    def test_editorial_migration_preserves_custom_thresholds_weights_and_caps(self):
        self.rules['fichas'][0]['reglas_ejecutables'][1]['todas'][-1][-1] = 0.75
        self.rules['calificacion_documental']['pesos_dimension']['proteccion_civil'] = 2
        self.rules['calificacion_documental']['candados']['dimension_colapsada_minimo'] = 2
        original = deepcopy(self.rules)
        updated = construir(self.rules)
        self.assertEqual(updated['fichas'], original['fichas'])
        self.assertEqual(updated['calificacion_documental'], original['calificacion_documental'])
        self.assertEqual(self.rules, original)

    def test_migration_is_idempotent(self):
        once = construir(self.rules)
        self.assertEqual(construir(once), once)

    def test_bad_policy_is_rejected_not_silently_reset(self):
        self.rules['calificacion_documental']['pesos_dimension']['proteccion_civil'] = -1
        with self.assertRaisesRegex(ValueError, 'positivos'):
            construir(self.rules)

    def test_template_has_both_notes_for_all_indicators_and_method_variables(self):
        dictionary = json.loads((ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json').read_text())
        variables = dictionary['variables_documento']
        self.assertEqual(len(variables), 157)
        for number in range(1, 19):
            for period in ('general', 'ultimo_periodo'):
                key = f'calificacion_indicador_{number:02d}_{period}'
                self.assertEqual(variables[key]['apariciones'], 1)
                self.assertEqual(variables[key]['origen_contenido'], 'metodologia_documental_calculada')
        for key in ('metodologia_calificacion', 'cobertura_general', 'cobertura_ultimo_periodo',
                    'sensibilidad_general', 'sensibilidad_ultimo_periodo'):
            self.assertIn(key, variables)

    def test_documental_scale_change_is_effective_and_preserved(self):
        self.rules['calificacion_documental']['escala_documental'][1]['minimo'] = 4.1
        updated = construir(self.rules)
        evaluations = {number: {'puntaje': 4} for number in range(1, 19)}
        asignar_calificaciones(evaluations, updated)
        self.assertEqual(agregar_documental(evaluations, updated)['calificacion_final'], 'ACREDITACIÓN PARCIAL')


if __name__ == '__main__':
    unittest.main()
