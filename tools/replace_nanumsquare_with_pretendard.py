"""Change only the six NanumSquare tNVSE face selections in a release catalog.

No tNVSE DLL replacement, backend rebuild, SST rewrite, or font download.
Work on an extracted catalog from the official v1.0.7.3 patcher release.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import vnvkr

EXPECTED_FONT_IDS = {"1", "2", "3", "6", "7", "42"}
OLD_FONT = "nanumsquareeb.ttf"
NEW_FONT = "Pretendard-Bold.ttf"
NEW_FACE_PATH = "Data/NVSE/plugins/fonts/" + NEW_FONT


def filename(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1].casefold()


def replace_font(catalog_root: Path) -> None:
    catalog_path = catalog_root / "catalog.json"
    catalog = vnvkr.read_json(catalog_path)
    bundle = catalog["font_bundle"]
    asset_paths = {entry["path"].replace("\\", "/").casefold()
                   for entry in bundle["assets"]}
    if NEW_FACE_PATH.removeprefix("Data/").casefold() not in asset_paths:
        raise ValueError("The existing release does not bundle Pretendard-Bold.ttf")

    xml_item = bundle["xml"]
    xml_file = vnvkr.contained(catalog_root, xml_item["payload"])
    if vnvkr.sha256(xml_file) != xml_item["payload_sha256"]:
        raise ValueError("Unmodified font XML does not match catalog SHA256")

    tree = ET.parse(xml_file, parser=ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True)))
    root = tree.getroot()
    if root.tag != "tNVSE":
        raise ValueError("Invalid font config root")
    found: set[str] = set()
    for font in root.findall("./fonts/font"):
        slot = font.get("id")
        for face in font.iter("face"):
            if filename(face.get("path", "")) != OLD_FONT:
                continue
            if slot not in EXPECTED_FONT_IDS or slot in found:
                raise ValueError(f"Unexpected or duplicate NanumSquare slot: {slot}")
            face.set("path", NEW_FACE_PATH)
            found.add(slot)

    if found != EXPECTED_FONT_IDS:
        raise ValueError(f"Changed slots {sorted(found)}; expected {sorted(EXPECTED_FONT_IDS)}")
    if any(filename(face.get("path", "")) == OLD_FONT for face in root.iter("face")):
        raise ValueError("A NanumSquare primary face remains in the config")
    tree.write(xml_file, encoding="utf-8", xml_declaration=True)
    xml_item["payload_sha256"] = vnvkr.sha256(xml_file)
    vnvkr.write_json(catalog_path, catalog)

    # Re-parse and check all unchanged release payloads against their hashes.
    updated = vnvkr.read_json(catalog_path)
    for key in ("ini", "xml", "runtime_patch"):
        item = updated["font_bundle"].get(key)
        if item:
            path = vnvkr.contained(catalog_root, item["payload"])
            if vnvkr.sha256(path) != item["payload_sha256"]:
                raise ValueError(f"Integrity failure: {key}")
    print("Replaced NanumSquareEB with Pretendard Bold: slots", sorted(found))
    print("Original tNVSE DLL remains byte-for-byte unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    replace_font(parser.parse_args().catalog)
