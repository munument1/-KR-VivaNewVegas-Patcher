"""Verify the packaged resource diff and all printable ASCII outline extents."""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from PyInstaller.archive.readers import CArchiveReader

from tools.fix_hacking_font import revised_xml


def resources(exe: Path) -> dict[str, bytes]:
    reader = CArchiveReader(str(exe))
    return {n.replace('\\', '/'): reader.extract(n) for n in reader.toc
            if n.replace('\\', '/').startswith(('TranslationData/', 'Backend/'))}


def verify(base: Path, revised: Path) -> None:
    old, new = resources(base), resources(revised)
    if old.keys() != new.keys():
        raise ValueError('Packaged resource set changed')
    catalog_name = 'TranslationData/catalog.json'
    before, after = [json.loads(r[catalog_name].decode('utf-8-sig')) for r in (old, new)]
    item = after['font_bundle']['xml']
    xml_name = 'TranslationData/' + item['payload']
    changed = {n for n in old if old[n] != new[n]}
    if changed != {catalog_name, xml_name}:
        raise ValueError(f'Unexpected changed resources: {changed}')
    expected = copy.deepcopy(before)
    expected['font_bundle']['xml']['payload_sha256'] = hashlib.sha256(new[xml_name]).hexdigest()
    if after != expected:
        raise ValueError('Unrelated catalog metadata changed')
    expected_xml = ET.fromstring(revised_xml(old[xml_name]))
    root = ET.fromstring(new[xml_name])
    if ET.tostring(root) != ET.tostring(expected_xml):
        raise ValueError('Unexpected XML changes')

    # Match BuildFontLetter's floor/ceil outline bounds at configured size.
    # Include the enabled outline width on both sides. Check EVERY printable
    # ASCII glyph: @ is wider than W in this proportional font.
    slot = root.find('./fonts/font[@id="5"]')
    style = slot.find('singleByte')
    font_asset = next(a for a in after['font_bundle']['assets']
                      if a['path'].lower().endswith('neodunggeunmopro-regular.ttf'))
    with TTFont(io.BytesIO(new['TranslationData/' + font_asset['payload']])) as font:
        glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
        unit_scale = float(style.get('pixelSize')) / font['head'].unitsPerEm
        outline = slot.find('outline')
        effect = float(outline.get('width')) if outline.get('enabled') == '1' else 0
        widest = 0
        for code in range(33, 127):
            pen = BoundsPen(glyphs)
            glyphs[cmap[code]].draw(pen)
            if pen.bounds is None:
                raise ValueError(f'Blank ASCII glyph: {code}')
            x0, y0, x1, y1 = pen.bounds
            sx = unit_scale * float(style.get('scaleX'))
            width = math.ceil(x1 * sx) - math.floor(x0 * sx) + 2 * effect
            height = math.ceil(y1 * unit_scale) - math.floor(y0 * unit_scale) + 2 * effect
            if width > 17 or height > 28:
                raise ValueError(f'Glyph overflows hacking cell: {chr(code)} {width}x{height}')
            widest = max(widest, width)
    print(f'PASS: 94 ASCII outlines fit 17x28 cells; maximum effect width={widest}.')
    print('PASS: only slot 5 singleByte and XML checksum changed; DLL/backend/translations identical.')
    print('In-game rendering, cursor alignment and Korean terminal text still require validation.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('base', type=Path)
    parser.add_argument('revised', type=Path)
    args = parser.parse_args()
    verify(args.base, args.revised)
