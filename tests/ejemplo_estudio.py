"""Evidencia ficticia para verificar la entrega sin datos municipales privados."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from calificar import definir_periodos
from componer_documento import componer
from contrato import huellas
from documentos import sha256
from ilustraciones_word import catalogar_graficas, seleccionar_graficas
from evaluacion_v23 import evaluar
from ponderacion import agregar_ponderado
from evidencia_complementaria import vacia, huella_objeto
from redaccion_editorial import VINCULOS_METODOLOGICOS, huella_evaluacion


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
    rules = json.loads((ROOT / 'config/reglas_calificacion.json').read_text())
    mappings = json.loads((ROOT / 'config/normalizaciones.json').read_text())
    dictionary = json.loads((ROOT / 'config/diccionario_datos_diagnostico_seguridad_municipal.json').read_text())
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
            if number == 15:
                header, details = ['Año', 'Porcentaje', 'Llamadas procedentes'], [['95', '100']]
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
    supplemental = vacia(municipality, state)
    supplemental['fuentes'] = [{'id': 'prueba', 'titulo': 'Fuente ficticia para pruebas',
                                'archivo': str(source), 'sha256': sha256(source)}]
    provenance = {'fuente': 'prueba', 'localizador': 'Fixture sintético', 'revision': 'verificada'}
    for year in (2022, 2024):
        supplemental['poblacion'].append({**provenance, 'ambito': 'municipal', 'anio': year, 'valor': 1000,
            'metodo': 'proyeccion', 'serie': 'prueba', 'fecha_referencia': f'{year}-07-01'})
    for number, fields in {
        2: {'universo': 'personal_unidad_pc', 'conteo_personas': 'unico'},
        3: {'grupos_captados': list(rules['definiciones_config']['normalizacion_proteccion_civil']['grupos']), 'catalogo_completo': True},
        5: {'universo': 'corporaciones_policiales', 'definicion': 'aprobatorias_vigentes'},
        7: {'universo': 'corporaciones_policiales', 'definicion': 'cup_vigente'},
        10: {'universo': 'corporaciones_policiales', 'definicion': 'capacitacion_sin_profesionalizacion'},
        15: {'registro_municipal': True},
    }.items():
        supplemental['observaciones'][str(number)] = {str(y): {**provenance, **fields} for y in (2022, 2024)}
    evaluations = evaluar(sections, rules, mappings, periods, supplemental)
    for section in sections:
        section['evaluaciones'] = {p: evaluations[p][section['numero']] for p in evaluations}
    result = {'version': '2.3', 'municipio': municipality, 'estado': state, 'estado_ejecucion': 'compuesto',
              'evidencia_complementaria': supplemental, 'evidencia_complementaria_sha256': huella_objeto(supplemental),
              'esquema_ponderacion': 'dimensiones_ponderadas',
              'contrato': huellas(), 'fuentes': [{'archivo': source.name, 'sha256': sha256(source)}],
              'rutas_fuentes': {source.name: str(source)}, 'indicadores': sections,
              'periodos_evaluacion': periods, 'metodo_calificacion': modo,
              'calculos': {p: agregar_ponderado(v, rules, modo=modo) for p, v in evaluations.items()},
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
    artifact = {'version': '2.3', 'municipio': municipality, 'estado': state,
                'seleccion_editorial': {str(i): {'encuadre_id': str(i), 'revision_semantica': True,
                    'consecuencia_revisada': 'Revisar distribución por turno.'} for i in range(1, 19)},
                'vinculos': {'fuentes': deepcopy(result['fuentes']),
                            'evidencia_complementaria_sha256': result['evidencia_complementaria_sha256'],
                            'evaluacion_sha256': huella_evaluacion(result),
                            **{key: result['contrato'][key] for key in VINCULOS_METODOLOGICOS}},
                'revision': {'estado': 'revisada', 'tipo_autor': 'agente_editorial'},
                'hechos': facts, 'bloques': blocks}
    writing = directory / 'redaccion.json'
    writing.write_text(json.dumps(artifact, ensure_ascii=False), encoding='utf-8')
    result['redaccion_editorial'] = {'archivo': str(writing), 'sha256': sha256(writing)}
    componer(result, dictionary, rules, artifact)
    choices = [{'fuente': source.name, 'parte': 'word/media/original.png', 'indicador': 1}] if graficas else []
    result['contenido_word']['ilustraciones'] = seleccionar_graficas(result['catalogo_ilustraciones'], choices)
    return result
