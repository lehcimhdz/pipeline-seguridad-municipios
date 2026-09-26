"""Normaliza únicamente SEGURIDAD y genera dos bases editoriales operativas.

Idempotente. Los otros ejes de los originales y el documento electoral se
conservan. Ejecutar al recibir una nueva revisión de los machotes generales.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import zipfile
from lxml import etree as ET
from documentos import sha256
from editorial import configurar, FORMATO
from fuentes_word import incrustar, FONTS

ROOT = Path(__file__).resolve().parents[1]
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MARKER = re.compile(r'(?<!\{)\{([a-z][a-z0-9_]*)\}(?!\})')


def text(node):
    return ''.join(t.text or '' for t in node.iter(W + 't'))


def paragraph(value, model=None):
    p = ET.Element(W + 'p')
    if model is not None and model.find(W + 'pPr') is not None:
        p.append(deepcopy(model.find(W + 'pPr')))
    ET.SubElement(ET.SubElement(p, W + 'r'), W + 't').text = value
    return p


def save(path, files):
    with tempfile.NamedTemporaryFile(suffix='.docx', dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    dictionary_path = ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json'
    dictionary = json.loads(dictionary_path.read_text(encoding='utf-8'))
    rules_path = ROOT / 'reglas_calificacion.json'
    rules = json.loads(rules_path.read_text(encoding='utf-8'))
    methodology_path = ROOT / 'config/metodologia_seguridad.json'
    if not methodology_path.exists():
        # Las nuevas bases no incluyen las fichas; preservar la transcripción histórica.
        dump(methodology_path, rules)
    templates = {}
    counts = Counter()
    per_template = {}
    for perfil, name in [('medicion', 'Machote general medicion version final.docx'),
                         ('anexo', 'Machote general anexos version final.docx')]:
        source = ROOT / 'templates' / name
        with zipfile.ZipFile(source) as z:
            files = {n: z.read(n) for n in z.namelist()}
        root = ET.fromstring(files['word/document.xml'])
        body = root.find(W + 'body')
        blocks = list(body)
        starts = [i for i, b in enumerate(blocks) if text(b).strip() == 'SEGURIDAD']
        if len(starts) != 1:
            raise ValueError(f'{name}: se requiere un capítulo SEGURIDAD único.')
        start = starts[0]
        end = next(i for i in range(start + 1, len(blocks))
                   if text(blocks[i]).strip().startswith('DESARROLLO URBANO SOSTENIBLE'))
        section = [deepcopy(blocks[start])]
        if perfil == 'medicion':
            section.extend([paragraph('CALIFICACIÓN GENERAL: {calificacion_general}'),
                            paragraph('CALIFICACIÓN DEL ÚLTIMO PERIODO: {calificacion_ultimo_periodo}'),
                            paragraph('{resumen_general}'), paragraph('{resumen_ultimo_periodo}')])
        else:
            section.append(paragraph('{tabla_calificaciones}'))
        for entry in dictionary['catalogo_indicadores']:
            number = entry.get('id', entry.get('numero'))
            if number is None:
                raise ValueError('Indicador sin id.')
            heading = next((b for b in blocks[start:end]
                            if entry['nombre'].casefold() in text(b).strip().casefold()
                            and b.tag == W + 'p' and '[' not in text(b)), None)
            section.append(paragraph(f"Indicador {number:02d}: {entry['nombre']}", heading))
            keys = ([f'analisis_indicador_{number:02d}', f'graficas_indicador_{number:02d}',
                     f'tablas_indicador_{number:02d}', f'cierre_indicador_{number:02d}']
                    if perfil == 'medicion' else [f'graficas_indicador_{number:02d}',
                                                f'tablas_estatales_indicador_{number:02d}',
                                                f'tablas_municipales_indicador_{number:02d}'])
            for key in keys:
                section.append(paragraph('{' + key + '}'))
        # Reemplazar solamente el capítulo de SEGURIDAD del original.
        for b in blocks[start:end]:
            body.remove(b)
        for offset, b in enumerate(section):
            body.insert(start + offset, b)
        files['word/document.xml'] = ET.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
        save(source, files)
        # Base operativa: portada, logo original y únicamente el capítulo contratado.
        operational = deepcopy(root)
        opbody = operational.find(W + 'body')
        final_section = deepcopy(opbody.find(W + 'sectPr'))
        for node in final_section.findall(W + 'type'):
            node.set(W + 'val', 'nextPage')
        for node in final_section.findall(W + 'cols'):
            node.set(W + 'num', '1')
        logo = next((deepcopy(p) for p in root.iter(W + 'p') if p.find('.//' + W + 'drawing') is not None), None)
        for b in list(opbody):
            opbody.remove(b)
        cover_title = configurar(paragraph('Mediciones de Funcionamiento Municipal — SEGURIDAD' if perfil == 'medicion'
                                           else 'ANEXO. Mediciones de Funcionamiento Municipal — SEGURIDAD'), perfil, 'titulo')
        layout = json.loads(FORMATO.read_text(encoding='utf-8'))
        page = final_section.find(W + 'pgSz'); margins = final_section.find(W + 'pgMar')
        usable = int(page.get(W + 'h')) - int(margins.get(W + 'top')) - int(margins.get(W + 'bottom'))
        line = layout[perfil]['titulo'][2] * 20
        # Espaciador explícito para centrar la portada también en visores que
        # omiten w:vAlign. Dos líneas de título, identidad inmediatamente debajo.
        cover_title.find(W + 'pPr/' + W + 'spacing').set(W + 'before', str(max(0, (usable - 2 * line) // 2)))
        opbody.append(cover_title)
        identity = configurar(paragraph('{municipio}, {estado}'), perfil, 'cuerpo')
        identity.find(W + 'pPr/' + W + 'jc').set(W + 'val', 'center')
        opbody.append(identity)
        if logo is not None:
            configurar(logo, perfil, 'cuerpo')
            wp = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
            a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
            for ext in logo.iter(wp + 'extent'):
                old_x, old_y = int(ext.get('cx')), int(ext.get('cy'))
                x, y = 1800000, round(old_y * 1800000 / old_x)
                ext.set('cx', str(x)); ext.set('cy', str(y))
                for size in logo.iter(a + 'ext'):
                    size.set('cx', str(x)); size.set('cy', str(y))
            inline = logo.find('.//' + wp + 'inline')
            if inline is not None:
                anchor = ET.Element(wp + 'anchor', {'distT': '0', 'distB': '0', 'distL': '0', 'distR': '0',
                    'simplePos': '0', 'relativeHeight': '0', 'behindDoc': '0', 'locked': '0',
                    'layoutInCell': '1', 'allowOverlap': '1'})
                ET.SubElement(anchor, wp + 'simplePos', {'x': '0', 'y': '0'})
                ET.SubElement(ET.SubElement(anchor, wp + 'positionH', {'relativeFrom': 'page'}), wp + 'align').text = 'center'
                ET.SubElement(ET.SubElement(anchor, wp + 'positionV', {'relativeFrom': 'margin'}), wp + 'align').text = 'bottom'
                for tag in ('extent', 'effectExtent'):
                    node = inline.find(wp + tag)
                    if node is not None:
                        anchor.append(deepcopy(node))
                ET.SubElement(anchor, wp + 'wrapNone')
                for tag in ('docPr', 'cNvGraphicFramePr'):
                    node = inline.find(wp + tag)
                    if node is not None:
                        anchor.append(deepcopy(node))
                anchor.append(deepcopy(inline.find(a + 'graphic')))
                inline.getparent().replace(inline, anchor)
            opbody.append(logo)
        cover_section = deepcopy(final_section)
        for node in cover_section.findall(W + 'vAlign'):
            cover_section.remove(node)
        valign = ET.Element(W + 'vAlign', {W + 'val': 'top'})
        grid = cover_section.find(W + 'docGrid')
        cover_section.insert(cover_section.index(grid) if grid is not None else len(cover_section), valign)
        break_p = paragraph('')
        props = ET.Element(W + 'pPr'); break_p.insert(0, props)
        props.append(cover_section)
        opbody.append(break_p)
        for p in section:
            copied = deepcopy(p)
            value = text(copied).strip()
            rol = 'capitulo' if value == 'SEGURIDAD' else 'subcapitulo' if value.startswith('Indicador ') else 'calificacion' if value.startswith('CALIFICACIÓN') else 'cuerpo'
            opbody.append(configurar(copied, perfil, rol))
        # Bibliografía exacta de las entradas, nunca un banco de fuentes no usadas.
        opbody.append(configurar(paragraph('Fuentes documentales'), perfil, 'subcapitulo'))
        opbody.append(configurar(paragraph('{bibliografia}'), perfil, 'bibliografia'))
        opbody.append(final_section)
        opfiles = dict(files)
        opfiles['word/document.xml'] = ET.tostring(operational, encoding='UTF-8', xml_declaration=True, standalone=True)
        incrustar(opfiles)
        dest = ROOT / 'templates' / f'seguridad_{perfil}.docx'
        save(dest, opfiles)
        found = Counter(MARKER.findall(text(operational)))
        counts.update(found)
        per_template[perfil] = dict(found)
        templates[perfil] = {'archivo': str(dest.relative_to(ROOT)), 'sha256': sha256(dest),
                             'origen': str(source.relative_to(ROOT)), 'origen_sha256': sha256(source)}
    variables = {}
    for key, count in counts.items():
        tipo = 'array' if key.startswith(('graficas_', 'tablas_')) or key == 'tabla_calificaciones' else 'string'
        variables[key] = {'marcador': '{' + key + '}', 'apariciones': count, 'tipo_dato': tipo,
                          'apariciones_por_documento': {p: c.get(key, 0) for p, c in per_template.items()},
                          'tipo_contenido': 'graficas' if key.startswith('graficas_') else 'tablas' if tipo == 'array' else 'texto',
                          'debe_contener': 'Contenido específico de SEGURIDAD, sustentado en las fuentes de entrada.',
                          'obligatorio': not key.startswith('graficas_')}
    dictionary['metadatos'].update(version='3.0', fuente='Bases operativas de SEGURIDAD derivadas de los nuevos machotes de medición y anexos.')
    dictionary['metadatos']['cobertura_verificada'] = {'marcadores_de_variables_unicos': len(variables),
        'apariciones_de_variables': sum(counts.values()), 'indicadores': 18, 'dimensiones': 3, 'periodos_de_evaluacion': 2}
    dictionary['variables_documento'] = variables
    dictionary['convenciones']['marcadores'] = {'formato_en_word': '{nombre_variable}',
        'formato_de_clave_json': 'nombre_variable', 'regla': 'Llaves simples; claves ASCII snake_case únicas por indicador.'}
    dictionary['convenciones']['nombres_de_variables'].update(conservar_nombres_existentes=False, conservar_letra_ñ=False,
                                                             ejemplos=['municipio', 'analisis_indicador_01', 'tablas_indicador_01'])
    dictionary['marcadores_no_tratados_como_variables'] = {}
    dictionary['validaciones_finales'] = [v for v in dictionary['validaciones_finales']
                                         if v['id'] not in ('variantes_correctas', 'resolucion_contextual')]
    dictionary['validaciones_finales'].extend(v for v in [
        {'id': 'contrato_editorial_v2', 'regla': '116 variables snake_case con llaves simples; apariciones por perfil y huellas de contrato coincidentes.'},
        {'id': 'objetos_visuales', 'regla': 'Tablas y gráficas deben coincidir con evidencia y puntajes; null no es cero.'}]
        if not any(existing['id'] == v['id'] for existing in dictionary['validaciones_finales']))
    dictionary['metadatos']['documento_modificado'] = True
    dictionary['metadatos']['alcance_activo'] = 'Sólo SEGURIDAD; los modelos auxiliares históricos no implican nuevos marcadores ni producto electoral.'
    dictionary['modelos_reutilizables']['tabla_word_v2'] = {'titulo': 'string', 'ambito': 'municipal|estatal',
                                                         'filas': 'array de arrays de strings', 'tabla_fuente': 'integer'}
    dictionary['modelos_reutilizables']['grafica_word_v2'] = {'tipo': 'puntajes', 'titulo': 'string',
        'categorias': 'array de strings', 'valores': 'array de number|null',
        'fuente': 'string', 'regla': 'null no se representa como cero; sólo puntajes calculados.'}
    dump(dictionary_path, dictionary)
    historical = json.loads(methodology_path.read_text(encoding='utf-8'))
    rules = deepcopy(historical)
    rules['version'] = '2.0'
    rules['fuente_historica'] = historical['fuente']
    rules['fuente'] = {'archivo': str(methodology_path.relative_to(ROOT)), 'sha256': sha256(methodology_path)}
    rules['alcance'] = 'Metodología de seguridad preservada; los machotes editoriales nuevos no contienen criterios de calificación.'
    dump(rules_path, rules)
    contract = {'version': '2.0', 'alcance': 'seguridad', 'marcador': '{snake_case}', 'plantillas': templates,
        'diccionario': {'archivo': str(dictionary_path.relative_to(ROOT)), 'sha256': sha256(dictionary_path)},
        'reglas': {'archivo': str(rules_path.relative_to(ROOT)), 'sha256': sha256(rules_path)},
        'formato': {'archivo': str(FORMATO.relative_to(ROOT)), 'sha256': sha256(FORMATO)},
        'tipografias': [{'archivo': f'assets/fonts/{filename}', 'sha256': sha256(ROOT / 'assets/fonts' / filename)}
                       for _, filename, _ in FONTS],
        'orden_indicadores': list(range(1, 19)),
        'correcciones': ['Medición: eliminar duplicado de personal e incorporar Certificado Único Policial como indicador 7.',
                        'Mantener EXCELENTE en la metodología; IDEAL del catálogo general no redefine umbrales.']}
    dump(ROOT / 'config/contrato_documental.json', contract)
    print(f'Migración: {len(variables)} variables, {sum(counts.values())} apariciones, dos bases de SEGURIDAD.')


if __name__ == '__main__':
    main()
