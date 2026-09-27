"""Contrato documental independiente de la metodología de calificación."""
import json
from pathlib import Path
from documentos import sha256

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'config/contrato_documental.json'


def cargar_contrato(verificar=True):
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    if verificar:
        if contract.get('version') != '2.1' or set(contract['plantillas']) != {'medicion'}:
            raise ValueError('Se requiere el contrato 2.1 del único documento de medición de seguridad.')
        template = contract['plantillas']['medicion']
        if sha256(ROOT / template['origen']) != template['origen_sha256']:
            raise ValueError(f"Cambió el machote original: {template['origen']}. Revisar y regenerar la base de seguridad.")
        for entry in [template, contract['diccionario'], contract['reglas'], contract['metodologia'],
                      contract['formato'], contract['redaccion'], *contract.get('tipografias', [])]:
            if sha256(ROOT / entry['archivo']) != entry['sha256']:
                raise ValueError(f"Cambió el contrato documental: {entry['archivo']}. Regenerar y revisar la migración.")
    return contract


def huellas():
    contract = cargar_contrato()
    return {'version': contract['version'], 'contrato_documental_sha256': sha256(CONTRACT),
            'plantilla_sha256': contract['plantillas']['medicion']['sha256'],
            'plantilla_original_sha256': contract['plantillas']['medicion']['origen_sha256'],
            'plantillas_sha256': {key: entry['sha256'] for key, entry in contract['plantillas'].items()},
            'diccionario_sha256': contract['diccionario']['sha256'],
            'reglas_sha256': contract['reglas']['sha256'],
            'metodologia_sha256': contract['metodologia']['sha256'],
            'formato_sha256': contract['formato']['sha256'],
            'redaccion_sha256': contract['redaccion']['sha256']}
