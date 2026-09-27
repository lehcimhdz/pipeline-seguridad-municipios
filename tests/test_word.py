"""Pruebas con datos sintéticos; no necesitan los archivos de un municipio."""
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
from calificar import agregar, definir_periodos
from componer_documento import componer
from documentos import sha256
from contrato import huellas
from renderizar_word import (DICTIONARY, RULES, TEMPLATE, W, STYLE, auditar,
                             parrafo, reemplazar, renderizar, run, texto, validar_resultado)


def ejemplo(pending=True):
    dictionary = json.loads(DICTIONARY.read_text(encoding='utf-8'))
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    sections = []
    for ficha in rules['fichas']:
        number = ficha['id']
        evaluation = {'puntaje': None if pending and number == 4 else 5,
                      'años_evaluados': [2021, 2022], 'criterio_aplicado': f'Ficha {number}, criterio 5'}
        if evaluation['puntaje'] is None:
            evaluation['motivo'] = 'Falta población comparable.'
        sections.append({'numero': number, 'nombre': ficha['nombre'],
                         'evaluaciones': {p: deepcopy(evaluation) for p in ('general', 'ultimo_periodo')},
                         'control_cruzado_anexo': {'tablas_identicas': True, 'calificacion_reportada_coincide': True},
                         'tablas': [{'tabla': number, 'ambito': 'municipal',
                                     'filas': [['Año', 'Valor'], ['2021', 'Sí & válido < 100'], ['2022', '']]}]})
        if number == 15:
            sections[-1]['tablas'].append({'tabla': 99, 'ambito': 'estatal',
                                          'filas': [['Año', 'Valor'], ['2021', '20'], ['2022', '30']]})
    values = {k: None for k in dictionary['variables_documento']}
    values.update(municipio='Municipio de prueba', estado='Entidad de prueba', año_inicial=2021, año_final=2022)
    result = {'municipio': values['municipio'], 'estado': values['estado'], 'estado_ejecucion': 'requiere_revision',
              'contrato': huellas(), 'periodos_evaluacion': definir_periodos(sections),
              'fuentes': [{'archivo': values['municipio'] + suffix, 'sha256': 'a' * 64}
                          for suffix in (' Anexo.docx', ' PAQUETE SEGURIDAD.docx')],
              'valores_plantilla': values, 'indicadores': sections,
              'calculos': {p: agregar({s['numero']: s['evaluaciones'][p] for s in sections}, rules)
                          for p in ('general', 'ultimo_periodo')},
              'validaciones': [{'nivel': 'bloqueante', 'codigo': 'COMPOSICION_WORD_PENDIENTE'},
                               {'nivel': 'bloqueante', 'codigo': 'VARIABLES_PENDIENTES'}]}
    if pending:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'INDICADOR_PENDIENTE', 'indicador': 4})
    return componer(result, dictionary, rules)


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
        for r in runs:
            self.assertIsNotNone(r.find(W + 'rPr/' + W + 'i'))
        self.assertIsNone(runs[0].find(W + 'rPr/' + W + 'highlight'))
        self.assertIsNone(runs[2].find(W + 'rPr/' + W + 'highlight'))
        self.assertIsNone(runs[1].find(W + 'rPr/' + W + 'highlight'))
        self.assertIsNone(runs[1].find(W + 'rPr/' + W + 'shd'))
        self.assertEqual(runs[1].find(W + 'rPr/' + W + 'rStyle').get(W + 'val'), STYLE)

    def test_composition_keeps_missing_scores_and_inactive_variables(self):
        result = ejemplo()
        self.assertIn('Municipio de prueba', result['valores_plantilla']['resumen_general'])
        self.assertNotIn('condicion_critica', result['valores_plantilla'])
        self.assertEqual(result['contenido_word']['variables_no_aplicables'], [])
        self.assertIsNone(result['calculos']['general']['calificacion_final'])
        codes = {v['codigo'] for v in result['validaciones']}
        self.assertNotIn('COMPOSICION_WORD_PENDIENTE', codes)
        self.assertIn('INDICADOR_PENDIENTE', codes)
        self.assertIn('REVISION_EDITORIAL_WORD', codes)

    def test_draft_roundtrip_no_highlight_hashes_and_replaces_current_output(self):
        result = ejemplo()
        before = sha256(TEMPLATE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            report = renderizar(path, Path(directory) / 'word')
            word = Path(report['archivo'])
            self.assertEqual(word.name, 'municipio_de_prueba_seguridad_medicion_borrador.docx')
            self.assertEqual(report['json_sha256'], sha256(path))
            self.assertEqual(report['sha256'], sha256(word))
            self.assertTrue(report['sin_resaltado_amarillo_verificado'])
            self.assertTrue(report['redaccion_publicable_verificada'])
            with zipfile.ZipFile(word) as archive:
                root = ET.fromstring(archive.read('word/document.xml'))
                text = texto(root)
                self.assertIn('Versión de trabajo', text)
                self.assertIn('Sí & válido < 100', text)
                self.assertIn('Alcance de la información', text)
                self.assertNotIn('JSON', text)
                self.assertNotIn('TEXTOS BASE', text)
                self.assertNotIn('{', text)
                self.assertIn('Certificado', text)
                sections = root.findall('.//' + W + 'sectPr')
                self.assertEqual(len(sections), 2)
                for r in root.iter(W + 'r'):
                    style = r.find(W + 'rPr/' + W + 'rStyle')
                    if style is not None and style.get(W + 'val') == STYLE:
                        self.assertIsNone(r.find(W + 'rPr/' + W + 'highlight'))
                        self.assertIsNone(r.find(W + 'rPr/' + W + 'shd'))
                        self.assertIn(r.find(W + 'rPr/' + W + 'rFonts').get(W + 'ascii'), ('Archivo Light', 'Archivo Medium', 'Archivo'))
            again = renderizar(path, word.parent)
            self.assertEqual(report['archivo'], again['archivo'])
            self.assertEqual(again['sha256'], sha256(word))
        self.assertEqual(before, sha256(TEMPLATE))

    def test_final_refuses_partial_data_even_if_state_is_changed(self):
        result = ejemplo()
        result['estado_ejecucion'] = 'validado'
        result['validaciones'] = []
        with self.assertRaisesRegex(ValueError, 'todos los puntajes'):
            validar_resultado(result, 'final')

    def test_final_requires_review_and_accepts_complete_validated_json(self):
        result = ejemplo(pending=False)
        result['estado_ejecucion'] = 'validado'
        with self.assertRaisesRegex(ValueError, 'revisiones pendientes'):
            validar_resultado(result, 'final')
        result['validaciones'] = []  # Simula una revisión resuelta en el JSON sintético.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            report = renderizar(path, Path(directory) / 'word', 'final')
            with zipfile.ZipFile(report['archivo']) as archive:
                text = texto(ET.fromstring(archive.read('word/document.xml')))
            self.assertNotIn('BORRADOR', text)
            self.assertNotIn('PENDIENTE', text)
            self.assertIn('CALIFICACIÓN GENERAL: EXCELENTE', text)

    def test_contract_mismatch_blocks_output(self):
        result = ejemplo()
        result['contrato']['plantilla_sha256'] = 'incorrecto'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'contrato actual'):
                renderizar(path, Path(directory) / 'word')
            self.assertFalse((Path(directory) / 'word').exists())

    def test_aggregate_and_worksheet_inconsistencies_block_output(self):
        for key in ('calculos', 'hoja'):
            result = ejemplo(pending=False)
            if key == 'calculos':
                result['calculos']['general']['calificacion_final'] = 'MAL'
            else:
                result['contenido_word']['hoja_computo'][0]['general'] = '1'
            with self.assertRaises(ValueError):
                validar_resultado(result, 'borrador')

    def test_audit_rejects_yellow_generated_text(self):
        p = parrafo('La información municipal presenta avances.')
        props = p.find(W + 'r/' + W + 'rPr')
        ET.SubElement(props, W + 'highlight', {W + 'val': 'yellow'})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.docx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('word/document.xml', ET.tostring(p))
            with self.assertRaisesRegex(ValueError, 'resaltado amarillo'):
                auditar(path)

    def test_medicion_uses_editorial_fonts_and_native_chart_relationships(self):
        result = ejemplo()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result), encoding='utf-8')
            report = renderizar(path, Path(directory) / 'word', perfil='medicion')
            with zipfile.ZipFile(report['archivo']) as archive:
                root = ET.fromstring(archive.read('word/document.xml'))
                self.assertNotIn('DESARROLLO SOCIAL', texto(root))
                self.assertNotIn('{', texto(root))
                table = root.find('.//' + W + 'tbl')
                header = table.find(W + 'tr/' + W + 'tc/' + W + 'p')
                self.assertEqual(header.find(W + 'r/' + W + 'rPr/' + W + 'rFonts').get(W + 'ascii'), 'Archivo Medium')
                self.assertEqual(header.find(W + 'r/' + W + 'rPr/' + W + 'sz').get(W + 'val'), '24')
                self.assertEqual(header.find(W + 'pPr/' + W + 'spacing').get(W + 'line'), '280')
                self.assertEqual(len([n for n in archive.namelist() if n.endswith('.odttf')]), 4)
                charts = [n for n in archive.namelist() if n.startswith('word/charts/pipeline_')]
                self.assertEqual(len(charts), 17)  # El indicador 4 está pendiente en ambos periodos.
                for name in charts:
                    graph = ET.fromstring(archive.read(name))
                    self.assertEqual(graph.find('{http://schemas.openxmlformats.org/drawingml/2006/chart}spPr/'
                                                '{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill/'
                                                '{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr').get('val'), 'FFFFFF')
                relations = ET.fromstring(archive.read('word/_rels/document.xml.rels'))
                chart_targets = [r.get('Target') for r in relations if r.get('Type', '').endswith('/chart')]
                self.assertEqual(len(chart_targets), len(charts))
                self.assertTrue(all('word/' + target in archive.namelist() for target in chart_targets))

    def test_visual_data_tampering_is_rejected(self):
        for kind in ('graph', 'table', 'summary'):
            result = json.loads(json.dumps(ejemplo()))
            if kind == 'graph':
                result['valores_plantilla']['graficas_indicador_01'][0]['valores'][0] = 1
            elif kind == 'table':
                result['valores_plantilla']['tablas_indicador_01'][0]['filas'][1][1] = 'Inventado'
            else:
                result['valores_plantilla']['calificacion_general'] = 'EXCELENTE'
            with self.assertRaises(ValueError):
                validar_resultado(result, 'borrador')

    def test_only_medicion_and_two_sources_are_accepted(self):
        result = ejemplo()
        result['fuentes'].append({'archivo': 'Otra fuente.docx'})
        with self.assertRaisesRegex(ValueError, 'exclusivamente'):
            validar_resultado(result, 'borrador')
        with self.assertRaisesRegex(ValueError, 'perfil'):
            renderizar(Path('unused.json'), Path('unused'), perfil='anexo')

    def test_recent_period_cannot_be_changed_individually(self):
        result = ejemplo()
        result['indicadores'][0]['evaluaciones']['ultimo_periodo']['años_evaluados'] = [2020, 2022]
        with self.assertRaisesRegex(ValueError, 'común'):
            validar_resultado(result, 'borrador')

    def test_recent_period_cannot_be_omitted_or_replaced_with_two_editions(self):
        for periods in (None, {'ultimo_periodo': {'años_objetivo': [2020, 2022]}}):
            result = ejemplo()
            result['periodos_evaluacion'] = periods
            with self.assertRaisesRegex(ValueError, 'dos años consecutivos'):
                validar_resultado(result, 'borrador')

    def test_state_first_tables_preserve_documentary_order(self):
        result = ejemplo()
        result['indicadores'][14]['tablas'].reverse()
        componer(result, json.loads(DICTIONARY.read_text()), json.loads(RULES.read_text()))
        self.assertEqual(result['valores_plantilla']['tablas_indicador_15'][0]['ambito'], 'estatal')
        validar_resultado(result, 'borrador')

    def test_embedded_fonts_match_official_font_bytes(self):
        from uuid import UUID
        from fuentes_word import FONTS
        with zipfile.ZipFile(TEMPLATE) as archive:
            fonts = ET.fromstring(archive.read('word/fontTable.xml'))
            for i, (family, filename, variant) in enumerate(FONTS, 1):
                f = next(n for n in fonts if n.get(W + 'name') == family)
                embed = f.find(W + variant)
                mask = UUID(embed.get(W + 'fontKey').strip('{}')).bytes[::-1]
                raw = bytearray(archive.read(f'word/fonts/archivo_{i}.odttf'))
                for j in range(32):
                    raw[j] ^= mask[j % 16]
                self.assertEqual(bytes(raw), (ROOT / 'assets/fonts' / filename).read_bytes())


if __name__ == '__main__':
    unittest.main()
