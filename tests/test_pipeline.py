"""Alcance de entrada y publicación sin depender de datos municipales reales."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ejecutar_pipeline import discover, publicar, SUFFIXES
from test_word import ejemplo


class PipelineTests(unittest.TestCase):
    def test_only_two_sources_with_one_municipality_are_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for suffix in SUFFIXES:
                (path / ('Municipio' + suffix)).touch()
            (path / 'Municipio PAQUETE GOBIERNO ABIERTO.docx').touch()
            (path / '~$Municipio Anexo.docx').touch()
            name, sources = discover(path)
            self.assertEqual(name, 'Municipio')
            self.assertEqual(len(sources), 2)
            (path / 'Otro Anexo.docx').touch()
            with self.assertRaisesRegex(ValueError, 'exactamente un archivo'):
                discover(path)

    def test_mismatched_municipalities_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / ('Uno' + SUFFIXES[0])).touch()
            (path / ('Dos' + SUFFIXES[1])).touch()
            with self.assertRaisesRegex(ValueError, 'compartir un municipio'):
                discover(path)

    def test_failed_render_preserves_previous_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'json').mkdir()
            (output / 'word').mkdir()
            old_json = output / 'json/municipio_de_prueba_diagnostico_seguridad_municipal.json'
            old_word = output / 'word/municipio_de_prueba_seguridad_medicion_borrador.docx'
            old_json.write_text('Entrega anterior', encoding='utf-8')
            old_word.write_bytes(b'Entrega anterior')
            with patch('renderizar_word.renderizar', side_effect=ValueError('Revisión pendiente')):
                with self.assertRaisesRegex(ValueError, 'Revisión pendiente'):
                    publicar(ejemplo(), output, 'borrador')
            self.assertEqual(old_json.read_text(), 'Entrega anterior')
            self.assertEqual(old_word.read_bytes(), b'Entrega anterior')
            self.assertFalse(list(output.glob('.publicacion-*')))

    def test_publishes_one_word_one_json_and_receipt_with_stable_names(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            dest, report, removed = publicar(ejemplo(), output, 'borrador')
            self.assertEqual(dest.name, 'municipio_de_prueba_diagnostico_seguridad_municipal.json')
            self.assertEqual(len(list((output / 'json').glob('*.json'))), 2)
            self.assertEqual(len(list((output / 'word').glob('*.docx'))), 1)
            receipt = next((output / 'json').glob('*_renderizado.json'))
            saved = json.loads(receipt.read_text())
            self.assertEqual(saved['json_fuente'], str(dest))
            self.assertTrue(Path(saved['archivo']).exists())
            self.assertNotIn('.publicacion-', receipt.read_text())
            publicar(ejemplo(), output, 'borrador')
            self.assertEqual(len(list((output / 'word').glob('*.docx'))), 1)

    def test_failed_replace_restores_all_previous_artifacts(self):
        for fail_name in ('municipio_de_prueba_seguridad_medicion_borrador_renderizado.json',
                          'municipio_de_prueba_diagnostico_seguridad_municipal.json'):
            with self.subTest(fail_name=fail_name), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                publicar(ejemplo(), output, 'borrador')
                before = {path: path.read_bytes() for folder in ('json', 'word')
                          for path in (output / folder).iterdir()}
                replace = Path.replace

                def fail_second_or_third(source, target):
                    if source.name == fail_name and '.publicacion-' in str(source):
                        raise PermissionError('Simulated publication error')
                    return replace(source, target)

                with patch.object(Path, 'replace', fail_second_or_third):
                    with self.assertRaisesRegex(OSError, 'se restauró'):
                        publicar(ejemplo(), output, 'borrador')
                for path, content in before.items():
                    self.assertEqual(path.read_bytes(), content)
                self.assertFalse(list(output.glob('.publicacion-*')))


if __name__ == '__main__':
    unittest.main()
