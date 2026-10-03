"""Hash the supplied Korean source tree and check font references (no plugin parsing)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Audit output must be separate from supplied sources")
    rows = []
    for path in sorted(source.rglob("*")):
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            rows.append({"path": path.relative_to(source).as_posix(), "size": path.stat().st_size,
                         "sha256": digest})
    readme = source / "K-font/K-font/Read ME.txt"
    content = readme.read_text(encoding="utf-8-sig")
    font_root = readme.parent
    slots = []
    for slot, value in re.findall(r"(?im)^sFontFile_(\d+)\s*=\s*([^\r\n]+)", content):
        value = value.strip()
        relative = Path(value.replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe font path in source Read ME")
        font = (font_root / relative).resolve()
        if not font.is_relative_to(font_root.resolve()):
            raise ValueError("Font reference escapes font source root")
        texture = font.with_suffix(".Tex")
        slots.append({"slot": int(slot), "data_path": value.replace("\\", "/"),
                      "font_exists": font.is_file(), "texture_exists": texture.is_file()})
    manifest = {"schema_version": 1, "source_root": str(source), "checked_on": "2026-10-03",
                "source_use": "user_supplied_translation_reference", "files": rows,
                "file_count": len(rows), "bytes": sum(row["size"] for row in rows),
                "font_slots_from_source_readme": slots,
                "findings": {"runtime_dll_in_loose_files": any(row["path"].lower().endswith("tnvse.dll") for row in rows),
                             "tnvse_ini_in_loose_files": any(row["path"].lower().endswith("tnvse.ini") for row in rows),
                             "missing_referenced_fonts": [slot["data_path"] for slot in slots if not slot["font_exists"]]},
                "limitations": ["Does not interpret plugin records, their encoding, or translation coverage.",
                                "Archive contents are inventoried separately with 7-Zip.",
                                "Read ME is source evidence; no game or profile INI was changed."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({key: manifest[key] for key in ("file_count", "bytes", "findings")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
