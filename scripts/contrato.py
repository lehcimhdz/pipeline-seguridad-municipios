"""Contrato documental independiente de la metodología de calificación."""
import json
from pathlib import Path
from documentos import sha256

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'config/contrato_documental.json'


def cargar_contrato(verificar=True):
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    if verificar:
        if (contract.get('version') != '2.3' or contract.get('producto') != 'estudio_seguridad'
                or set(contract['plantillas']) != {'medicion'}):
            raise ValueError('Se requiere el contrato 2.3 del único documento Estudio Seguridad.')
        template = contract['plantillas']['medicion']
        if sha256(ROOT / template['origen']) != template['origen_sha256']:
            raise ValueError(f"Cambió el machote original: {template['origen']}. Revisar y regenerar la base de seguridad.")
        source = contract['fuente_formato']
        if (source['archivo'], source['sha256']) != (template['origen'], template['origen_sha256']):
            raise ValueError('La fuente de formato no coincide con la procedencia de la base operativa.')
        for entry in [template, source, contract['guia'], contract['benchmark'], contract['diccionario'],
                      contract['reglas'], contract['metodologia'], contract['formato'],
                      contract['redaccion'], contract['normalizaciones'], contract['ponderacion'],
                      contract['definiciones'], contract['textos_narrativos'], *contract.get('tipografias', [])]:
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
            'benchmark_sha256': contract['benchmark']['sha256'],
            'guia_sha256': contract['guia']['sha256'],
            'normalizaciones_sha256': contract['normalizaciones']['sha256'],
            'formato_sha256': contract['formato']['sha256'],
            'redaccion_sha256': contract['redaccion']['sha256'],
            **{key + '_sha256': contract[key]['sha256'] for key in ('ponderacion', 'definiciones', 'textos_narrativos')}}
