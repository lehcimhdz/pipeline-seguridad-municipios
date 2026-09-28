"""Integridad y límites del contexto obtenido de las gráficas, con fuentes ficticias."""
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lectura_graficas as lector


ENVIRONMENT = ('disponible', '/local/tesseract', 'tesseract 5.test', 'spa', '')
TEXT = ('Porcentaje\n\n90\n70\nVilla Ejemplo: Porcentaje de elementos que aprobó\n'
        'las evaluaciones de control de confianza, (2022-2024)\n2022 2023 2024')


class LecturaGraficasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'Municipio PAQUETE SEGURIDAD.docx'
        self.raw = b'imagen ficticia; el OCR se sustituye por un doble de prueba'
        with zipfile.ZipFile(self.source, 'w') as archive:
            archive.writestr('word/media/image1.png', self.raw)
            archive.writestr('word/media/image2.png', self.raw)
        self.spec = {'fuente': self.source.name,
                     'fuente_sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(),
                     'parte': 'word/media/image1.png',
                     'sha256': hashlib.sha256(self.raw).hexdigest(),
                     'indicador': 5, 'ambito': 'municipal', 'bloque': 12, 'relacion': 'rId1'}
        self.routes = {self.source.name: self.source}
        lector._ocr.cache_clear()

    def test_titulo_separa_ejes_y_une_lineas_hasta_el_periodo(self):
        self.assertEqual(lector.extraer_titulo(TEXT),
                         'Villa Ejemplo: Porcentaje de elementos que aprobó las evaluaciones '
                         'de control de confianza, (2022-2024)')
        self.assertEqual(lector.extraer_titulo('Municipio: Cámaras en funcionamiento (2022-\n2024)'),
                         'Municipio: Cámaras en funcionamiento (2022- 2024)')
        self.assertEqual(lector.extraer_titulo('Municipio: Cámaras en funcionamiento (2022–2024)'),
                         'Municipio: Cámaras en funcionamiento (2022–2024)')

    def test_no_inventa_titulo_a_partir_de_ejes_o_fuentes(self):
        for text in ['Porcentaje\n2022 2024\n90 50', 'Fuente: Censo (2022-2024)',
                     'Municipio: Cámaras\n2022\n2024\n12\n14']:
            self.assertEqual(lector.extraer_titulo(text), '')

    @patch.object(lector, '_entorno_tesseract', return_value=ENVIRONMENT)
    @patch.object(lector, '_ocr', return_value=TEXT)
    def test_deduplica_imagenes_sin_perder_procedencia_ni_mutar_catalogo(self, ocr, environment):
        duplicate = {**self.spec, 'parte': 'word/media/image2.png', 'relacion': 'rId2'}
        catalogue = [self.spec, duplicate]
        original = deepcopy(catalogue)
        result = lector.leer_graficas(catalogue, self.routes)
        self.assertEqual(ocr.call_count, 1)
        self.assertEqual([x['parte'] for x in result], [x['parte'] for x in catalogue])
        self.assertEqual(result[0]['lectura']['estado'], 'leida')
        self.assertEqual(result[0]['lectura']['texto'], TEXT)
        result[0]['lectura']['texto'] = 'alterado'
        self.assertEqual(result[1]['lectura']['texto'], TEXT)
        self.assertEqual(catalogue, original)

    @patch.object(lector, '_entorno_tesseract', return_value=ENVIRONMENT)
    @patch.object(lector, '_ocr', return_value=TEXT)
    def test_rechaza_huellas_fuente_e_imagen_modificadas(self, ocr, environment):
        for field in ('fuente_sha256', 'sha256'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                lector.leer_graficas([{**self.spec, field: '0' * 64}], self.routes)
        ocr.assert_not_called()

    @patch.object(lector, '_entorno_tesseract', return_value=ENVIRONMENT)
    @patch.object(lector, '_ocr', return_value=TEXT)
    def test_validacion_detecta_titulo_anios_y_contexto_adulterados(self, ocr, environment):
        actual = lector.leer_graficas([self.spec], self.routes)
        self.assertEqual(lector.validar_lecturas(actual, [self.spec], self.routes), actual)
        for field, value in [('titulo', 'Municipio: Cámaras (2022-2024)'),
                             ('texto', TEXT.replace('2024', '2025'))]:
            changed = deepcopy(actual)
            changed[0]['lectura'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                lector.validar_lecturas(changed, [self.spec], self.routes)
        changed = deepcopy(actual)
        changed[0]['indicador'] = 14
        with self.assertRaises(ValueError):
            lector.validar_lecturas(changed, [self.spec], self.routes)

    @patch.object(lector, '_entorno_tesseract', return_value=(
        'no_disponible', '', 'tesseract', '', 'Tesseract no está instalado.'))
    @patch.object(lector, '_ocr')
    def test_ocr_ausente_no_es_ausencia_de_datos(self, ocr, environment):
        record = lector.leer_graficas([self.spec], self.routes)[0]['lectura']
        self.assertEqual(record['estado'], 'no_disponible')
        self.assertEqual(record['texto'], '')
        self.assertIn('no está instalado', record['diagnostico'])
        ocr.assert_not_called()

    @patch.object(lector, '_entorno_tesseract', return_value=ENVIRONMENT)
    @patch.object(lector, '_ocr', side_effect=subprocess.TimeoutExpired('tesseract', 25))
    def test_timeout_no_se_confunde_con_imagen_sin_texto(self, ocr, environment):
        record = lector.leer_graficas([self.spec], self.routes)[0]['lectura']
        self.assertEqual(record['estado'], 'error')
        self.assertIn('TimeoutExpired', record['diagnostico'])

    @patch.object(lector, '_entorno_tesseract', return_value=ENVIRONMENT)
    @patch.object(lector, '_ocr', return_value='')
    def test_imagen_legible_sin_texto_tiene_estado_propio(self, ocr, environment):
        self.assertEqual(lector.leer_graficas([self.spec], self.routes)[0]['lectura']['estado'], 'sin_texto')

    @patch.object(lector.subprocess, 'run')
    def test_cache_reutiliza_ocr_pero_cambia_por_version_e_idioma(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout=TEXT.encode(), stderr=b'')
        for _ in range(2):
            self.assertEqual(lector._ocr(self.raw, '/local/tesseract', '5.1', 'spa'), TEXT)
        self.assertEqual(run.call_count, 1)
        lector._ocr(self.raw, '/local/tesseract', '5.2', 'spa')
        lector._ocr(self.raw, '/local/tesseract', '5.2', 'eng')
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args.kwargs['input'], self.raw)
        self.assertNotIn('shell', run.call_args.kwargs)
        self.assertEqual(run.call_args.args[0][1:3], ['stdin', 'stdout'])

    @patch.object(lector.shutil, 'which', return_value='/local/tesseract')
    @patch.object(lector.subprocess, 'run')
    def test_idioma_prefiere_espanol_y_recurre_a_ingles(self, run, which):
        for languages, expected in [('spa\neng', 'spa'), ('eng', 'eng'), ('fra', '')]:
            run.side_effect = [subprocess.CompletedProcess([], 0, stdout='tesseract 5.1\n', stderr=''),
                               subprocess.CompletedProcess([], 0, stdout=languages, stderr='')]
            env = lector._entorno_tesseract()
            self.assertEqual(env[3], expected)
            self.assertEqual(env[0], 'disponible' if expected else 'no_disponible')


if __name__ == '__main__':
    unittest.main()
