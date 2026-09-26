"""Actualiza el esquema sin sobreescribir los parámetros de las reglas activas."""
from copy import deepcopy
import json
from pathlib import Path
from documentos import sha256
from calificacion_documental import POLITICA_DOCUMENTAL, validar_politica

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/metodologia_seguridad.json'
DEST = ROOT / 'reglas_calificacion.json'


def construir(reglas_activas=None):
    historical = json.loads(SOURCE.read_text(encoding='utf-8'))
    if [f['id'] for f in historical['fichas']] != list(range(1, 19)):
        raise ValueError('Las fichas metodológicas no son exactamente 1–18.')
    if any(sorted(c['puntaje'] for c in f['criterios']) != [1, 2, 3, 4, 5] for f in historical['fichas']):
        raise ValueError('Se requieren los cinco criterios en cada ficha.')
    # La parametrización editorial no debe restablecer decisiones metodológicas.
    active = reglas_activas if reglas_activas is not None else (
        json.loads(DEST.read_text(encoding='utf-8')) if DEST.exists() else historical)
    result = deepcopy(active)
    if [f['id'] for f in result['fichas']] != list(range(1, 19)):
        raise ValueError('Las reglas activas requieren exactamente las fichas 1–18.')
    result['version'] = '3.2'
    result['fuente_historica'] = historical['fuente']
    result['fuente'] = {'archivo': str(SOURCE.relative_to(ROOT)), 'sha256': sha256(SOURCE)}
    result['alcance'] = ('Puntaje observado según fichas y calificación documental siempre emitida; '
                         'la falta de evidencia no acredita desempeño deficiente.')
    result.setdefault('calificacion_documental', deepcopy(POLITICA_DOCUMENTAL))
    result['investigacion_modifica_puntajes'] = False
    result['periodo_reciente'] = {'criterio': 'dos_anios_consecutivos', 'anclaje': 'maximo_anio_municipal_documental',
        'faltantes': 'puntaje observado null y calificación documental no acreditada; no sustituir años'}
    result['criterio_operativo']['periodos'] = (
        'General: observaciones documentadas. Último: dos años calendario consecutivos comunes a los 18 indicadores.')
    result['criterio_operativo']['huecos'] = (
        'No interpolar: puntaje observado null si no hay criterio inequívoco; aplicar la política documental declarada.')
    result['criterio_operativo']['faltantes'] = (
        'Una celda vacía no demuestra falta de respuesta ni desempeño deficiente; conservar motivo y asignar nota documental.')
    validar_politica(result)
    return result


if __name__ == '__main__':
    DEST.write_text(json.dumps(construir(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Reglas activas conservadas y esquema actualizado; regenerar el contrato antes del pipeline.')
