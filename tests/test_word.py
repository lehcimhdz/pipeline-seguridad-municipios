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
from calificar import agregar
from componer_documento import componer
from documentos import sha256
from contrato import huellas, cargar_contrato
from investigacion import validar_aporte
from unittest.mock import patch
from renderizar_word import (DICTIONARY, RULES, TEMPLATE, W, STYLE, auditar,
                             parrafo, reemplazar, renderizar, run, texto, validar_resultado)


def investigacion_sintetica():
    """Referencias ficticias, sólo para probar estructura, nunca para un municipio."""
    config = json.loads((ROOT / 'config/investigacion_seguridad.json').read_text())
    lines = []
    for definition in config['lineas']:
        url = 'https://example.org/' + definition['id']
        lines.append({'id': definition['id'], 'estado': 'verificado',
                      'analisis': 'Análisis sintético de pruebas. Fuente: ' + url,
                      'referencias': [{'titulo': 'Fuente sintética', 'url': url,
                                      'fecha_consulta': '2026-09-25', 'localizador': 'Sección de prueba',
                                      'aplicabilidad': 'Sólo prueba', 'revisado_por': 'Prueba automatizada'}]})
    url = lines[0]['referencias'][0]['url']
    return {'version': '1.0', 'lineas': lines, 'minimos_indicadores': {
        f'{i:02d}': {'texto': 'Mínimo sintético de pruebas. Fuente: ' + url,
                    'referencias': [url]} for i in range(1, 4)}}


