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
from renderizar_word import (DICTIONARY, RULES, TEMPLATE, W, STYLE, auditar,
                             parrafo, reemplazar, renderizar, run, texto, validar_resultado)


def ejemplo(pending=True):
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
              'contrato': {'plantilla_sha256': sha256(TEMPLATE), 'diccionario_sha256': sha256(DICTIONARY), 'reglas_sha256': sha256(RULES)},
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
        for text in ('Antes {{ muni', 'cipio }} después'):
            r = run(text, generated=False)
            ET.SubElement(r.find(W + 'rPr'), W + 'i')
            p.append(r)
        reemplazar(p, '{{ municipio }}', 'A & B < C')
        self.assertEqual(texto(p), 'Antes A & B < C después')
        runs = list(p.iter(W + 'r'))
        self.assertEqual(len(runs), 3)
        for r in runs:
            self.assertIsNotNone(r.find(W + 'rPr/' + W + 'i'))
        self.assertIsNone(runs[0].find(W + 'rPr/' + W + 'highlight'))
        self.assertIsNone(runs[2].find(W + 'rPr/' + W + 'highlight'))
        self.assertEqual(runs[1].find(W + 'rPr/' + W + 'highlight').get(W + 'val'), 'yellow')

    def test_composition_keeps_missing_scores_and_inactive_variables(self):
        result = ejemplo()
        self.assertIn('4', result['valores_plantilla']['resumen_general'])
        self.assertIsNone(result['valores_plantilla']['condicion_critica'])
        self.assertIn('condicion_critica', result['contenido_word']['variables_no_aplicables'])
        self.assertIsNone(result['calculos']['general']['calificacion_final'])
        codes = {v['codigo'] for v in result['validaciones']}
        self.assertNotIn('COMPOSICION_WORD_PENDIENTE', codes)
        self.assertIn('INDICADOR_PENDIENTE', codes)
        self.assertIn('REVISION_EDITORIAL_WORD', codes)

    def test_draft_roundtrip_highlight_hashes_and_no_overwrite(self):
        result = ejemplo()
        before = sha256(TEMPLATE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'municipio.json'
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            report = renderizar(path, Path(directory) / 'word')
            word = Path(report['archivo'])
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
                self.assertNotIn('{{', text)
                self.assertIn('Anexo 1.', text)
                self.assertIn('Anexo 2.', text)
                sections = root.findall('.//' + W + 'sectPr')
                self.assertEqual(len(sections), 2)
                self.assertEqual(sections[-1].find(W + 'pgSz').get(W + 'orient'), 'landscape')
                for r in root.iter(W + 'r'):
                    style = r.find(W + 'rPr/' + W + 'rStyle')
                    if style is not None and style.get(W + 'val') == STYLE:
                        self.assertEqual(r.find(W + 'rPr/' + W + 'highlight').get(W + 'val'), 'yellow')
                        self.assertEqual(r.find(W + 'rPr/' + W + 'rFonts').get(W + 'ascii'), 'Archivo Light')
            again = renderizar(path, word.parent)
            self.assertNotEqual(report['archivo'], again['archivo'])
            self.assertEqual(report['sha256'], sha256(word))
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


if __name__ == '__main__':
    unittest.main()
