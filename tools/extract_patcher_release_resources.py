"""Extract only trusted resource trees from a verified PyInstaller VNV patcher EXE."""
from __future__ import annotations
import argparse
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader
import vnvkr


def extract_resources(exe: Path, target: Path) -> None:
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    reader = CArchiveReader(str(exe))
    copied = 0
    for entry in reader.toc:
        relative = entry.replace(chr(92), "/")
        if not relative.startswith(("TranslationData/", "Backend/")):
            continue
        path = vnvkr.contained(target, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(reader.extract(entry))
        copied += 1
    if copied < 10 or not (target / "TranslationData/catalog.json").is_file():
        raise ValueError("Missing resources in upstream release EXE")
    if not (target / "Backend/XEditLib.dll").is_file():
        raise ValueError("Missing native XEditLib backend")
    print(f"Extracted {copied} resource files from {exe.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    extract_resources(args.exe, args.output)