def ejemplo(pending=True, research=None):
    dictionary = json.loads(DICTIONARY.read_text(encoding='utf-8'))
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    sections = []
    for ficha in rules['fichas']:
        number = ficha['id']
        evaluation = {'puntaje': None if pending and number == 4 else 5,
                      'años_evaluados': [2020, 2022], 'criterio_aplicado': f'Ficha {number}, criterio 5'}
        if evaluation['puntaje'] is None:
            evaluation['motivo'] = 'Falta población comparable.'
        sections.append({'numero': number, 'nombre': ficha['nombre'],
                         'evaluaciones': {p: deepcopy(evaluation) for p in ('general', 'ultimo_periodo')},
                         'control_cruzado_anexo': {'tablas_identicas': True, 'calificacion_reportada_coincide': True},
                         'tablas': [{'tabla': number, 'ambito': 'municipal',
                                     'filas': [['Año', 'Valor'], ['2020', 'Sí & válido < 100'], ['2022', '']]}]})
    values = {k: None for k in dictionary['variables_documento']}
    values.update(municipio='Municipio de prueba', estado='Entidad de prueba', año_inicial=2020, año_final=2022)
    result = {'municipio': values['municipio'], 'estado': values['estado'], 'estado_ejecucion': 'requiere_revision',
              'contrato': huellas(),
              'valores_plantilla': values, 'indicadores': sections,
              'calculos': {p: agregar({s['numero']: s['evaluaciones'][p] for s in sections}, rules)
                          for p in ('general', 'ultimo_periodo')},
              'validaciones': [{'nivel': 'bloqueante', 'codigo': 'COMPOSICION_WORD_PENDIENTE'},
                               {'nivel': 'bloqueante', 'codigo': 'VARIABLES_PENDIENTES'}]}
    if pending:
        result['validaciones'].append({'nivel': 'bloqueante', 'codigo': 'INDICADOR_PENDIENTE', 'indicador': 4})
    include_research = research if research is not None else not pending
    if include_research:
        result['investigacion_aportada'] = investigacion_sintetica()
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
        self.assertEqual(runs[1].find(W + 'rPr/' + W + 'highlight').get(W + 'val'), 'yellow')
        self.assertEqual(runs[1].find(W + 'rPr/' + W + 'shd').get(W + 'fill'), 'FFFF00')

    def test_composition_keeps_missing_scores_and_inactive_variables(self):
        result = ejemplo()
        self.assertIn('4', result['valores_plantilla']['resumen_general'])
        self.assertNotIn('condicion_critica', result['valores_plantilla'])
        self.assertEqual(result['contenido_word']['variables_no_aplicables'], [])
        self.assertIsNone(result['calculos']['general']['calificacion_final'])
        codes = {v['codigo'] for v in result['validaciones']}
        self.assertNotIn('COMPOSICION_WORD_PENDIENTE', codes)
        self.assertIn('INDICADOR_PENDIENTE', codes)
        self.assertIn('REVISION_EDITORIAL_WORD', codes)

    def test_draft_roundtrip_highlight_hashes_and_replaces_current_output(self):
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
            self.assertTrue(report['resaltado_amarillo_verificado'])
            with zipfile.ZipFile(word) as archive:
                root = ET.fromstring(archive.read('word/document.xml'))
                text = texto(root)
                self.assertIn('BORRADOR DE REVISIÓN', text)
                self.assertIn('Sí & válido < 100', text)
                self.assertIn('Falta población comparable', text)
                self.assertNotIn('TEXTOS BASE', text)
                self.assertNotIn('{', text)
                self.assertIn('Certificado', text)
                first = next(p for p in root.iter(W + 'p') if texto(p).startswith('La medición examina'))
                subsequent = next(p for p in root.iter(W + 'p') if texto(p).startswith('El documento conserva'))
                self.assertEqual(first.find(W + 'pPr/' + W + 'ind').get(W + 'firstLine'), '0')
                self.assertEqual(subsequent.find(W + 'pPr/' + W + 'ind').get(W + 'firstLine'), '283')
                sections = root.findall('.//' + W + 'sectPr')
                self.assertEqual(len(sections), 2)
                for r in root.iter(W + 'r'):
                    style = r.find(W + 'rPr/' + W + 'rStyle')
                    if style is not None and style.get(W + 'val') == STYLE:
                        self.assertEqual(r.find(W + 'rPr/' + W + 'highlight').get(W + 'val'), 'yellow')
                        self.assertEqual(r.find(W + 'rPr/' + W + 'shd').get(W + 'fill'), 'FFFF00')
                        self.assertIn(r.find(W + 'rPr/' + W + 'rFonts').get(W + 'ascii'), ('Archivo Light', 'Archivo Medium', 'Archivo'))
            again = renderizar(path, word.parent)
            self.assertEqual(report['archivo'], again['archivo'])
            self.assertEqual(again['sha256'], sha256(word))
        self.assertEqual(before, sha256(TEMPLATE))

    def test_final_refuses_partial_data_even_if_state_is_changed(self):
        result = ejemplo(research=True)
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

    def test_audit_rejects_unhighlighted_generated_text(self):
        p = parrafo('Texto procedente del JSON')
        props = p.find(W + 'r/' + W + 'rPr')
        props.remove(props.find(W + 'highlight'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.docx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('word/document.xml', ET.tostring(p))
            with self.assertRaisesRegex(ValueError, 'sin resaltado'):
                auditar(path)

    def test_measurement_uses_editorial_fonts_and_native_chart_relationships(self):
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
                                                '{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr').get('val'), 'FFFF00')
                relations = ET.fromstring(archive.read('word/_rels/document.xml.rels'))
                chart_targets = [r.get('Target') for r in relations if r.get('Type', '').endswith('/chart')]
                self.assertEqual(len(chart_targets), len(charts))
                self.assertTrue(all('word/' + target in archive.namelist() for target in chart_targets))

    def test_visual_data_tampering_is_rejected(self):
        for kind in ('graph', 'table', 'worksheet'):
            result = json.loads(json.dumps(ejemplo()))
            if kind == 'graph':
                result['valores_plantilla']['graficas_indicador_01'][0]['valores'][0] = 1
            elif kind == 'table':
                result['valores_plantilla']['tablas_indicador_01'][0]['filas'][1][1] = 'Inventado'
            else:
                result['contenido_word']['hoja_computo'][0]['general'] = '1'
            with self.assertRaises(ValueError):
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

    def test_final_rejects_missing_research_even_after_clearing_reviews(self):
        result = ejemplo(pending=False, research=False)
        result['estado_ejecucion'] = 'validado'
        result['validaciones'] = []
        with self.assertRaisesRegex(ValueError, 'Variable pendiente'):
            validar_resultado(result, 'final')

    def test_research_requires_reviewed_citations_and_known_minimum_sources(self):
        for kind in ('references', 'reviewer', 'citation', 'minimum', 'duplicate'):
            aporte = investigacion_sintetica()
            if kind == 'references':
                aporte['lineas'][0]['referencias'] = []
            elif kind == 'reviewer':
                aporte['lineas'][0]['referencias'][0]['revisado_por'] = ''
            elif kind == 'citation':
                aporte['lineas'][0]['analisis'] = 'Sin cita'
            elif kind == 'minimum':
                aporte['minimos_indicadores']['01']['referencias'] = ['https://example.org/desconocida']
            else:
                aporte['lineas'].append(deepcopy(aporte['lineas'][0]))
            with self.assertRaises(ValueError):
                validar_aporte(aporte)

    def test_pending_benchmark_cannot_claim_verified_content(self):
        result = ejemplo()
        result['valores_plantilla']['benchmark_proteccion_civil'] = 'Conclusión sin evidencia'
        with self.assertRaisesRegex(ValueError, 'Benchmark pendiente'):
            validar_resultado(result, 'borrador')

    def test_research_cannot_redirect_its_template_variable(self):
        result = ejemplo(pending=False)
        result['investigacion']['lineas'][0]['variable'] = 'municipio'
        with self.assertRaisesRegex(ValueError, 'Variable de benchmark'):
            validar_resultado(result, 'borrador')

    def test_changed_original_blocks_contract_without_touching_files(self):
        contract = cargar_contrato()
        origin = ROOT / contract['plantillas']['medicion']['origen']
        def altered_hash(path):
            return 'cambio simulado' if path == origin else sha256(path)
        with patch('contrato.sha256', side_effect=altered_hash):
            with self.assertRaisesRegex(ValueError, 'machote de origen'):
                cargar_contrato()


if __name__ == '__main__':
    unittest.main()
