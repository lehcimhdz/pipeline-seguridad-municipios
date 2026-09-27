"""Reproduce reglas desde la metodología histórica; los nuevos DOCX son editoriales."""
from copy import deepcopy
import json
from pathlib import Path
from documentos import sha256

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/metodologia_seguridad.json'
DEST = ROOT / 'reglas_calificacion.json'


def construir():
    historical = json.loads(SOURCE.read_text(encoding='utf-8'))
    if [f['id'] for f in historical['fichas']] != list(range(1, 19)):
        raise ValueError('Las fichas metodológicas no son exactamente 1–18.')
    if any(sorted(c['puntaje'] for c in f['criterios']) != [1, 2, 3, 4, 5] for f in historical['fichas']):
        raise ValueError('Se requieren los cinco criterios en cada ficha.')
    result = deepcopy(historical)
    result['version'] = '2.1'
    result['fuente_historica'] = historical['fuente']
    result['fuente'] = {'archivo': str(SOURCE.relative_to(ROOT)), 'sha256': sha256(SOURCE)}
    result['alcance'] = 'Sólo SEGURIDAD en el documento de medición general; evidencia exclusiva del paquete de seguridad y su anexo.'
    result['politica_evidencia'] = {
        'fuentes_admitidas': ['{municipio} PAQUETE SEGURIDAD.docx', '{municipio} Anexo.docx'],
        'fuente_primaria': 'PAQUETE SEGURIDAD', 'control_cruzado': 'Anexo',
        'fuentes_externas': False,
        'muestra_estilo': 'Referencia editorial; no aporta datos, calificaciones ni estándares.',
        'faltantes': 'Puntaje null cuando falta evidencia comparable; no convertir vacíos en cero, ausencia municipal o puntaje 1.',
        'calificaciones_reportadas': 'Se conservan para contraste, sin sustituir los puntajes calculados.',
        'agregacion': 'Requiere los 18 puntajes del periodo; no completar ni promediar un subconjunto.',
        'ultimo_periodo': 'Dos años calendario consecutivos de cierre comunes a los 18 indicadores; no sustituir un año faltante por una edición anterior.',
        'parametros_conservados': '18 indicadores, 90 criterios, escala 1–5, tres dimensiones, dependencias y candados de la transcripción histórica.',
        'limites': 'Los umbrales históricos no acreditan vigencia normativa ni estándares externos. Las tasas requieren denominadores documentados en las dos fuentes.'}
    return result


if __name__ == '__main__':
    DEST.write_text(json.dumps(construir(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Reglas reproducidas: 18 fichas, 90 criterios; regenerar el contrato si cambió la metodología.')
