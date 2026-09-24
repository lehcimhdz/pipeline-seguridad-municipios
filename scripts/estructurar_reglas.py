"""Exporta las 18 fichas y sus 90 criterios desde el DOCX, con reglas ejecutables."""
import json
import re
from pathlib import Path
from documentos import leer_docx, sha256

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates/Machote_seguridad_general_con_calificacion.docx'
DEST = ROOT / 'reglas_calificacion.json'
BINARY = {1, 6, 11, 12, 13, 16}


def condiciones(number):
    # Lista de [métrica, operador, valor]; evaluación de arriba abajo.
    if number in BINARY:
        return [
            (5, [['todas', 'eq', True]]),
            (4, [['dos_recientes', 'eq', True], ['proporcion', 'ge', 0.5]]),
            (2, [['alguna', 'eq', True], ['ninguna_reciente', 'eq', True]]),
            (3, [['alguna', 'eq', True]]),
            (1, [['alguna', 'eq', False]]),
        ]
    if number == 2:
        return [
            (5, [['cursos_y_personal_siempre', 'eq', True]]),
            (4, [['proporcion', 'ge', 0.75], ['dos_recientes', 'eq', True]]),
            (3, [['proporcion', 'ge', 0.5]]),
            (3, [['ultima', 'eq', True]]),
            (2, [['alguna', 'eq', True], ['proporcion', 'lt', 0.5], ['ninguna_reciente', 'eq', True]]),
            (1, [['alguna', 'eq', False]]),
        ]
    if number in (5, 7):
        return [
            (5, [['promedio', 'ge', 95], ['minimo', 'ge', 85]]),
            (4, [['promedio', 'ge', 85], ['promedio', 'le', 94.9]]),
            (3, [['promedio', 'ge', 70], ['promedio', 'le', 84.9]]),
            (2, [['promedio', 'ge', 50], ['promedio', 'le', 69.9]]),
            (1, [['promedio', 'lt', 50]]),
        ]
    return []


def construir():
    fichas = []
    active = False
    current = None
    for block in leer_docx(TEMPLATE):
        if block['tipo'] == 'parrafo':
            text = block['texto'].strip()
            if text.startswith('Anexo 1.'):
                active = True
            if text.startswith('Anexo 2.'):
                break
            if not active:
                continue
            match = re.match(r'Ficha (\d+)\. (.+)', text)
            if match:
                current = {'id': int(match[1]), 'nombre': match[2], 'criterios': [], 'texto_fuente': []}
                fichas.append(current)
            if current:
                current['texto_fuente'].append({'bloque': block['bloque'], 'texto': text})
        elif active and current:
            for row_number, row in enumerate(block['filas'], 1):
                match = re.match(r'([1-5])\s*·', row[0]) if row else None
                if match:
                    current['criterios'].append({'puntaje': int(match[1]), 'criterio': row[1],
                                                 'tabla': block['tabla'], 'fila': row_number})
    if [x['id'] for x in fichas] != list(range(1, 19)):
        raise ValueError('Las fichas no son exactamente 1–18.')
    catalog = json.loads((ROOT / 'diccionario_datos_diagnostico_seguridad_municipal.json').read_text())
    for ficha, entry in zip(fichas, catalog['catalogo_indicadores']):
        number = ficha['id']
        if sorted(c['puntaje'] for c in ficha['criterios']) != [1, 2, 3, 4, 5]:
            raise ValueError(f'Faltan criterios en ficha {number}')
        ficha['datos_requeridos'] = entry['datos_especificos']
        ficha['periodicidad'] = 'anual' if number in (17, 18) else 'por_edicion'
        ficha['metodo'] = 'existencia' if number in BINARY else 'cursos' if number == 2 else 'porcentaje' if number in (5, 7) else 'revision_contextual'
        ficha['reglas_ejecutables'] = [
            {'puntaje': score, 'todas': cond, 'referencia': f'Ficha {number}, criterio {score}'}
            for score, cond in condiciones(number)
        ]
        ficha['regla_especifica'] = entry.get('regla_especifica')
        ficha['precauciones'] = entry.get('precauciones', [entry['precaucion']] if 'precaucion' in entry else [])
    return {
        'version': '1.0',
        'fuente': {'archivo': str(TEMPLATE.relative_to(ROOT)), 'sha256': sha256(TEMPLATE)},
        'alcance': 'Transcripción de criterios internos; no verifica vigencia legal ni bibliográfica.',
        'criterio_operativo': {
            'prioridad': 'Primera regla satisfecha. En binarios, ausencia en el último periodo aplica 2 antes de intermitencia (3).',
            'huecos': 'No interpolar huecos entre umbrales ni asignar puntaje si no se satisface un criterio explícito.',
            'faltantes': 'Una celda vacía no demuestra falta de respuesta municipal; requiere clasificación.',
            'periodos': 'General: todas las observaciones documentadas. Último: dos etiquetas temporales más recientes, sin saltar vacíos.',
            'cobertura': 'No inferir que una variable no existía en las ediciones ausentes; declarar cobertura observada.',
            'redondeo': 'Agregación: ROUND_HALF_UP a dos decimales para clasificar; precisión interna conservada.',
            'ajustes': 'No se aplican ajustes discrecionales automáticos.',
        },
        'dimensiones': {'proteccion_civil': [1, 2, 3], 'condiciones_del_personal': list(range(4, 11)),
                        'inteligencia_y_eficiencia_policial': list(range(11, 19))},
        'escala': [{'minimo': low, 'calificacion': name} for low, name in
                   [(4.5, 'EXCELENTE'), (3.5, 'MUY BIEN'), (2.5, 'REGULAR'), (1.5, 'MAL'), (1, 'CATASTRÓFICO')]],
        'candados': catalog['calculos_derivados']['reglas_generales_del_documento'],
        'fichas': fichas,
    }


if __name__ == '__main__':
    DEST.write_text(json.dumps(construir(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Reglas exportadas: 18 fichas, 90 criterios documentales.')
