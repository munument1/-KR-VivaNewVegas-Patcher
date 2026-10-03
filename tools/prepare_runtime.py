"""Prepare an uninstalled tNVSE Korean candidate from user-supplied ZIPs."""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vnvkr import contained, sha256, virtual_path, write_json


def patch_ini(text: str) -> str:
    changes = {("multibyte", "benablemultibytefonthook"): "1",
               ("multibyte", "uiencoding"): "4", ("multibyte", "butf8"): "1"}
    seen, section, lines = set(), "", []
    for line in text.splitlines(keepends=True):
        header = re.match(r"\s*\[([^\]]+)\]", line)
        if header:
            section = header[1].casefold()
        item = re.match(r"(\s*([^;#=]+?)\s*=\s*)([^\r\n]*)(\r?\n)?$", line)
        if item and (section, item[2].strip().casefold()) in changes:
            key = section, item[2].strip().casefold()
            seen.add(key)
            line = item[1] + changes[key] + (item[4] or "")
        lines.append(line)
    if seen != changes.keys():
        raise ValueError("Supplied tNVSE config lacks expected Korean settings")
    result = "".join(lines)
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(result)
    if config.getint("FreeTypeFont", "bEnableFreeTypeFontRendering") != 0:
        raise ValueError("Bitmap-font candidate requires FreeType rendering disabled")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives", required=True, type=Path)
    parser.add_argument("--fonts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    output, report = args.output.resolve(), args.report.resolve()
    staging_root = Path(__file__).resolve().parents[1] / "staging"
    if output.parent != staging_root.resolve():
        raise ValueError("Uninstalled candidates must be new direct children of this project's staging directory")
    if output.exists() or report.exists():
        raise FileExistsError("Use new candidate and report paths")
    if report.is_relative_to(output) or output.is_relative_to(report):
        raise ValueError("Keep the preparation report outside the runtime mod")
    for source in (args.archives.resolve(), args.fonts.resolve()):
        if output.is_relative_to(source) or source.is_relative_to(output) or report.is_relative_to(source):
            raise ValueError("Output/report overlaps supplied sources")
    rows, archives, omitted, contents = [], [], [], {}
    for archive in sorted(args.archives.glob("*.zip")):
        archive_hash = sha256(archive)
        archives.append({"name": archive.name, "sha256": archive_hash, "size": archive.stat().st_size})
        with zipfile.ZipFile(archive) as opened:
            for info in opened.infolist():
                if info.is_dir():
                    continue
                relative = virtual_path(info.filename.replace("\\", "/"))
                key = relative.casefold()
                if key.endswith(".pdb") or key == "nvse/plugins/tnvse/save_display_names.dat":
                    omitted.append(relative)
                    continue
                raw = opened.read(info)  # CRC is checked by ZipFile.
                if key in contents:
                    raise ValueError(f"Overlapping archive file requires review: {relative}")
                contents[key] = (relative, raw)
                rows.append({"archive": archive.name, "path": relative, "size": len(raw),
                             "source_sha256": hashlib.sha256(raw).hexdigest()})
        if sha256(archive) != archive_hash:
            raise ValueError("Archive changed during preparation")
    required = {"nvse/plugins/tnvse.dll", "nvse/plugins/tnvse.ini",
                "nvse/plugins/tnvse_fonts.xml", "nvse/plugins/tnvse_dictionary.xml"}
    if not required <= contents.keys():
        raise ValueError("Incomplete runtime + default-config ZIP set")
    original_ini = contents["nvse/plugins/tnvse.ini"][1].decode("utf-8-sig")
    candidate = patch_ini(original_ini).encode("utf-8")
    contents["nvse/plugins/tnvse.ini"] = (contents["nvse/plugins/tnvse.ini"][0], candidate)
    font_readme = (args.fonts / "Read ME.txt").read_text(encoding="utf-8-sig")
    slots = []
    for slot, value in re.findall(r"(?im)^sFontFile_(\d+)\s*=\s*([^\r\n]+)", font_readme):
        if 1 <= int(slot) <= 8:
            relative = virtual_path(value.strip().replace("\\", "/"))
            font = contained(args.fonts, relative)
            if not font.is_file() or not font.with_suffix(".Tex").is_file():
                raise ValueError(f"Incomplete font pair: {relative}")
            slots.append((int(slot), relative))
    if {slot for slot, _ in slots} != set(range(1, 9)):
        raise ValueError("Font source must supply complete standard slots 1-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vnvkr-runtime-", dir=output.parent) as temp:
        stage = Path(temp) / "mod"
        stage.mkdir()
        for relative, raw in contents.values():
            target = contained(stage, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            if target.read_bytes() != raw:
                raise ValueError("Runtime write readback mismatch")
        prepared = {"schema_version": 1, "candidate": "tNVSE Korean bitmap-font baseline",
                    "archives": archives, "source_files": rows, "omitted": omitted,
                    "output_files": [{"path": p.relative_to(stage).as_posix(), "sha256": sha256(p)}
                                     for p in sorted(stage.rglob("*")) if p.is_file()],
                    "config_changes": {"Multibyte.bEnableMultibyteFontHook": 1,
                                       "Multibyte.uiEncoding": 4, "Multibyte.bUTF8": 1},
                    "font_slots": dict(slots), "bitmap_fonts_copied": False,
                    "runtime_validation": "not_tested", "game_or_mo2_modified": False,
                    "limitations": ["Uses the supplied K-font bitmap files from a separate mod.",
                                    "Does not enable input, runtime dictionaries or FreeType.",
                                    "Requires actual VNV dependency/version/UI checks before installation."]}
        stage.rename(output)
        write_json(report, prepared)
    fragment = report.with_suffix(".FalloutCustom.fragment.ini")
    with fragment.open("x", encoding="utf-8") as stream:
        stream.write("; Review and merge into the selected MO2 profile only after installation.\n[Fonts]\n")
        for slot, value in sorted(slots):
            stream.write(f"sFontFile_{slot}={value.replace('/', chr(92))}\n")
    print(json.dumps({"output": str(output), "runtime_files": len(contents), "report": str(report),
                      "font_fragment": str(fragment), "omitted": omitted,
                      "runtime_validation": "not_tested"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
