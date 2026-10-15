"""Align terminal ASCII with the hacking menu's 17-unit cells (tNVSE 71).

Apply to resources extracted from v1.0.7.4. The existing runtime implements
fixedWidth in both glyph metrics and geometry; no DLL patch is necessary.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import vnvkr

OLD_STYLE = {'pixelSize': '22', 'tracking': '-0.5', 'scaleX': '1'}
NEW_STYLE = {'pixelSize': '28', 'tracking': '0', 'scaleX': '0.8', 'fixedWidth': '17'}


def revised_xml(raw: bytes) -> bytes:
    root = ET.fromstring(raw, parser=ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True)))
    slots = root.findall('./fonts/font[@id="5"]/singleByte')
    if root.tag != 'tNVSE' or len(slots) != 1:
        raise ValueError('Expected exactly one terminal singleByte style')
    style = slots[0]
    face = style.find('face')
    if face is None or not face.get('path', '').lower().endswith('neodunggeunmopro-regular.ttf'):
        raise ValueError('Unexpected terminal font face')
    if any(style.get(k) != v for k, v in OLD_STYLE.items()) or style.get('fixedWidth'):
        raise ValueError('Expected unmodified v1.0.7.4 terminal style')
    style.attrib.update(NEW_STYLE)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def apply(catalog_root: Path) -> None:
    catalog_path = catalog_root / 'catalog.json'
    catalog = vnvkr.read_json(catalog_path)
    item = catalog['font_bundle']['xml']
    path = vnvkr.contained(catalog_root, item['payload'])
    if vnvkr.sha256(path) != item['payload_sha256']:
        raise ValueError('Font XML checksum mismatch')
    path.write_bytes(revised_xml(path.read_bytes()))
    item['payload_sha256'] = vnvkr.sha256(path)
    vnvkr.write_json(catalog_path, catalog)
    print('Terminal ASCII: size=28, scaleX=0.8, fixedWidth=17, tracking=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('catalog', type=Path)
    apply(parser.parse_args().catalog)
