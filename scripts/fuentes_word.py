"""Incrusta las fuentes Archivo oficiales redistribuibles bajo SIL OFL."""
import hashlib
from pathlib import Path
from uuid import UUID
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
FONTS = [('Archivo', 'Archivo-Regular.ttf', 'embedRegular'),
         ('Archivo Medium', 'Archivo-Medium.ttf', 'embedRegular'),
         ('Archivo Light', 'Archivo-Light.ttf', 'embedRegular'),
         ('Archivo Light', 'Archivo-LightItalic.ttf', 'embedItalic'),
         ('Archivo', 'Archivo-Bold.ttf', 'embedBold'),
         ('Archivo Medium', 'Archivo-Bold.ttf', 'embedBold')]


def incrustar(files):
    fonts = ET.fromstring(files['word/fontTable.xml'])
    relname = 'word/_rels/fontTable.xml.rels'
    relations = ET.fromstring(files[relname]) if relname in files else ET.Element(REL + 'Relationships', nsmap={None: REL[1:-1]})
    types = ET.fromstring(files['[Content_Types].xml'])
    if not any(n.get('Extension') == 'odttf' for n in types):
        ET.SubElement(types, CT + 'Default', {'Extension': 'odttf', 'ContentType': 'application/vnd.openxmlformats-officedocument.obfuscatedFont'})
    for index, (family, filename, variant) in enumerate(FONTS, 1):
        raw = bytearray((ROOT / 'assets/fonts' / filename).read_bytes())
        key = UUID(bytes=hashlib.sha256(raw).digest()[:16])
        # OOXML ofusca los primeros 32 bytes con los 16 bytes del GUID en reversa.
        mask = key.bytes[::-1]
        for i in range(32):
            raw[i] ^= mask[i % 16]
        rid = f'rIdArchivo{index}'
        part = f'fonts/archivo_{index}.odttf'
        files['word/' + part] = bytes(raw)
        for old in list(relations):
            if old.get('Id') == rid:
                relations.remove(old)
        ET.SubElement(relations, REL + 'Relationship', {'Id': rid, 'Type': R[1:-1] + '/font', 'Target': part})
        font = next((n for n in fonts if n.get(W + 'name') == family), None)
        if font is None:
            font = ET.SubElement(fonts, W + 'font', {W + 'name': family})
        for old in font.findall(W + variant):
            font.remove(old)
        ET.SubElement(font, W + variant, {R + 'id': rid, W + 'fontKey': '{' + str(key).upper() + '}', W + 'subsetted': '0'})
    files['word/fontTable.xml'] = ET.tostring(fonts, encoding='UTF-8', xml_declaration=True)
    files[relname] = ET.tostring(relations, encoding='UTF-8', xml_declaration=True)
    files['[Content_Types].xml'] = ET.tostring(types, encoding='UTF-8', xml_declaration=True)
