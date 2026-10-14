"""Add a complete Korean glyph fallback to the packaged tNVSE font XML.

The preinstalled NanumSquareEB cmap maps rare syllables to empty outlines.
The paired DLL fix skips those outlines and searches the following face.
Apply this to a fresh, already-extracted TranslationData catalog only.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import vnvkr

EXPECTED_FONT_IDS = {"1", "2", "3", "6", "7", "42"}
FALLBACK_PATH = "Data/NVSE/plugins/fonts/Pretendard-Bold.ttf"


def basename(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1].casefold()


def add_fallback(catalog_dir: Path) -> None:
    catalog_path = catalog_dir / "catalog.json"
    catalog = vnvkr.read_json(catalog_path)
    bundle = catalog["font_bundle"]
    assets = {item["path"].replace("\\", "/").casefold() for item in bundle["assets"]}
    fallback_asset = FALLBACK_PATH.removeprefix("Data/").casefold()
    if fallback_asset not in assets:
        raise RuntimeError(f"Missing bundled fallback font: {fallback_asset}")

    xml_path = catalog_dir / bundle["xml"]["payload"]
    tree = ET.parse(xml_path)
    root = tree.getroot()
    modified = set()

    for font in root.findall("./fonts/font"):
        doublebyte = font.find("doubleByte")
        # When the double-byte role owns its face list, modify that list.
        # Otherwise, edit the inherited face chain on the enclosing font.
        face = doublebyte.find("face") if doublebyte is not None else None
        group = doublebyte if face is not None else font
        face = group.find("face")
        if face is None or basename(face.get("path", "")) != "nanumsquareeb.ttf":
            continue

        slot = font.get("id")
        if slot not in EXPECTED_FONT_IDS:
            raise RuntimeError(f"Unexpected NanumSquare font slot: {slot}")
        if not any(basename(x.get("path", "")) == "pretendard-bold.ttf"
                   for x in group.findall("fallback")):
            ET.SubElement(group, "fallback", {"path": FALLBACK_PATH, "index": "0"})
        modified.add(slot)

    if modified != EXPECTED_FONT_IDS:
        raise RuntimeError(f"Expected font slots {EXPECTED_FONT_IDS}, found {modified}")
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    bundle["xml"]["payload_sha256"] = hashlib.sha256(xml_path.read_bytes()).hexdigest()
    vnvkr.write_json(catalog_path, catalog)
    print("Added Pretendard-Bold fallback to tNVSE font slots:", sorted(modified))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    add_fallback(parser.parse_args().catalog)
