"""Recupera el logo previamente aprobado de la historia local, sin recrearlo."""
from copy import deepcopy
import io
from pathlib import Path
import subprocess
import zipfile
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
LOGO = ROOT / 'assets/institutionworks.jpeg'
LAYOUT = ROOT / 'assets/institutionworks_logo.xml'


def preparar():
    if LOGO.exists() and LAYOUT.exists():
        return
    historical = subprocess.run(['git', 'show', 'pipeline-v2:templates/seguridad_medicion.docx'],
                                cwd=ROOT, check=True, capture_output=True).stdout
    with zipfile.ZipFile(io.BytesIO(historical)) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
        p = next(p for p in root.iter(W + 'p') if p.find('.//' + W + 'drawing') is not None)
        blip = p.find('.//' + A + 'blip')
        rid = blip.get(R + 'embed')
        rels = ET.fromstring(archive.read('word/_rels/document.xml.rels'))
        target = next(r.get('Target') for r in rels if r.get('Id') == rid)
        LOGO.write_bytes(archive.read('word/' + target))
        blip.set(R + 'embed', 'rIdInstitutionworksLogo')
        LAYOUT.write_bytes(ET.tostring(p, encoding='UTF-8', xml_declaration=True))


def insertar(files):
    preparar()
    files['word/media/institutionworks.jpeg'] = LOGO.read_bytes()
    rels = ET.fromstring(files['word/_rels/document.xml.rels'])
    ET.SubElement(rels, REL + 'Relationship', {'Id': 'rIdInstitutionworksLogo',
        'Type': R[1:-1] + '/image', 'Target': 'media/institutionworks.jpeg'})
    files['word/_rels/document.xml.rels'] = ET.tostring(rels, encoding='UTF-8', xml_declaration=True)
    types = ET.fromstring(files['[Content_Types].xml'])
    if not any(n.get('Extension') == 'jpeg' for n in types):
        ET.SubElement(types, CT + 'Default', {'Extension': 'jpeg', 'ContentType': 'image/jpeg'})
    files['[Content_Types].xml'] = ET.tostring(types, encoding='UTF-8', xml_declaration=True)
    return deepcopy(ET.fromstring(LAYOUT.read_bytes()))
