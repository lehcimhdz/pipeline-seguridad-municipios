"""Entrega editorial y reproducción fiel, con datos exclusivamente ficticios."""
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
from documentos import sha256
from renderizar_word import TEMPLATE, W, STYLE, auditar, parrafo, reemplazar, renderizar, run, texto, validar_resultado
from ilustraciones_word import seleccionar_graficas
from ejemplo_estudio import ejemplo


class WordTests(unittest.TestCase):
    def test_fragmented_marker_preserves_surrounding_style(self):
        p = ET.Element(W + 'p')
        for text in ('Antes {muni', 'cipio} después'):
            r = run(text, generated=False)
            ET.SubElement(r.find(W + 'rPr'), W + 'i')
            p.append(r)
        reemplazar(p, '{municipio}', 'A & B < C')
        self.assertEqual(texto(p), 'Antes A & B < C después')
        runs = list(p.iter(W + 'r'))
        self.assertEqual(len(runs), 3)
        self.assertTrue(all(r.find(W + 'rPr/' + W + 'i') is not None for r in runs))
        self.assertIsNone(runs[1].find(W + 'rPr/' + W + 'highlight'))
        self.assertEqual(runs[1].find(W + 'rPr/' + W + 'rStyle').get(W + 'val'), STYLE)

    def test_final_word_has_requested_name_no_tables_or_new_charts(self):
        before = sha256(TEMPLATE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = ejemplo(root)
            path = root / 'municipio.json'
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            report = renderizar(path, root / 'word')
            word = Path(report['archivo'])
            self.assertEqual(word.name, 'Municipio de prueba Estudio Seguridad.docx')
            self.assertEqual(report['json_sha256'], sha256(path))
            self.assertEqual(report['sha256'], sha256(word))
            self.assertTrue(report['sin_resaltado_amarillo_verificado'])
            with zipfile.ZipFile(word) as archive:
                document = ET.fromstring(archive.read('word/document.xml'))
                text = texto(document)
                self.assertNotIn('borrador', text.lower())
                self.assertNotIn('machote', text.lower())
                self.assertNotIn('Indicador 01:', text)
                self.assertNotIn('{', text)
                self.assertNotIn('JSON', text)
                self.assertIn('14 de los 18 indicadores', text)
                self.assertIsNone(document.find('.//' + W + 'tbl'))
                self.assertFalse(any(n.startswith('word/charts/') for n in archive.namelist()))
                self.assertEqual(len(document.findall('.//' + W + 'sectPr')), 2)
            again = renderizar(path, root / 'word')
            self.assertEqual(again['archivo'], report['archivo'])
        self.assertEqual(before, sha256(TEMPLATE))

    def test_original_images_are_copied_byte_for_byte_and_linked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = ejemplo(root, graficas=True)
            path = root / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            report = renderizar(path, root / 'word')
            self.assertEqual(report['graficas_reutilizadas'], 1)
            self.assertEqual(report['graficas_creadas'], 0)
            with zipfile.ZipFile(report['archivo']) as archive:
                image = report['ilustraciones'][0]
                source = Path(result['rutas_fuentes'][image['fuente']])
                with zipfile.ZipFile(source) as original:
                    self.assertEqual(archive.read(image['parte_salida']), original.read(image['parte_fuente']))
                rels = ET.fromstring(archive.read('word/_rels/document.xml.rels'))
                relation = next(r for r in rels if r.get('Id') == 'rIdEvidencia1')
                self.assertIn('word/' + relation.get('Target'), archive.namelist())

    def test_changed_original_image_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = ejemplo(root, graficas=True)
            source = Path(next(iter(result['rutas_fuentes'].values())))
            source.write_bytes(source.read_bytes() + b'changed source')
            path = root / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fuente'):
                renderizar(path, root / 'word')
            self.assertFalse((root / 'word').exists())

    def test_unknown_image_and_nonexistent_insertion_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(Path(directory), graficas=True)
            with self.assertRaises(ValueError):
                seleccionar_graficas(result['catalogo_ilustraciones'], [{'fuente': 'Otra.docx', 'parte': 'word/media/x.png', 'indicador': 1}])
            result['contenido_word']['ilustraciones'][0]['despues_parrafo'] = 100
            with self.assertRaisesRegex(ValueError, 'párrafo'):
                validar_resultado(result)

    def test_full_method_publishes_study_without_forging_a_joint_grade(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = ejemplo(root, modo='completo')
            self.assertIsNone(result['calculos']['general']['calificacion_final'])
            self.assertEqual(result['valores_plantilla']['calificacion_general'], 'SIN VALORACIÓN CONJUNTA')
            validar_resultado(result)
            path = root / 'municipio.json'
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            report = renderizar(path, root / 'word')
            with zipfile.ZipFile(report['archivo']) as archive:
                text = texto(ET.fromstring(archive.read('word/document.xml')))
            self.assertIn('SIN VALORACIÓN CONJUNTA', text)
            self.assertIn('La valoración conjunta requiere completar la evidencia', text)
            result['valores_plantilla']['calificacion_general'] = 'REGULAR'
            with self.assertRaisesRegex(ValueError, 'calificación publicada'):
                validar_resultado(result)

    def test_disponibles_publica_categoria_identificada_como_parcial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = ejemplo(root, modo='disponibles')
            self.assertEqual(result['calculos']['general']['estado'], 'calculado_disponibles')
            self.assertEqual(result['valores_plantilla']['calificacion_general'], 'MUY BIEN (COBERTURA PARCIAL)')
            path = root / 'municipio.json'
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            report = renderizar(path, root / 'word')
            with zipfile.ZipFile(report['archivo']) as archive:
                text = texto(ET.fromstring(archive.read('word/document.xml')))
            self.assertIn('MUY BIEN (COBERTURA PARCIAL)', text)
            self.assertIn('Los demás no se calificaron por falta de evidencia suficiente', text)
            result['valores_plantilla']['calificacion_general'] = 'MUY BIEN'
            with self.assertRaisesRegex(ValueError, 'calificación publicada'):
                validar_resultado(result)

    def test_modified_grade_or_score_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = ejemplo(Path(directory))
            for kind in ('score', 'grade'):
                result = deepcopy(base)
                if kind == 'score':
                    result['indicadores'][0]['evaluaciones']['general']['puntaje'] = 1
                else:
                    result['valores_plantilla']['calificacion_general'] = 'CATASTRÓFICO'
                with self.assertRaises(ValueError):
                    validar_resultado(result)

    def test_modified_text_is_rejected_even_when_contract_is_current(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ejemplo(Path(directory))
            result['valores_plantilla']['analisis_indicador_01'] = 'El municipio tiene 999 cámaras.'
            with self.assertRaisesRegex(ValueError, 'interpretación verificada'):
                validar_resultado(result)

    def test_contract_mismatch_blocks_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = ejemplo(root)
            result['contrato']['benchmark_sha256'] = 'incorrecto'
            path = root / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'contrato actual'):
                renderizar(path, root / 'word')
            self.assertFalse((root / 'word').exists())

    def test_audit_rejects_yellow_generated_text(self):
        p = parrafo('La información municipal presenta avances.')
        ET.SubElement(p.find(W + 'r/' + W + 'rPr'), W + 'highlight', {W + 'val': 'yellow'})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.docx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('word/document.xml', ET.tostring(p))
            with self.assertRaisesRegex(ValueError, 'resaltado amarillo'):
                auditar(path)

    def test_embedded_fonts_match_official_font_bytes(self):
        from uuid import UUID
        from fuentes_word import FONTS
        with zipfile.ZipFile(TEMPLATE) as archive:
            fonts = ET.fromstring(archive.read('word/fontTable.xml'))
            for i, (family, filename, variant) in enumerate(FONTS, 1):
                font = next(n for n in fonts if n.get(W + 'name') == family)
                embed = font.find(W + variant)
                mask = UUID(embed.get(W + 'fontKey').strip('{}')).bytes[::-1]
                raw = bytearray(archive.read(f'word/fonts/archivo_{i}.odttf'))
                for j in range(32):
                    raw[j] ^= mask[j % 16]
                self.assertEqual(bytes(raw), (ROOT / 'assets/fonts' / filename).read_bytes())


if __name__ == '__main__':
    unittest.main()
