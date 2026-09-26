"""Contrato documental independiente de la metodología de calificación."""
import json
from pathlib import Path
from documentos import sha256

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'config/contrato_documental.json'


def cargar_contrato(verificar=True):
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    if verificar:
        for entry in [*contract['plantillas'].values(), contract['diccionario'], contract['reglas'], contract['formato'],
                      contract['investigacion'], contract['metodologia'], *contract.get('tipografias', []), *contract.get('logotipo', [])]:
            if sha256(ROOT / entry['archivo']) != entry['sha256']:
                raise ValueError(f"Cambió el contrato documental: {entry['archivo']}. Ejecutar scripts/migrar_machote_v3.py y revisar.")
        for entry in contract['plantillas'].values():
            if sha256(ROOT / entry['origen']) != entry['origen_sha256']:
                raise ValueError(f"Cambió el machote de origen: {entry['origen']}. Ejecutar scripts/migrar_machote_v3.py antes del pipeline.")
    return contract


def huellas():
    contract = cargar_contrato()
    return {'version': contract['version'], 'contrato_documental_sha256': sha256(CONTRACT),
            'plantilla_sha256': contract['plantillas']['medicion']['sha256'],
            'plantillas_sha256': {key: entry['sha256'] for key, entry in contract['plantillas'].items()},
            'diccionario_sha256': contract['diccionario']['sha256'],
            'reglas_sha256': contract['reglas']['sha256'], 'formato_sha256': contract['formato']['sha256'],
            'investigacion_sha256': contract['investigacion']['sha256'],
            'origenes_sha256': {key: entry['origen_sha256'] for key, entry in contract['plantillas'].items()}}
