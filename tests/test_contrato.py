"""Contrato 2.2: tres roles documentales y una salida narrativa reproducible."""
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

    def test_only_measurement_has_25_text_variables(self):
        self.assertEqual(self.contract['version'], '2.2')
        self.assertEqual(self.contract['producto'], 'estudio_seguridad')
        self.assertEqual(set(self.contract['plantillas']), {'medicion'})
        self.assertEqual(self.contract['documentos_salida'], ['medicion'])
        self.assertEqual(validar(), (25, 25))
        keys = set(self.dictionary['variables_documento'])
        self.assertNotIn('introduccion_seguridad', keys)
        self.assertNotIn('conclusiones_seguridad', keys)
        self.assertNotIn('tabla_calificaciones', keys)
        self.assertFalse(any(key.startswith(('tablas_', 'graficas_', 'cierre_')) for key in keys))
        self.assertTrue(all(entry['tipo_dato'] == 'string'
                            for entry in self.dictionary['variables_documento'].values()))
        self.assertEqual(self.contract['nombre_salida'], '{municipio} Estudio Seguridad.docx')

    def test_chapter_preserves_indicator_order_without_internal_blocks(self):
        entry = self.contract['plantillas']['medicion']
        original = leer_documento(ROOT / entry['origen'])
        section = migrador.extraer_capitulo(original, self.dictionary['catalogo_indicadores'])
        self.assertEqual(entry['bloques_capitulo_origen'], len(section))
        derived = list(leer_documento(ROOT / entry['archivo']).find(migrador.W + 'body'))
        start = next(i for i, node in enumerate(derived) if migrador.text(node).strip() == 'SEGURIDAD')
        end = next(i for i in range(start + 1, len(derived)) if migrador.text(derived[i]).strip() == 'Fuentes documentales')
        expected = migrador.parametrizar_capitulo(section, self.dictionary['catalogo_indicadores'])
        self.assertEqual([(node.tag, migrador.text(node)) for node in derived[start:end]],
                         [(node.tag, migrador.text(node)) for node in expected])
        headings = [migrador.text(node) for node in derived
                    if migrador.text(node) in self.contract['titulos_indicadores']]
        self.assertEqual(headings, [entry['nombre'] for entry in self.dictionary['catalogo_indicadores']])
        self.assertNotIn('Indicador 01:', ''.join(migrador.text(node) for node in derived))
        self.assertEqual(sha256(ROOT / entry['origen']), entry['origen_sha256'])

    def test_reference_roles_have_distinct_sources_and_hashes(self):
        paths = []
        for key in ('fuente_formato', 'guia', 'benchmark'):
            entry = self.contract[key]
            self.assertTrue(entry['rol'])
            self.assertEqual(entry['sha256'], sha256(ROOT / entry['archivo']))
            paths.append(entry['archivo'])
        self.assertEqual(len(set(paths)), 3)
        self.assertEqual(contrato.huellas()['benchmark_sha256'], self.contract['benchmark']['sha256'])
        self.assertEqual(contrato.huellas()['guia_sha256'], self.contract['guia']['sha256'])

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

    def test_changed_benchmark_guide_or_normalizations_rejects_stale_contract(self):
        for key in ('benchmark', 'guia', 'normalizaciones'):
            with self.subTest(component=key), tempfile.TemporaryDirectory() as directory:
                modified = deepcopy(self.contract)
                modified[key]['sha256'] = '0' * 64
                contract_path = Path(directory) / 'contrato.json'
                contract_path.write_text(json.dumps(modified), encoding='utf-8')
                with patch.object(contrato, 'CONTRACT', contract_path):
                    with self.assertRaisesRegex(ValueError, 'Cambió el contrato documental'):
                        contrato.cargar_contrato()

    def test_migration_is_deterministic_idempotent_and_preserves_inputs(self):
        entry = self.contract['plantillas']['medicion']
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            paths = [entry['origen'], *[self.contract[key]['archivo'] for key in
                     ('diccionario', 'reglas', 'metodologia', 'formato', 'redaccion', 'guia', 'benchmark', 'normalizaciones')],
                     *[font['archivo'] for font in self.contract['tipografias']]]
            for relative in paths:
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            source = temporary / entry['origen']
            rules = temporary / self.contract['reglas']['archivo']
            originals = [source, temporary / self.contract['guia']['archivo'],
                         temporary / self.contract['benchmark']['archivo'], rules]
            unchanged = [path.read_bytes() for path in originals]
            with ExitStack() as stack:
                for name, value in {
                    'ROOT': temporary,
                    'SOURCE': source,
                    'BASE': temporary / entry['archivo'],
                    'FORMATO': temporary / self.contract['formato']['archivo'],
                    'REDACCION': temporary / self.contract['redaccion']['archivo'],
                    'BENCHMARK': temporary / self.contract['benchmark']['archivo'],
                    'NORMALIZACIONES': temporary / self.contract['normalizaciones']['archivo'],
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
                self.assertEqual(unchanged, [path.read_bytes() for path in originals])
                stack.enter_context(patch.object(contrato, 'ROOT', temporary))
                stack.enter_context(patch.object(contrato, 'CONTRACT', outputs[-1]))
                self.assertEqual(set(contrato.cargar_contrato()['plantillas']), {'medicion'})


if __name__ == '__main__':
    unittest.main()
