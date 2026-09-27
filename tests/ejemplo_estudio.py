"""Evidencia ficticia para verificar la entrega sin datos municipales privados."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from calificar import calificar_indicador, agregar, dependencias, definir_periodos
from componer_documento import componer
from contrato import huellas
from documentos import sha256
from ilustraciones_word import catalogar_graficas, seleccionar_graficas


def ejemplo(directory, *, graficas=False, modo='evaluables'):
    directory = Path(directory)
    municipality, state = 'Municipio de prueba', 'Entidad de prueba'
    source = directory / (municipality + ' PAQUETE SEGURIDAD.docx')
    w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    r = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    wp = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
    xml = f'''<w:document xmlns:w="{w}" xmlns:r="{r}" xmlns:a="{a}" xmlns:wp="{wp}"><w:body>
      <w:p><w:r><w:t>SEGURIDAD</w:t></w:r></w:p>
      <w:p><w:r><w:t>Indicador: Plan de protección civil</w:t></w:r></w:p>
      <w:p><w:r><w:t>Datos Municipales</w:t></w:r></w:p>
      <w:p><w:r><w:drawing><wp:inline><wp:extent cx="3600000" cy="1800000"/>
      <wp:docPr id="1" name="Original"/><a:graphic><a:graphicData><a:blip r:embed="rId1"/>
      </a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>
      </w:body></w:document>'''
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aAn8AAAAASUVORK5CYII=')
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('word/document.xml', xml)
        archive.writestr('word/_rels/document.xml.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{r}/image" Target="media/original.png"/></Relationships>')
        archive.writestr('word/media/original.png', png)
    rules = json.loads((ROOT / 'reglas_calificacion.json').read_text())
    mappings = json.loads((ROOT / 'config/normalizaciones.json').read_text())
    dictionary = json.loads((ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json').read_text())
    sections = []
    for ficha in rules['fichas']:
        number = ficha['id']
        years = [2022, 2024] if number <= 16 else [2023, 2024]
        header, details = ['Año', 'Existencia'], [['Sí']]
        if number == 2:
            header, details = ['Año', 'Número de cursos', 'Número de servidores capacitados'], [['10', '100']]
        elif number == 3:
            header = ['Año', 'Tema impartido']
            details = [[topic] for topic in ('Identificación y análisis de riesgos', 'Sistema de comando de incidentes',
                       'Mapas de riesgo y alerta temprana', 'Evacuación búsqueda y rescate', 'Primeros auxilios')]
        elif number in (5, 7, 15):
            header, details = ['Año', 'Porcentaje'], [['95']]
        elif number == 8:
            header = ['Año', 'Elementos del uniforme', 'Otorgado', 'Frecuencia']
            details = [[item, 'Sí', 'Anual'] for item in ('Camisola', 'Pantalón', 'Botas', 'Chamarra', 'Fornitura', 'Chaleco táctico')]
        elif number == 10:
            header = ['Año', 'Tema', 'Total', 'Porcentaje']
            details = [[topic, '100', '90'] for topic in ('Primer respondiente', 'Informe Policial Homologado')]
        elif number in (4, 9, 14, 17, 18):
            header, details = ['Año', 'Total'], [['0' if number == 17 else '100']]
        tables = [{'tabla': number, 'ambito': 'municipal',
                   'filas': [header] + [[str(year), *detail] for year in years for detail in details]}]
        if number == 15:
            tables.append({'tabla': 99, 'ambito': 'estatal', 'filas': [header, ['2022', '90'], ['2024', '90']]})
        sections.append({'numero': number, 'nombre': ficha['nombre'], 'tablas': tables})
    periods = definir_periodos(sections)
    evaluations = {}
    for period in ('general', 'ultimo_periodo'):
        evaluations[period] = {s['numero']: calificar_indicador(
            s, rules['fichas'][s['numero'] - 1], period, mappings,
            años_objetivo=periods['ultimo_periodo']['por_indicador'][str(s['numero'])] if period == 'ultimo_periodo' else None)
            for s in sections}
        dependencias(evaluations[period])
    for section in sections:
        section['evaluaciones'] = {p: evaluations[p][section['numero']] for p in evaluations}
    result = {'version': '2.2', 'municipio': municipality, 'estado': state, 'estado_ejecucion': 'compuesto',
              'contrato': huellas(), 'fuentes': [{'archivo': source.name, 'sha256': sha256(source)}],
              'rutas_fuentes': {source.name: str(source)}, 'indicadores': sections,
              'periodos_evaluacion': periods, 'metodo_calificacion': modo,
              'calculos': {p: agregar(v, rules, modo=modo) for p, v in evaluations.items()},
              'catalogo_ilustraciones': catalogar_graficas(source), 'validaciones': []}
    facts = {}
    for section in sections:
        table = section['tablas'][0]
        facts[f'f{section["numero"]}'] = {'indicador': section['numero'], 'tabla': table['tabla'],
                                         'fila': 1, 'columna': table['filas'][0][1], 'valor': table['filas'][1][1]}
    paragraph = lambda fact: {'texto': 'La información municipal permite examinar la continuidad de esta función.', 'evidencia': [fact]}
    blocks = {f'analisis_indicador_{i:02d}': [paragraph(f'f{i}')] for i in range(1, 19)}
    blocks.update(resumen_general=[paragraph('f1'), paragraph('f5'), paragraph('f11')],
                  resumen_ultimo_periodo=[paragraph('f1'), paragraph('f5'), paragraph('f11')],
                  bibliografia=[{'texto': 'Información estadística municipal proporcionada para el estudio.', 'evidencia': []}])
    artifact = {'version': '2.2', 'municipio': municipality, 'estado': state,
                'vinculos': {'fuentes': deepcopy(result['fuentes']),
                            **{key: result['contrato'][key] for key in ('benchmark_sha256', 'reglas_sha256')}},
                'revision': {'estado': 'revisada', 'tipo_autor': 'agente_editorial'},
                'hechos': facts, 'bloques': blocks}
    writing = directory / 'redaccion.json'
    writing.write_text(json.dumps(artifact, ensure_ascii=False), encoding='utf-8')
    result['redaccion_editorial'] = {'archivo': str(writing), 'sha256': sha256(writing)}
    componer(result, dictionary, rules, artifact)
    choices = [{'fuente': source.name, 'parte': 'word/media/original.png', 'indicador': 1}] if graficas else []
    result['contenido_word']['ilustraciones'] = seleccionar_graficas(result['catalogo_ilustraciones'], choices)
    return result
