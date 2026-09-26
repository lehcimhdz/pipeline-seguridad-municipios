"""Regresiones: un Word válido también debe conservar el machote recibido."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zipfile
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fidelidad_machote import validar, controles, retirar_resaltado_amarillo, W
from migrar_machote_v3 import validar_encabezados


class FidelidadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / 'config/contrato_documental.json').read_text())
        definition = cls.contract['plantillas']['medicion']
        with zipfile.ZipFile(ROOT / definition['origen']) as z:
            cls.original = {n: z.read(n) for n in z.namelist()}
        with zipfile.ZipFile(ROOT / definition['archivo']) as z:
            cls.base = {n: z.read(n) for n in z.namelist()}

    def mutate(self, mutation):
        files = deepcopy(self.base)
        root = ET.fromstring(files['word/document.xml'])
        mutation(root)
        files['word/document.xml'] = ET.tostring(root)
        return files

    def without_yellow(self, files=None):
        files = deepcopy(self.base if files is None else files)
        for name, data in list(files.items()):
            if name.startswith('word/') and name.endswith('.xml'):
                root = ET.fromstring(data)
                if retirar_resaltado_amarillo(root):
                    files[name] = ET.tostring(root)
        return files

    def test_preserves_source_structure_lists_and_single_section(self):
        result = validar(self.original, self.base, self.contract['fidelidad'])
        self.assertEqual(result['bloques_origen_verificados'], 101)
        root = ET.fromstring(self.base['word/document.xml'])
        source = ET.fromstring(self.original['word/document.xml'])
        self.assertEqual(len(root.findall('.//' + W + 'sectPr')), len(source.findall('.//' + W + 'sectPr')))
        self.assertEqual(len(root.findall('.//' + W + 'numPr')), len(source.findall('.//' + W + 'numPr')))
        self.assertEqual(self.base['word/numbering.xml'], self.original['word/numbering.xml'])

    def test_rejects_changed_fixed_heading(self):
        def change(root):
            controles(root)['origen_027'][0].find('.//' + W + 't').text = 'Título inventado'
        with self.assertRaisesRegex(ValueError, 'Contenido fijo'):
            validar(self.original, self.mutate(change), self.contract['fidelidad'])

    def test_rejects_reordered_source_blocks(self):
        def change(root):
            body = root.find(W + 'body')
            node = body[5]
            body.remove(node)
            body.insert(7, node)
        with self.assertRaisesRegex(ValueError, 'orden'):
            validar(self.original, self.mutate(change), self.contract['fidelidad'])

    def test_rejects_lost_numbering_in_generated_slot(self):
        def change(root):
            p = controles(root)['origen_006'][0]
            numbering = p.find(W + 'pPr/' + W + 'numPr')
            numbering.getparent().remove(numbering)
        with self.assertRaisesRegex(ValueError, 'numeración'):
            validar(self.original, self.mutate(change), self.contract['fidelidad'])

    def test_rejects_changed_page_geometry(self):
        def change(root):
            root.find('.//' + W + 'sectPr/' + W + 'pgSz').set(W + 'w', '5000')
        with self.assertRaisesRegex(ValueError, 'configuración de página'):
            validar(self.original, self.mutate(change), self.contract['fidelidad'])

    def test_rejects_unmapped_cover(self):
        def change(root):
            p = ET.Element(W + 'p')
            ET.SubElement(ET.SubElement(p, W + 'r'), W + 't').text = 'Portada ajena al machote'
            root.find(W + 'body').insert(0, p)
        with self.assertRaisesRegex(ValueError, 'fuera de las posiciones'):
            validar(self.original, self.mutate(change), self.contract['fidelidad'])

    def test_rejects_modified_original_styles_even_when_paragraphs_are_untouched(self):
        files = deepcopy(self.base)
        styles = ET.fromstring(files['word/styles.xml'])
        style = styles.find(W + 'style')
        style.set(W + 'default', '0' if style.get(W + 'default') != '0' else '1')
        files['word/styles.xml'] = ET.tostring(styles)
        with self.assertRaisesRegex(ValueError, 'estilo original'):
            validar(self.original, files, self.contract['fidelidad'], salida=True)

    def test_rejects_changed_document_defaults(self):
        files = deepcopy(self.base)
        styles = ET.fromstring(files['word/styles.xml'])
        defaults = styles.find(W + 'docDefaults')
        if defaults is None:
            defaults = ET.SubElement(styles, W + 'docDefaults')
        defaults.set('alteracion_prueba', '1')
        files['word/styles.xml'] = ET.tostring(styles)
        with self.assertRaisesRegex(ValueError, 'configuración global de estilos'):
            validar(self.original, files, self.contract['fidelidad'], salida=True)

    def test_only_output_may_add_content_json_style(self):
        files = self.without_yellow()
        styles = ET.fromstring(files['word/styles.xml'])
        added = ET.SubElement(styles, W + 'style', {W + 'styleId': 'ContenidoJSON', W + 'type': 'character'})
        files['word/styles.xml'] = ET.tostring(styles)
        self.assertTrue(validar(self.original, files, self.contract['fidelidad'], salida=True)['fidelidad_machote_verificada'])
        with self.assertRaisesRegex(ValueError, 'estilos ajenos'):
            validar(self.original, files, self.contract['fidelidad'])
        added.set(W + 'styleId', 'OtroEstilo')
        files['word/styles.xml'] = ET.tostring(styles)
        with self.assertRaisesRegex(ValueError, 'estilos ajenos'):
            validar(self.original, files, self.contract['fidelidad'], salida=True)

    def test_only_output_may_remove_original_yellow_marks(self):
        files = self.without_yellow()
        self.assertNotEqual(files['word/document.xml'], self.base['word/document.xml'])
        self.assertTrue(validar(self.original, files, self.contract['fidelidad'], salida=True)['fidelidad_machote_verificada'])
        with self.assertRaisesRegex(ValueError, 'Contenido fijo|Formato'):
            validar(self.original, files, self.contract['fidelidad'])

    def test_yellow_exception_does_not_allow_other_format_changes(self):
        for kind in ('color', 'highlight', 'shd'):
            files = self.without_yellow()
            root = ET.fromstring(files['word/document.xml'])
            props = controles(root)['origen_027'][0].find('.//' + W + 'rPr')
            if props is None:
                props = ET.SubElement(controles(root)['origen_027'][0].find('.//' + W + 'r'), W + 'rPr')
            ET.SubElement(props, W + kind, {W + ('fill' if kind == 'shd' else 'val'): 'FFFF00' if kind == 'shd' else 'yellow' if kind == 'highlight' else 'FF0000'})
            files['word/document.xml'] = ET.tostring(root)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Contenido fijo'):
                validar(self.original, files, self.contract['fidelidad'], salida=True)

    def test_output_removes_yellow_in_original_styles_but_keeps_other_shading(self):
        originals = deepcopy(self.original)
        current = deepcopy(self.base)
        for files in (originals, current):
            root = ET.fromstring(files['word/styles.xml'])
            style = root.find(W + 'style')
            props = style.find(W + 'rPr')
            if props is None:
                props = ET.SubElement(style, W + 'rPr')
            ET.SubElement(props, W + 'highlight', {W + 'val': 'yellow'})
            ET.SubElement(props, W + 'shd', {W + 'fill': 'DAE3F3'})
            files['word/styles.xml'] = ET.tostring(root)
        current = self.without_yellow(current)
        self.assertTrue(validar(originals, current, self.contract['fidelidad'], salida=True)['fidelidad_machote_verificada'])
        styles = ET.fromstring(current['word/styles.xml'])
        shade = styles.find(W + 'style/' + W + 'rPr/' + W + 'shd')
        shade.getparent().remove(shade)
        current['word/styles.xml'] = ET.tostring(styles)
        with self.assertRaisesRegex(ValueError, 'estilo original'):
            validar(originals, current, self.contract['fidelidad'], salida=True)

    def test_heading_validation_accepts_current_aliases_and_explicit_duplicate(self):
        blocks = list(ET.fromstring(self.original['word/document.xml']).find(W + 'body'))
        catalog = json.loads((ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json').read_text())['catalogo_indicadores']
        validar_encabezados(blocks, catalog)

    def test_heading_validation_rejects_swapped_indicator_names(self):
        blocks = list(ET.fromstring(self.original['word/document.xml']).find(W + 'body'))
        catalog = json.loads((ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json').read_text())['catalogo_indicadores']
        blocks[32], blocks[35] = blocks[35], blocks[32]
        with self.assertRaisesRegex(ValueError, 'Encabezado de indicador inesperado en bloque 32'):
            validar_encabezados(blocks, catalog)

    def test_duplicate_slot_cannot_silently_replace_a_new_indicator(self):
        blocks = list(ET.fromstring(self.original['word/document.xml']).find(W + 'body'))
        catalog = json.loads((ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json').read_text())['catalogo_indicadores']
        blocks[50] = deepcopy(blocks[52])
        with self.assertRaisesRegex(ValueError, 'Encabezado de indicador inesperado en bloque 50'):
            validar_encabezados(blocks, catalog)


if __name__ == '__main__':
    unittest.main()
