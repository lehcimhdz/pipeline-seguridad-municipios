"""Aplica el manual editorial con tamaños e interlineados explícitos."""
import json
from pathlib import Path
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
FORMATO = ROOT / 'config/formato_editorial.json'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def configurar(p, perfil='medicion', rol='cuerpo', inicial=True):
    config = json.loads(FORMATO.read_text(encoding='utf-8'))
    font, size, line, align = config[perfil][rol]
    props = p.find(W + 'pPr')
    if props is None:
        props = ET.Element(W + 'pPr')
        p.insert(0, props)
    for key in ('spacing', 'ind', 'jc', 'tabs', 'numPr', 'contextualSpacing'):
        for node in props.findall(W + key):
            props.remove(node)
    ET.SubElement(props, W + 'spacing', {W + 'before': '0', W + 'after': '0',
                                        W + 'line': str(line * 20), W + 'lineRule': 'atLeast' if line < size else 'exact'})
    ET.SubElement(props, W + 'jc', {W + 'val': align})
    ET.SubElement(props, W + 'ind', {W + 'left': '0', W + 'right': '0',
                                   W + 'firstLine': '283' if not inicial and rol in ('cuerpo', 'bibliografia') else '0'})
    if rol in ('capitulo', 'subcapitulo') and props.find(W + 'keepNext') is None:
        ET.SubElement(props, W + 'keepNext')
    for run in p.iter(W + 'r'):
        rpr = run.find(W + 'rPr')
        if rpr is None:
            rpr = ET.Element(W + 'rPr')
            run.insert(0, rpr)
        for key in ('rFonts', 'sz', 'szCs', 'caps'):
            for node in rpr.findall(W + key):
                rpr.remove(node)
        ET.SubElement(rpr, W + 'rFonts', {W + key: font for key in ('ascii', 'hAnsi', 'eastAsia', 'cs')})
        ET.SubElement(rpr, W + 'sz', {W + 'val': str(size * 2)})
        ET.SubElement(rpr, W + 'szCs', {W + 'val': str(size * 2)})
        if rol in ('capitulo', 'calificacion'):
            ET.SubElement(rpr, W + 'caps')
        order = ['rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike', 'dstrike',
                 'outline', 'shadow', 'emboss', 'imprint', 'noProof', 'snapToGrid', 'vanish', 'webHidden',
                 'color', 'spacing', 'w', 'kern', 'position', 'sz', 'szCs', 'highlight', 'u', 'effect',
                 'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs', 'em', 'lang', 'eastAsianLayout', 'specVanish']
        rpr[:] = sorted(rpr, key=lambda n: order.index(ET.QName(n).localname) if ET.QName(n).localname in order else len(order))
    order = ['pStyle', 'keepNext', 'keepLines', 'pageBreakBefore', 'framePr', 'widowControl', 'numPr',
             'suppressLineNumbers', 'pBdr', 'shd', 'tabs', 'suppressAutoHyphens', 'kinsoku', 'wordWrap',
             'overflowPunct', 'topLinePunct', 'autoSpaceDE', 'autoSpaceDN', 'bidi', 'adjustRightInd',
             'snapToGrid', 'spacing', 'ind', 'contextualSpacing', 'mirrorIndents', 'suppressOverlap',
             'jc', 'textDirection', 'textAlignment', 'textboxTightWrap', 'outlineLvl', 'divId', 'cnfStyle', 'rPr', 'sectPr']
    props[:] = sorted(props, key=lambda n: order.index(ET.QName(n).localname) if ET.QName(n).localname in order else len(order))
    return p
