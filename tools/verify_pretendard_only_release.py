"""Confirm font-only patcher release diff and real glyph outlines (not cmap only)."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from PyInstaller.archive.readers import CArchiveReader

EXPECTED_IDS = {"1", "2", "3", "6", "7", "42"}
SAMPLES = ("겍", "걕", "괙", "게", "코")


def entries(reader):
    return {name.replace(chr(92), "/"): name for name in reader.toc
            if name.replace(chr(92), "/").startswith(("TranslationData/", "Backend/"))}


def get(reader, mapping, name):
    return reader.extract(mapping[name])


def verify(base: Path, revised: Path) -> None:
    sys.stdout.reconfigure(encoding='utf-8')
    base_reader, new_reader = CArchiveReader(str(base)), CArchiveReader(str(revised))
    old, new = entries(base_reader), entries(new_reader)
    if set(old) != set(new):
        raise RuntimeError(f"Added: {set(new)-set(old)}; removed: {set(old)-set(new)}")
    raw_catalog = get(base_reader, old, "TranslationData/catalog.json")
    catalog = json.loads(raw_catalog.decode("utf-8-sig"))
    xml_name = "TranslationData/" + catalog["font_bundle"]["xml"]["payload"]
    approved = {"TranslationData/catalog.json", xml_name}
    changed = set()
    for name in old:
        before = hashlib.sha256(get(base_reader, old, name)).digest()
        after = hashlib.sha256(get(new_reader, new, name)).digest()
        if before != after:
            changed.add(name)
    if changed != approved:
        raise RuntimeError(f"Unexpected resource changes: {changed ^ approved}")

    old_xml = ET.fromstring(get(base_reader, old, xml_name))
    new_xml = ET.fromstring(get(new_reader, new, xml_name))
    found = set()
    for before in old_xml.findall("./fonts/font"):
        slot = before.get("id")
        after = next(x for x in new_xml.findall("./fonts/font") if x.get("id") == slot)
        orig_faces = before.findall(".//face")
        new_faces = after.findall(".//face")
        if len(orig_faces) != len(new_faces):
            raise RuntimeError(f"Face count changed in {slot}")
        for a, b in zip(orig_faces, new_faces):
            old_path, new_path = a.get("path", ""), b.get("path", "")
            if old_path != new_path:
                if not (slot in EXPECTED_IDS
                        and old_path.lower().endswith("nanumsquareeb.ttf")
                        and new_path.lower().endswith("pretendard-bold.ttf")):
                    raise RuntimeError(f"Unexpected font swap slot={slot}: {old_path} -> {new_path}")
                found.add(slot)
    if found != EXPECTED_IDS:
        raise RuntimeError(f"Incorrect swapped font slots {found}")

    patched_catalog = json.loads(get(new_reader, new, "TranslationData/catalog.json").decode("utf-8-sig"))
    assets = patched_catalog["font_bundle"]["assets"]
    font_asset = next(item for item in assets
                      if item["path"].lower().endswith("pretendard-bold.ttf"))
    payload = get(new_reader, new, "TranslationData/" + font_asset["payload"])
    f = TTFont(io.BytesIO(payload))
    try:
        cmap = f.getBestCmap() or {}
        glyph_set = f.getGlyphSet()
        for char in SAMPLES:
            glyph_name = cmap.get(ord(char))
            if not glyph_name:
                raise RuntimeError(f"No glyph mapping for {char}")
            pen = BoundsPen(glyph_set)
            glyph_set[glyph_name].draw(pen)
            advance = f["hmtx"].metrics[glyph_name][0]
            if pen.bounds is None or advance <= 0:
                raise RuntimeError(f"Blank glyph in Pretendard: {char}")
            print(f"Verified {char}: bounds={pen.bounds}, advance={advance}")
    finally:
        f.close()
    print("PASS: only catalog metadata + font XML changed; original DLL/backend/SST retained.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("original", type=Path)
    p.add_argument("modified", type=Path)
    args = p.parse_args()
    verify(args.original, args.modified)
