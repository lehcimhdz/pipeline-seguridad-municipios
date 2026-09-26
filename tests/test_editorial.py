"""El manual debe cumplirse en el XML final, no sólo declararse en un JSON."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from editorial import W, configurar, rol_estilo
from auditoria_editorial import normalizar_notas, validar_editorial, validar_parrafo
from fidelidad_machote import controles, validar as validar_fidelidad
from renderizar_word import renderizar, parrafo, texto
from test_word import ejemplo


class FormatoTests(unittest.TestCase):
    def test_titles_use_approved_minimum_and_body_uses_exact_spacing(self):
        for role in ('capitulo', 'subcapitulo'):
            p = parrafo('Título', rol=role)
            spacing = p.find(W + 'pPr/' + W + 'spacing')
            self.assertEqual(spacing.get(W + 'lineRule'), 'atLeast')
            self.assertEqual(spacing.get(W + 'line'), '280')
            self.assertEqual(p.find('.//' + W + 'rFonts').get(W + 'ascii'), 'Archivo Light')
            self.assertEqual(p.find('.//' + W + 'sz').get(W + 'val'), '48')
        for initial in (True, False):
            p = parrafo('Cuerpo', inicial=initial)
            spacing = p.find(W + 'pPr/' + W + 'spacing')
            self.assertEqual(spacing.get(W + 'lineRule'), 'exact')
            self.assertEqual(spacing.get(W + 'line'), '320')
            self.assertEqual(spacing.get(W + 'before'), '0')
            self.assertEqual(spacing.get(W + 'after'), '0')
            self.assertEqual(p.find(W + 'pPr/' + W + 'ind').get(W + 'firstLine'), '0' if initial else '283')

    def test_theme_fonts_cannot_override_archivo_and_italics_only_in_bibliography(self):
        p = parrafo('Texto', generated=False)
        rpr = p.find(W + 'r/' + W + 'rPr')
        rpr.find(W + 'rFonts').set(W + 'asciiTheme', 'minorHAnsi')
        rpr.find(W + 'i').set(W + 'val', '1')
        configurar(p, rol='bibliografia')
        self.assertEqual(rpr.find(W + 'i').get(W + 'val'), '1')
        self.assertIsNone(rpr.find(W + 'rFonts').get(W + 'asciiTheme'))
        configurar(p, rol='cuerpo')
        self.assertEqual(rpr.find(W + 'i').get(W + 'val'), '0')

    def test_preserves_numbering_and_color_but_normalizes_indent(self):
        p = parrafo('Elemento')
        props = p.find(W + 'pPr')
        numbering = ET.SubElement(props, W + 'numPr')
        ET.SubElement(numbering, W + 'numId', {W + 'val': '7'})
        ET.SubElement(p.find(W + 'r/' + W + 'rPr'), W + 'color', {W + 'val': '1F4E78'})
        configurar(p)
        self.assertEqual(p.find(W + 'pPr/' + W + 'numPr/' + W + 'numId').get(W + 'val'), '7')
        self.assertEqual(p.find(W + 'pPr/' + W + 'ind').get(W + 'hanging'), '283')
        self.assertEqual(p.find(W + 'r/' + W + 'rPr/' + W + 'color').get(W + 'val'), '1F4E78')
        validar_parrafo(p)

    def test_normalizes_real_notes_without_creating_notes_or_changing_separators(self):
        root = ET.Element(W + 'footnotes')
        separator = ET.SubElement(root, W + 'footnote', {W + 'id': '-1', W + 'type': 'separator'})
        separator.append(ET.Element(W + 'p'))
        note = ET.SubElement(root, W + 'footnote', {W + 'id': '1'})
        note.append(parrafo('Nota existente'))
        before = ET.tostring(separator)
        files = {'word/footnotes.xml': ET.tostring(root)}
        normalizar_notas(files)
        result = ET.fromstring(files['word/footnotes.xml'])
        self.assertEqual(len(result), 2)
        self.assertEqual(ET.tostring(result[0]), before)
        validar_parrafo(result[1][0], 'nota')
        self.assertEqual(result[1][0].find(W + 'pPr/' + W + 'spacing').get(W + 'line'), '220')


class SalidaEditorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / 'config/contrato_documental.json').read_text())
        cls.manifest = cls.contract['fidelidad']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prueba.json'
            path.write_text(json.dumps(ejemplo()), encoding='utf-8')
            cls.report = renderizar(path, Path(directory) / 'word')
            with zipfile.ZipFile(cls.report['archivo']) as z:
                cls.files = {n: z.read(n) for n in z.namelist()}
        with zipfile.ZipFile(ROOT / cls.contract['plantillas']['medicion']['origen']) as z:
            cls.original = {n: z.read(n) for n in z.namelist()}

    def mutate(self, callback):
        files = dict(self.files)
        root = ET.fromstring(files['word/document.xml'])
        callback(root)
        files['word/document.xml'] = ET.tostring(root)
        return files

    def test_output_is_faithful_with_explicit_editorial_exceptions(self):
        self.assertTrue(validar_fidelidad(self.original, self.files, self.manifest, salida=True)['fidelidad_machote_verificada'])
        report = validar_editorial(self.files, self.manifest)
        self.assertTrue(report['formato_editorial_verificado'])
        self.assertEqual(report['graficas_editoriales_verificadas'], 18)
        self.assertEqual(report['notas_al_pie_o_finales'], 0)
        root = ET.fromstring(self.files['word/document.xml'])
        self.assertEqual(len(root.findall('.//' + W + 'numPr')), 35)
        self.assertEqual(list(controles(root))[0], 'adicional_portada')

    def test_rejects_fixed_heading_text_change_even_with_valid_format(self):
        def change(root):
            controles(root)['origen_027'][0].find('.//' + W + 't').text = 'Título ajeno'
        files = self.mutate(change)
        with self.assertRaisesRegex(ValueError, 'Contenido fijo'):
            validar_fidelidad(self.original, files, self.manifest, salida=True)

    def test_rejects_font_spacing_indent_alignment_and_size_regressions(self):
        for property_name, attribute, value in (
            ('rFonts', 'ascii', 'Calibri'), ('sz', 'val', '18'),
            ('spacing', 'lineRule', 'auto'), ('spacing', 'before', '320'),
            ('ind', 'firstLine', '283'), ('jc', 'val', 'left'),
        ):
            def change(root):
                p = controles(root)['origen_005'][0]
                p.find('.//' + W + property_name).set(W + attribute, value)
            with self.subTest(property=property_name), self.assertRaisesRegex(ValueError, 'Formato editorial'):
                validar_editorial(self.mutate(change), self.manifest)

    def test_rejects_wrong_semantic_roles_on_fixed_heading_and_table_headers(self):
        for target in ('heading', 'table'):
            def change(root):
                p = controles(root)['origen_027'][0] if target == 'heading' else root.find('.//' + W + 'tbl/' + W + 'tr/' + W + 'tc/' + W + 'p')
                configurar(p, rol='cuerpo')
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'Rol editorial incorrecto'):
                validar_editorial(self.mutate(change), self.manifest)

    def test_continuation_paragraphs_have_five_mm_indent(self):
        root = ET.fromstring(self.files['word/document.xml'])
        paragraphs = [p for p in root.iter(W + 'p') if rol_estilo(p) == ('cuerpo', False)]
        self.assertTrue(paragraphs)
        for p in paragraphs:
            self.assertEqual(p.find(W + 'pPr/' + W + 'ind').get(W + 'firstLine'), '283')

    def test_original_spacers_are_preserved_but_hidden(self):
        root = ET.fromstring(self.files['word/document.xml'])
        p = controles(root)['origen_004'][0]
        self.assertEqual(texto(p), '')
        self.assertEqual(rol_estilo(p), ('separador', True))
        self.assertEqual(p.find(W + 'pPr/' + W + 'rPr/' + W + 'vanish').get(W + 'val'), '1')

    def test_rejects_missing_or_disconnected_charts(self):
        files = dict(self.files)
        del files['word/charts/pipeline_1.xml']
        with self.assertRaisesRegex(ValueError, 'Faltan gráficas'):
            validar_editorial(files, self.manifest)
        def disconnect(root):
            c = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
            r = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
            root.find('.//' + c + 'chart').set(r + 'id', 'rIdAusente')
        with self.assertRaisesRegex(ValueError, 'relación interna'):
            validar_editorial(self.mutate(disconnect), self.manifest)


if __name__ == '__main__':
    unittest.main()
