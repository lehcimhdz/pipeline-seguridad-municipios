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
    result['version'] = '3.0'
    result['fuente_historica'] = historical['fuente']
    result['fuente'] = {'archivo': str(SOURCE.relative_to(ROOT)), 'sha256': sha256(SOURCE)}
    result['alcance'] = 'Metodología histórica de seguridad preservada. El machote rzg aporta instrucciones editoriales y de investigación, no nuevos umbrales.'
    result['investigacion_modifica_puntajes'] = False
    return result


if __name__ == '__main__':
    DEST.write_text(json.dumps(construir(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Reglas reproducidas: 18 fichas, 90 criterios; regenerar el contrato si cambió la metodología.')
