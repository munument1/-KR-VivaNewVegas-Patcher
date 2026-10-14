"""Inspect shipped VNV Korean fonts for CP949 extension coverage (read-only)."""
from __future__ import annotations

import io
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools.ttLib import TTFont
from PyInstaller.archive.readers import CArchiveReader

SAMPLES = {
    "겍": 0xAC8D,  # CP949 81 A6: extended Hangul, reported missing
    "걕": 0xAC55,  # CP949 81 7A: ASCII-range trail byte
    "괙": 0xAD19,  # CP949 82 45: another extension group
    "게": 0xAC8C,  # CP949 B0 D4: baseline KS X 1001
    "코": 0xCF54,  # CP949 C4 DA: baseline KS X 1001
}


def extract(reader: CArchiveReader, name: str) -> bytes:
    matched = next((key for key in reader.toc
                    if key.replace("\\\\", "/").casefold() == name.casefold()), None)
    if matched is None:
        similar = [key for key in reader.toc if "catalog" in key.casefold() or "font" in key.casefold()]
        raise ValueError(f"missing packaged resource: {name}; similar entries: {similar[:20]}")
    return reader.extract(matched)


def check(release: Path) -> int:
    reader = CArchiveReader(str(release))
    catalog = json.loads(extract(reader, "TranslationData/catalog.json").decode("utf-8-sig"))
    bundle = catalog["font_bundle"]
    xml_path = bundle["xml"]["payload"]
    root = ET.fromstring(extract(reader, "TranslationData/" + xml_path))
    assets = {item["path"].replace("\\", "/").casefold(): item for item in bundle["assets"]}
    missing = []
    cached = {}
    print("Shipped release:", release.name, flush=True)
    print("Installed fonts:", len(assets), flush=True)
    for label, cp in SAMPLES.items():
        print(f"  {label} U+{cp:04X} cp949={label.encode('cp949').hex(' ')}", flush=True)

    for font in root.findall("./fonts/font"):
        slot = font.attrib["id"]
        # Prefer class-specific face lists, which override direct children.
        group = font.find("doubleByte")
        if group is None or not any(ch.tag in ("face", "fallback") for ch in group):
            group = font
        paths = [ch.attrib["path"].replace("\\", "/").removeprefix("Data/").casefold()
                 for ch in group if ch.tag in ("face", "fallback")]
        coverage = {label: False for label in SAMPLES}
        for path in paths:
            if path not in assets:
                print(f"FONT SLOT {slot}: asset not in bundle: {path}", flush=True)
                missing.append(f"font {slot} missing asset {path}")
                continue
            item = assets[path]
            payload_name = "TranslationData/" + item["payload"]
            index = next((int(ch.attrib.get("index", "0")) for ch in group
                          if ch.tag in ("face", "fallback")
                          and ch.attrib.get("path", "").replace("\\", "/").removeprefix("Data/").casefold() == path), 0)
            key = (payload_name, index)
            if key not in cached:
                f = TTFont(io.BytesIO(extract(reader, payload_name)), fontNumber=index, lazy=False)
                try:
                    cached[key] = set().union(*(set(table.cmap) for table in f["cmap"].tables if table.isUnicode()))
                finally:
                    f.close()
            found = [label for label, cp in SAMPLES.items() if cp in cached[key]]
            print(f"FONT SLOT {slot} {path} face={index}: {','.join(found) or 'none'}", flush=True)
            for label in found:
                coverage[label] = True
        missing_labels = [label for label, found in coverage.items() if not found]
        print(f"FONT SLOT {slot} missing: {','.join(missing_labels) or '(none)'}", flush=True)
        if missing_labels:
            missing.append(f"slot {slot}: {','.join(missing_labels)}")

    if missing:
        print("FAILED coverage:", "; ".join(missing), flush=True)
        return 1
    print("PASS: all tested Korean codepoints have a glyph in every font slot.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(check(Path(sys.argv[1])))
