"""Pruebas de retención de artefactos de salida."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from salidas import limpiar_salidas


class SalidasTests(unittest.TestCase):
    def test_conserva_unicamente_la_corrida_vigente(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_dir, word_dir = root / 'json', root / 'word'
            json_dir.mkdir()
            word_dir.mkdir()
            actual = json_dir / 'actual.json'
            recibo = json_dir / 'actual_renderizado.json'
            anterior = json_dir / 'anterior.json'
            word = word_dir / 'actual.docx'
            word_anterior = word_dir / 'anterior.docx'
            bloqueo = word_dir / '~$actual.docx'
            for path in (actual, recibo, anterior, word, word_anterior, bloqueo):
                path.write_text('x', encoding='utf-8')

            removidos = limpiar_salidas(json_dir, word_dir, json_actual=actual,
                                        recibo_actual=recibo, word_actual=word)

            self.assertEqual(removidos, {'json': 1, 'word': 1})
            self.assertTrue(actual.exists())
            self.assertTrue(recibo.exists())
            self.assertTrue(word.exists())
            self.assertTrue(bloqueo.exists())
            self.assertFalse(anterior.exists())
            self.assertFalse(word_anterior.exists())


if __name__ == '__main__':
    unittest.main()
