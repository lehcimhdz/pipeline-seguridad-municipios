"""Portada y gráficas nativas: propiedades efectivas del manual editorial."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from editorial import configurar, normalizar_seccion
from graficas_word import agregar_grafica, validar_graficas, C
from logo_editorial import (A, CT, LOGO, LOGO_HEIGHT, LOGO_WIDTH, PIC, R, REL,
                            W, WP, construir_portada, validar_portada)


def paquete():
    return {
        'word/_rels/document.xml.rels': ET.tostring(ET.Element(REL + 'Relationships')),
        '[Content_Types].xml': ET.tostring(ET.Element(CT + 'Types')),
    }


def documento_portada():
    files = paquete()
    section = ET.Element(W + 'sectPr')
    ET.SubElement(section, W + 'type', {W + 'val': 'continuous'})
    ET.SubElement(section, W + 'pgSz', {W + 'w': '12240', W + 'h': '15840'})
    ET.SubElement(section, W + 'pgMar', {W + 'top': '1418', W + 'bottom': '1418',
                                       W + 'left': '1701', W + 'right': '1701'})
    ET.SubElement(section, W + 'cols', {W + 'space': '708'})
    ET.SubElement(section, W + 'docGrid', {W + 'linePitch': '360'})
    root = ET.Element(W + 'document', nsmap={'w': W[1:-1], 'a': A[1:-1], 'wp': WP[1:-1]})
    body = ET.SubElement(root, W + 'body')
    body.append(construir_portada(files, 'Municipio de prueba', 'Estado de prueba', section))
    ET.SubElement(body, W + 'p')
    body.append(normalizar_seccion(deepcopy(section)))
    return files, root


class PortadaTests(unittest.TestCase):
    def test_portada_y_logotipo_cumplen_manual(self):
        files, root = documento_portada()
        result = validar_portada(files, root)
        self.assertTrue(result['portada_editorial_verificada'])
        self.assertTrue(result['logotipo_editorial_verificado'])
        self.assertEqual(result['logotipo_ancho_cm'], 5)
        self.assertEqual(files['word/media/institutionworks.jpeg'], LOGO.read_bytes())
        self.assertEqual(LOGO_HEIGHT, round(LOGO_WIDTH * 332 / 407))
        self.assertEqual(len(root.findall('.//' + W + 'sectPr')), 2)
        self.assertFalse(any('footer' in name for name in files))
        for p in root.find(W + 'body')[0].find(W + 'sdtContent'):
            props = p.find(W + 'pPr')
            self.assertEqual(props.find(W + 'spacing').get(W + 'line'), '800')
            self.assertEqual(props.find(W + 'spacing').get(W + 'lineRule'), 'exact')
            self.assertEqual(props.find(W + 'jc').get(W + 'val'), 'center')
            frame = props.find(W + 'framePr')
            self.assertEqual(frame.get(W + 'hRule'), 'auto')
            self.assertEqual(frame.get(W + 'w'), '8838')
            for axis in ('xAlign', 'yAlign'):
                self.assertEqual(frame.get(W + axis), 'center')
            for axis in ('hAnchor', 'vAnchor'):
                self.assertEqual(frame.get(W + axis), 'page')
            for run in p.iter(W + 'r'):
                self.assertEqual(run.find(W + 'rPr/' + W + 'sz').get(W + 'val'), '52')
                self.assertEqual(run.find(W + 'rPr/' + W + 'rFonts').get(W + 'ascii'), 'Archivo')

    def test_portada_sobrevive_serializacion(self):
        files, root = documento_portada()
        validar_portada(files, ET.fromstring(ET.tostring(root)))

    def test_rechaza_alteraciones_en_tipografia_y_geometria(self):
        mutations = [
            ('.//' + W + 'rPr/' + W + 'rFonts', W + 'ascii', 'Calibri'),
            ('.//' + W + 'rPr/' + W + 'sz', W + 'val', '60'),
            ('.//' + W + 'spacing', W + 'lineRule', 'auto'),
            ('.//' + W + 'jc', W + 'val', 'left'),
            ('.//' + W + 'framePr', W + 'yAlign', 'top'),
            ('.//' + W + 'framePr', W + 'w', '7000'),
            ('.//' + W + 'framePr', W + 'hRule', 'exact'),
            ('.//' + WP + 'extent', 'cx', '2000000'),
            ('.//' + PIC + 'spPr/' + A + 'xfrm/' + A + 'ext', 'cy', '1000000'),
            ('.//' + WP + 'positionV', 'relativeFrom', 'paragraph'),
            ('.//' + W + 'vAlign', W + 'val', 'top'),
            ('.//' + W + 'type', W + 'val', 'continuous'),
            ('.//' + W + 'cols', W + 'num', '2'),
            ('.//' + A + 'blip', R + 'embed', 'rIdFalso'),
        ]
        for path, key, value in mutations:
            with self.subTest(path=path, key=key):
                files, root = documento_portada()
                root.find(path).set(key, value)
                with self.assertRaises(ValueError):
                    validar_portada(files, root)

    def test_rechaza_logotipo_alterado(self):
        files, root = documento_portada()
        files['word/media/institutionworks.jpeg'] = b'imagen distinta'
        with self.assertRaisesRegex(ValueError, 'recurso institucional'):
            validar_portada(files, root)

    def test_rechaza_cuerpo_centrado_verticalmente(self):
        files, root = documento_portada()
        root.find(W + 'body/' + W + 'sectPr/' + W + 'vAlign').set(W + 'val', 'center')
        with self.assertRaises(ValueError):
            validar_portada(files, root)

    def test_rechaza_portada_ausente_o_duplicada(self):
        for duplicate in (True, False):
            files, root = documento_portada()
            body = root.find(W + 'body')
            body.insert(1, deepcopy(body[0])) if duplicate else body.remove(body[0])
            with self.assertRaises(ValueError):
                validar_portada(files, root)

    def test_portada_no_modifica_seccion_original(self):
        section = ET.Element(W + 'sectPr')
        ET.SubElement(section, W + 'pgSz', {W + 'w': '12240', W + 'h': '15840'})
        ET.SubElement(section, W + 'pgMar', {W + 'bottom': '1418'})
        before = ET.tostring(section)
        construir_portada(paquete(), 'Municipio', 'Estado', section)
        self.assertEqual(ET.tostring(section), before)

    def test_recurso_logo_no_duplica_relacion(self):
        files, root = documento_portada()
        section = root.find(W + 'body/' + W + 'sectPr')
        construir_portada(files, 'Municipio', 'Estado', section)
        rels = ET.fromstring(files['word/_rels/document.xml.rels'])
        self.assertEqual(len(rels), 1)

    def test_rechaza_identidad_ausente_o_no_textual(self):
        files, root = documento_portada()
        section = root.find(W + 'body/' + W + 'sectPr')
        for municipality, state in ((None, 'Estado'), ('Municipio', None), ('', 'Estado'),
                                    ('Municipio', '  '), (123, 'Estado')):
            with self.subTest(municipality=municipality, state=state), self.assertRaises(ValueError):
                construir_portada(files, municipality, state, section)

    def test_rechaza_identidad_distinta_del_cuerpo(self):
        files, root = documento_portada()
        body = root.find(W + 'body')
        control = ET.Element(W + 'sdt')
        ET.SubElement(ET.SubElement(control, W + 'sdtPr'), W + 'tag', {W + 'val': 'origen_000'})
        content = ET.SubElement(control, W + 'sdtContent')
        paragraph = ET.SubElement(content, W + 'p')
        text = ET.SubElement(ET.SubElement(paragraph, W + 'r'), W + 't')
        text.text = 'Municipio de prueba, Estado de prueba'
        configurar(paragraph, rol='identidad')
        body.insert(1, control)
        validar_portada(files, root)
        text.text = 'Municipio distinto, Estado de prueba'
        with self.assertRaisesRegex(ValueError, 'identidad municipal'):
            validar_portada(files, root)

    def test_rechaza_geometria_diferente_en_portada_y_cuerpo(self):
        for tag, key in (('pgSz', 'w'), ('pgMar', 'left')):
            with self.subTest(tag=tag):
                files, root = documento_portada()
                root.find(W + 'body/' + W + 'sectPr/' + W + tag).set(W + key, '1234')
                with self.assertRaisesRegex(ValueError, 'dimensiones y márgenes'):
                    validar_portada(files, root)

    def test_rechaza_portada_sin_marco_de_centrado_compatible(self):
        files, root = documento_portada()
        frame = root.find('.//' + W + 'framePr')
        frame.getparent().remove(frame)
        with self.assertRaisesRegex(ValueError, 'marco de altura automática'):
            validar_portada(files, root)


class GraficasEditorialesTests(unittest.TestCase):
    def grafica(self):
        files = paquete()
        agregar_grafica(files, {'titulo': 'Calificación de prueba',
                               'categorias': ['Primero', 'Segundo'], 'valores': [3, 4]}, 1)
        return files

    def test_grafica_cumple_fuentes_y_espaciado_manual(self):
        result = validar_graficas(self.grafica())
        self.assertEqual(result['graficas_editoriales_verificadas'], 1)
        self.assertTrue(result['formato_graficas_verificado'])

    def test_rechaza_fuente_tamano_espaciado_o_resaltado_incorrecto(self):
        mutations = [
            ('.//' + A + 'latin', 'typeface', 'Calibri'),
            ('.//' + A + 'defRPr', 'sz', '900'),
            ('.//' + A + 'defRPr', 'b', '1'),
            ('.//' + A + 'lnSpc/' + A + 'spcPts', 'val', '1600'),
        ]
        for path, key, value in mutations:
            with self.subTest(path=path):
                files = self.grafica()
                root = ET.fromstring(files['word/charts/pipeline_1.xml'])
                root.find(path).set(key, value)
                files['word/charts/pipeline_1.xml'] = ET.tostring(root)
                with self.assertRaises(ValueError):
                    validar_graficas(files)
        files = self.grafica()
        root = ET.fromstring(files['word/charts/pipeline_1.xml'])
        ET.SubElement(root.find('.//' + A + 'defRPr'), A + 'highlight')
        files['word/charts/pipeline_1.xml'] = ET.tostring(root)
        with self.assertRaisesRegex(ValueError, 'resaltado'):
            validar_graficas(files)

    def test_rechaza_grafica_sin_interlineado(self):
        files = self.grafica()
        root = ET.fromstring(files['word/charts/pipeline_1.xml'])
        spacing = root.find('.//' + C + 'valAx/' + C + 'txPr/' + A + 'p/' + A + 'pPr/' + A + 'lnSpc')
        spacing.getparent().remove(spacing)
        files['word/charts/pipeline_1.xml'] = ET.tostring(root)
        with self.assertRaisesRegex(ValueError, 'interlineado'):
            validar_graficas(files)


if __name__ == '__main__':
    unittest.main()
