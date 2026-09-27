"""Transcribe los 90 criterios del benchmark activo y conserva su adaptación ejecutable."""
from copy import deepcopy
import json
from pathlib import Path
import re
from documentos import leer_docx, sha256

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/metodologia_seguridad.json'
BENCHMARK = ROOT / 'templates/Machote_seguridad_general_con_calificacion.docx'
DEST = ROOT / 'reglas_calificacion.json'


def construir():
    historical = json.loads(SOURCE.read_text(encoding='utf-8'))
    if [f['id'] for f in historical['fichas']] != list(range(1, 19)):
        raise ValueError('Las fichas metodológicas no son exactamente 1–18.')
    if any(sorted(c['puntaje'] for c in f['criterios']) != [1, 2, 3, 4, 5] for f in historical['fichas']):
        raise ValueError('Se requieren los cinco criterios en cada ficha.')
    result = deepcopy(historical)
    result['version'] = '2.2'
    result.pop('fuente_historica', None)
    result['fuente'] = {'archivo': str(BENCHMARK.relative_to(ROOT)), 'sha256': sha256(BENCHMARK)}
    current = None
    captured = set()
    for block in leer_docx(BENCHMARK):
        if block['tipo'] == 'parrafo':
            match = re.match(r'^Ficha (\d+)\.\s*(.+)$', block['texto'])
            if match:
                identifier = int(match[1])
                if identifier not in range(1, 19) or identifier in captured:
                    raise ValueError('Las fichas del benchmark no son únicas en el rango 1–18.')
                captured.add(identifier)
                current = result['fichas'][identifier - 1]
                current.update(nombre=match[2].strip(), texto_fuente=[], criterios=[])
            if block['texto'].startswith('Anexo 2.'):
                current = None
            if current is not None:
                current['texto_fuente'].append({'bloque': block['bloque'], 'texto': block['texto']})
        elif current is not None and block['filas'][0] == ['Puntaje', 'Criterio']:
            current['criterios'] = [
                {'puntaje': int(row[0].split('·')[0].strip()), 'criterio': row[1],
                 'tabla': block['tabla'], 'fila': index}
                for index, row in enumerate(block['filas'][1:], 2)]
    if captured != set(range(1, 19)) or any(
            sorted(c['puntaje'] for c in ficha['criterios']) != [1, 2, 3, 4, 5]
            for ficha in result['fichas']):
        raise ValueError('El benchmark activo debe contener 18 fichas con cinco criterios cada una.')
    # Cambiar el DOCX no debe conservar silenciosamente una lógica que ya no lo refleja.
    for before, after in zip(historical['fichas'], result['fichas']):
        if [(c['puntaje'], c['criterio']) for c in before['criterios']] != [
                (c['puntaje'], c['criterio']) for c in after['criterios']]:
            raise ValueError(f"Cambió la ficha {after['id']}; revisar su adaptación ejecutable antes de regenerar.")
    result['alcance'] = 'Estudio de seguridad en el formato de la consultora; estadísticas del paquete de seguridad y contraste opcional con su anexo.'
    result['fichas'][7]['metodo'] = 'uniformes'
    result['fichas'][16]['metodo'] = 'fallecimientos'
    result['criterio_operativo'].update(
        periodos='General: observaciones documentadas; reciente: dos ediciones censales para 1–16 y dos años calendario para 17–18.',
        ajustes='Sin ajustes discrecionales automáticos. La escala no acredita cumplimiento normativo ni vigencia de las referencias.',
        huecos='Combinaciones no definidas por las fichas conservan puntaje null; no interpolar umbrales.')
    result['agregacion'] = {
        'modo_predeterminado': 'completo',
        'modos': {
            'completo': {'requiere': '18 indicadores calificados', 'origen': 'Benchmark suministrado'},
            'evaluables': {
                'origen': 'Adaptación operativa; no equivale a la evaluación completa del benchmark',
                'cobertura_minima_por_dimension': '2/3 de sus indicadores, redondeado al entero superior',
                'minimos': {'proteccion_civil': 2, 'condiciones_del_personal': 5, 'inteligencia_y_eficiencia_policial': 6},
                'formula': 'Promedio de los indicadores evaluables dentro de cada dimensión; promedio simple de las tres dimensiones.',
                'peso_dimensiones': '1/3 cada una', 'imputacion': False,
                'tope_con_pendientes': 'MUY BIEN',
                'declaracion': 'Publicar cobertura y alcance parcial; conservar intervalo de sensibilidad de la evaluación completa.'}}}
    result['convenciones_ejecutables'] = {
        'uniformes': 'Homologar seis prendas básicas; camisola/camisa y tipos de calzado cuentan una vez por grupo. Frecuencias semestral y anual cumplen al menos anual. Dotación en una sola edición precede a incompleta.',
        'fallecimientos': 'Usar la serie municipal de conteos, no porcentajes de egresos ni sumar los desgloses. Mayoría significa más de la mitad de los años del periodo, incluidos los vacíos en el denominador; un conteo desconocido no se transforma en cero.',
        'ultimo_periodo': 'El criterio de todas las ediciones se evalúa sobre ambas recientes; un cumplimiento completo puede obtener 5.',
        'faltantes': 'Sólo una falta de respuesta municipal acreditada permite penalizarla como tal; denominadores ausentes no son evidencia de abandono.',
        'fuentes_normativas': 'Referencias aportadas por el benchmark; no constituyen verificación externa ni acreditan vigencia jurídica.'}
    result['politica_evidencia'] = {
        'fuentes_admitidas': ['{municipio} PAQUETE SEGURIDAD.docx', '{municipio} Anexo.docx (opcional)'],
        'fuente_primaria': 'PAQUETE SEGURIDAD', 'control_cruzado': 'Anexo, si se aporta',
        'fuentes_externas': False,
        'muestra_estilo': 'Referencia editorial; no aporta datos, calificaciones ni estándares.',
        'faltantes': 'Puntaje null cuando falta evidencia comparable; no convertir vacíos en cero, ausencia municipal o puntaje 1.',
        'calificaciones_reportadas': 'Se conservan para contraste, sin sustituir los puntajes calculados.',
        'agregacion': 'Modo completo requiere 18 puntajes; modo evaluables es una adaptación explícita con cobertura mínima por dimensión y alcance parcial.',
        'ultimo_periodo': 'Dos ediciones censales recientes para indicadores 1–16; dos años calendario recientes para 17–18. No omitir celdas vacías al seleccionar.',
        'parametros_conservados': '18 indicadores, 90 criterios, escala 1–5, tres dimensiones, dependencias y candados de la transcripción histórica.',
        'limites': 'Los umbrales del benchmark no acreditan vigencia normativa ni estándares externos. Las tasas requieren denominadores documentados; no se completan con cifras de la muestra editorial.'}
    return result


if __name__ == '__main__':
    serialized = json.dumps(construir(), ensure_ascii=False, indent=2) + '\n'
    SOURCE.write_text(serialized, encoding='utf-8')
    DEST.write_text(serialized, encoding='utf-8')
    print('Benchmark transcrito: 18 fichas, 90 criterios; regenerar el contrato documental.')
