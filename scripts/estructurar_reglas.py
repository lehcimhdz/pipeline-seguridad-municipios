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
    result['version'] = '2.3'
    for key, filename in (('ponderacion_config', 'ponderacion.json'), ('definiciones_config', 'definiciones_cngmd.json')):
        result[key] = json.loads((ROOT / 'config' / filename).read_text(encoding='utf-8'))
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
    result['agregacion']['modos']['evaluables'].update(
        formula=result['ponderacion_config']['agregacion']['evaluables']['formula'],
        peso_dimensiones='25% protección civil, 35% condiciones del personal, 40% inteligencia y eficiencia policial',
        minimo_prioritarios=6)
    result['agregacion']['esquema_predeterminado'] = 'dimensiones_ponderadas'
    result['politica_evidencia']['fuentes_externas'] = True
    result['politica_evidencia']['condiciones_fuentes_externas'] = 'Complementos explícitos: archivo íntegro con SHA-256, identidad municipal, año, localizador y revisión. No búsqueda ni imputación automática.'
    result['politica_evidencia']['precedencia'] = 'El anexo de integración 2.3 y config/definiciones_cngmd.json prevalecen sobre criterios históricos incompatibles; los 90 criterios originales se conservan como transcripción, no como única especificación ejecutable.'
    result['politica_evidencia']['parametros_conservados'] = '18 indicadores y escala 1–5. Agregación, definiciones y fichas 3 y 15 revisadas explícitamente en 2.3.'
    result['convenciones_ejecutables']['implementacion_vigente'] = 'evaluacion_v23.evaluar y ponderacion.agregar_ponderado; calificar conserva las reglas base y la comparación histórica.'
    result['politica_evidencia']['correspondencias'] = 'Resolver automáticamente campos explícitos y homologaciones autorizadas en definiciones_cngmd.json, con coordenadas por año. No exigir un complemento vacío como paso previo; sólo resolver ambigüedades o aportar datos realmente ausentes. Las contradicciones bloquean la valoración.'
    for ficha in result['fichas']:
        ficha['peso'] = result['ponderacion_config']['ponderacion']['pesos'][str(ficha['id'])]
        ficha['prioritario'] = ficha['id'] in result['ponderacion_config']['ponderacion']['prioritarios']
        if ficha['id'] in (2, 3, 4, 5, 7, 9, 10, 14, 15, 18):
            ficha['revision_definiciones'] = 'Resolver las correspondencias desde las entradas por año; exigir evidencia complementaria sólo para los requisitos que sigan sin acreditarse. Una homologación metodológica no equivale a revisión humana.'
        if ficha['id'] in (3, 15):
            ficha['escala_vigente'] = result['definiciones_config']['escalas_operativas'][
                'proteccion_civil' if ficha['id'] == 3 else 'llamadas']
    staff = result['fichas'][3]['datos_requeridos']
    staff.pop('total_personal', None)
    staff['personal_policial'] = {'tipo_dato': 'integer', 'minimo': 0, 'universo': 'Corporaciones policiales; excluye administrativos.'}
    staff['policias_por_mil_habitantes']['formula'] = 'personal_policial / poblacion * 1000'
    result['fichas'][8]['datos_requeridos']['naturaleza_del_dato'] = {
        'tipo_dato': 'string', 'opciones': ['asignado_al_cierre'],
        'precaucion': 'Unidades asignadas, no personas que recibieron equipo ni compras anuales.'}
    result['fichas'][14]['datos_requeridos'] = {
        'llamadas_procedentes': {'tipo_dato': 'integer', 'minimo': 0},
        'registro_municipal': {'tipo_dato': 'boolean', 'debe_contener': 'Competencia del registro verificada por año.'},
        'poblacion': {'tipo_dato': 'integer', 'minimo': 1},
        'meta_respuesta': {'tipo_dato': 'string', 'obligatorio_para': 'Puntaje 5, cumplimiento documentado en cada año.'}}
    return result


if __name__ == '__main__':
    serialized = json.dumps(construir(), ensure_ascii=False, indent=2) + '\n'
    SOURCE.write_text(serialized, encoding='utf-8')
    DEST.write_text(serialized, encoding='utf-8')
    print('Benchmark transcrito: 18 fichas, 90 criterios; regenerar el contrato documental.')
