"""Contrato 2.1: procedencia del machote y una salida reproducible."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import contrato
import fuentes_word
import migrar_machotes_v2 as migrador
from documentos import sha256
from validar_plantilla import validar


def leer_documento(path):
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read('word/document.xml'))


class ContratoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = contrato.cargar_contrato()
        cls.dictionary = json.loads((ROOT / cls.contract['diccionario']['archivo']).read_text(encoding='utf-8'))

    def test_only_measurement_has_81_registered_variables(self):
        self.assertEqual(self.contract['version'], '2.1')
        self.assertEqual(set(self.contract['plantillas']), {'medicion'})
        self.assertEqual(self.contract['documentos_salida'], ['medicion'])
        self.assertEqual(validar(), (81, 81))
        keys = set(self.dictionary['variables_documento'])
        self.assertIn('introduccion_seguridad', keys)
        self.assertIn('conclusiones_seguridad', keys)
        self.assertNotIn('tabla_calificaciones', keys)
        self.assertFalse(any(key.startswith(('tablas_municipales_', 'tablas_estatales_')) for key in keys))

    def test_original_chapter_blocks_keep_order_and_contents(self):
        entry = self.contract['plantillas']['medicion']
        original = leer_documento(ROOT / entry['origen'])
        section = migrador.extraer_capitulo(original, self.dictionary['catalogo_indicadores'])
        self.assertEqual(len(section), 95)
        self.assertEqual(entry['bloques_capitulo_origen'], len(section))
        derived = list(leer_documento(ROOT / entry['archivo']).find(migrador.W + 'body'))
        start = next(i for i, node in enumerate(derived) if migrador.text(node).strip() == 'SEGURIDAD')
        end = next(i for i in range(start + 1, len(derived)) if migrador.text(derived[i]).strip() == 'Conclusiones')
        copied = [node for node in derived[start:end] if migrador.text(node) != '{introduccion_seguridad}']
        self.assertEqual([(node.tag, migrador.text(node)) for node in copied],
                         [(node.tag, migrador.text(node)) for node in section])
        self.assertEqual(sha256(ROOT / entry['origen']), entry['origen_sha256'])

    def test_changed_original_rejects_stale_operational_base(self):
        entry = self.contract['plantillas']['medicion']
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / entry['origen']
            source.parent.mkdir(parents=True)
            source.write_bytes((ROOT / entry['origen']).read_bytes() + b'changed original')
            contract_path = temporary / 'contrato.json'
            contract_path.write_text(json.dumps(self.contract), encoding='utf-8')
            with patch.object(contrato, 'ROOT', temporary), patch.object(contrato, 'CONTRACT', contract_path):
                with self.assertRaisesRegex(ValueError, 'Cambió el machote original'):
                    contrato.cargar_contrato()

    def test_contract_rejects_removed_output_profile(self):
        modified = deepcopy(self.contract)
        modified['plantillas']['anexo'] = deepcopy(modified['plantillas']['medicion'])
        with tempfile.TemporaryDirectory() as directory:
            contract_path = Path(directory) / 'contrato.json'
            contract_path.write_text(json.dumps(modified), encoding='utf-8')
            with patch.object(contrato, 'CONTRACT', contract_path):
                with self.assertRaisesRegex(ValueError, 'único documento'):
                    contrato.cargar_contrato()

    def test_changed_writing_profile_rejects_stale_contract(self):
        modified = deepcopy(self.contract)
        modified['redaccion']['sha256'] = '0' * 64
        with tempfile.TemporaryDirectory() as directory:
            contract_path = Path(directory) / 'contrato.json'
            contract_path.write_text(json.dumps(modified), encoding='utf-8')
            with patch.object(contrato, 'CONTRACT', contract_path):
                with self.assertRaisesRegex(ValueError, 'redaccion_consultoria'):
                    contrato.cargar_contrato()

    def test_migration_is_deterministic_idempotent_and_preserves_inputs(self):
        entry = self.contract['plantillas']['medicion']
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            paths = [entry['origen'], *[self.contract[key]['archivo'] for key in
                     ('diccionario', 'reglas', 'metodologia', 'formato', 'redaccion')],
                     *[font['archivo'] for font in self.contract['tipografias']]]
            for relative in paths:
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            source = temporary / entry['origen']
            rules = temporary / self.contract['reglas']['archivo']
            unchanged = (source.read_bytes(), rules.read_bytes())
            with ExitStack() as stack:
                for name, value in {
                    'ROOT': temporary,
                    'SOURCE': source,
                    'BASE': temporary / entry['archivo'],
                    'FORMATO': temporary / self.contract['formato']['archivo'],
                    'REDACCION': temporary / self.contract['redaccion']['archivo'],
                }.items():
                    stack.enter_context(patch.object(migrador, name, value))
                stack.enter_context(patch.object(fuentes_word, 'ROOT', temporary))
                stack.enter_context(redirect_stdout(io.StringIO()))
                migrador.main()
                outputs = [temporary / relative for relative in
                           (entry['archivo'], self.contract['diccionario']['archivo'], 'config/contrato_documental.json')]
                first = [path.read_bytes() for path in outputs]
                migrador.main()
                self.assertEqual(first, [path.read_bytes() for path in outputs])
                self.assertEqual(unchanged, (source.read_bytes(), rules.read_bytes()))
                stack.enter_context(patch.object(contrato, 'ROOT', temporary))
                stack.enter_context(patch.object(contrato, 'CONTRACT', outputs[-1]))
                self.assertEqual(set(contrato.cargar_contrato()['plantillas']), {'medicion'})


if __name__ == '__main__':
    unittest.main()
