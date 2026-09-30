"""La segunda salida conserva los marcadores y el formato de su base Word."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from plataforma_electoral import cargar, renderizar, sha256


class PlataformaElectoralTests(unittest.TestCase):
    def test_citas_declaradas_y_bibliografia_seleccionada(self):
        spec = json.loads((ROOT / 'config/variables_plataforma_electoral_seguridad.json').read_text())
        catalog = json.loads((ROOT / spec['referencias']['catalogo']).read_text())['fuentes']
        fields = {key: {'texto': 'Propuesta municipal revisada.',
                        'indicadores': [1 if key.startswith('proteccion_civil_') else 5]}
                  for key in spec['variables']}
        for key, ids in (
            ('proteccion_civil_razonamiento_justificatorio', ['ley_proteccion_civil', 'marco_sendai']),
            ('seguridad_razonamiento_justificatorio', ['ley_seguridad_publica', 'braga_focalizacion'])):
            fields[key]['referencias'] = ids
            fields[key]['texto'] += ' ' + ' '.join(catalog[ref]['cita'] for ref in ids)
        result = {'municipio': 'Municipio de prueba', 'estado': 'Estado de prueba',
                  'fuentes': [], 'evaluacion_sha256': 'a' * 64}
        artifact = {'municipio': result['municipio'], 'estado': result['estado'],
                    'revision': {'estado': 'revisada'}, 'vinculos': {
                        'fuentes': [], 'evaluacion_sha256': result['evaluacion_sha256']},
                    'campos': fields}
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'redaccion.json'
            path.write_text(json.dumps(artifact), encoding='utf-8')
            content = cargar(result, path)
            self.assertIn('Braga, A. A.', content['valores_plantilla']['fuentes_clave'])
            self.assertNotIn('Piza, E. L.', content['valores_plantilla']['fuentes_clave'])
            fields['seguridad_razonamiento_justificatorio']['texto'] = 'Propuesta sin citas.'
            path.write_text(json.dumps(artifact), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Falta la cita'):
                cargar(result, path)

    def test_renderiza_solo_seguridad_y_resuelve_todas_las_variables(self):
        spec = json.loads((ROOT / 'config/variables_plataforma_electoral_seguridad.json').read_text())
        template = ROOT / spec['plantilla']
        values = {key: 'Propuesta municipal revisada.' for key in spec['variables']}
        values.update(municipio='Municipio de prueba', estado='Estado de prueba',
                      fuentes_clave='Referencia de prueba.\nOtra referencia de prueba.')
        content = {'valores_plantilla': values, 'plantilla_sha256': sha256(template),
                   'redaccion_sha256': 'a' * 64, 'evaluacion_sha256': 'b' * 64,
                   'referencias_formateadas': [
                       {'texto': 'Referencia de prueba.', 'titulo_cursiva': 'Referencia'},
                       {'texto': 'Otra referencia de prueba.', 'titulo_cursiva': 'referencia'}]}
        with TemporaryDirectory() as directory:
            destination = Path(directory) / 'plataforma.docx'
            receipt = renderizar(content, destination)
            document = Document(destination)
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            body = '\n'.join(paragraphs)
            self.assertIn('Protección Civil', body)
            self.assertIn('Seguridad', body)
            self.assertIn('Municipio de prueba', body)
            self.assertNotIn('{', body)
            self.assertEqual(receipt['variables'], len(values))
            self.assertEqual(receipt['sha256'], sha256(destination))
            self.assertEqual(document.paragraphs[0].runs[0].font.name, 'Archivo')
            self.assertEqual(document.paragraphs[0].runs[0].font.size.pt, 26)
            self.assertFalse(document.paragraphs[0].runs[0].bold)
            chapter = document.paragraphs[2]
            self.assertTrue(chapter.paragraph_format.page_break_before)
            self.assertEqual(chapter.runs[0].font.size.pt, 24)
            self.assertFalse(chapter.runs[0].bold)
            self.assertEqual(chapter.paragraph_format.line_spacing_rule, WD_LINE_SPACING.AT_LEAST)
            self.assertEqual(document.paragraphs[3].runs[0].font.name, 'Archivo Light')
            self.assertEqual(document.paragraphs[3].runs[0].font.size.pt, 12)
            self.assertAlmostEqual(document.paragraphs[6].paragraph_format.first_line_indent.mm, 5, places=1)
            self.assertTrue(document.sections[0].different_first_page_header_footer)
            extent = document.sections[0].first_page_footer._element.xpath('.//wp:extent')[0]
            self.assertEqual(int(extent.get('cx')), 1800000)
            self.assertTrue(any(run.italic for run in document.paragraphs[-2].runs))
            self.assertTrue(any(run.italic for run in document.paragraphs[-1].runs))
            self.assertEqual(document.paragraphs[-1].alignment, WD_ALIGN_PARAGRAPH.LEFT)
            self.assertAlmostEqual(document.paragraphs[-1].paragraph_format.first_line_indent.mm, 5, places=1)
            with ZipFile(destination) as archive:
                self.assertEqual(len([name for name in archive.namelist() if name.endswith('.odttf')]), 4)
                self.assertEqual(len([name for name in archive.namelist() if name.startswith('word/media/')]), 1)


if __name__ == '__main__':
    unittest.main()
