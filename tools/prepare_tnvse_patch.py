"""Reuse verified release resources and add the narrowly patched tNVSE DLL."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import zipfile

from PyInstaller.archive.readers import CArchiveReader
import vnvkr

UPSTREAM_COMMIT = '7355fd3f2e008dc252ac484f9b376c153e584455'
BASE_RELEASE_SHA256 = 'e5826584fcc7ae7d4df7f7a58b612baca04fb1374a9d0b4582776fb96d27f247'


def prepare(release: Path, source: Path, output: Path):
    if vnvkr.sha256(release) != BASE_RELEASE_SHA256:
        raise ValueError('The base release does not match v1.0.6.1')
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    reader = CArchiveReader(str(release))
    for name in reader.toc:
        relative = name.replace('\\', '/')
        if relative.startswith(('TranslationData/', 'Backend/')):
            target = vnvkr.contained(output, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(reader.extract(name))
    data = output / 'TranslationData'
    catalog = vnvkr.read_json(data / 'catalog.json')
    assets = data / 'font-payloads'
    assets.mkdir(exist_ok=True)
    dll = source / 'out/kr-ui-fix/bin/Release/tnvse.dll'
    if not dll.is_file():
        raise FileNotFoundError(dll)
    shutil.copyfile(dll, assets / 'tnvse.dll')
    # Deliver the actual patched source, including pinned FreeType/msdfgen
    # submodules, with the DLL. Exclude generated outputs and NuGet binaries.
    archive = assets / 'tNVSE-71-KR-UI-source.zip'
    excluded = {'.git', '.vs', 'out', 'packages', '__pycache__'}
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipout:
        for path in sorted(source.rglob('*')):
            rel = path.relative_to(source)
            if path.is_file() and not any(part in excluded for part in rel.parts):
                zipout.write(path, 'tNVSE/' + rel.as_posix())
        for name in ('build_tnvse_patch.ps1', 'tnvse/ui-replacement-encoding.patch'):
            path = Path(__file__).parent / name
            zipout.write(path, 'build/' + name)
    license_path = assets / 'tNVSE-GPL-3.0.txt'
    shutil.copyfile(source / 'LICENSE', license_path)
    notice = assets / 'tNVSE-KR-UI-fix.txt'
    notice.write_text(
        'tNVSE by Artaud / TIAIMM: https://github.com/TIAIMM/tNVSE\n'
        f'Upstream source commit: {UPSTREAM_COMMIT}\n'
        'License: GPL-3.0; included in tNVSE-GPL-3.0.txt.\n'
        'Modified for the VNV Korean patcher on 2026-10-07.\n'
        'Change: normalize UTF-8 GMST/UI replacement text through the existing\n'
        'tNVSE encoding converter before layout, including rich-text replacements.\n'
        'No shaders, UI assets, font defaults, plugin identity or hooks changed.\n'
        'Install upstream tNVSE 71 normally; the Korean Fonts mod overrides only its DLL.\n'
        'Exact modified source and pinned submodules: tNVSE-71-KR-UI-source.zip.\n'
        'Build with MSVC Win32, CMake and restored packages.config dependencies.\n'
        'This build requires in-game validation; offline tests do not prove game compatibility.\n',
        encoding='utf-8')

    def item(path, destination):
        return {'path': destination, 'payload': path.relative_to(data).as_posix(),
                'payload_sha256': vnvkr.sha256(path)}

    catalog['font_bundle']['runtime_patch'] = {
        **item(assets / 'tnvse.dll', 'NVSE/plugins/tnvse.dll'),
        'upstream_commit': UPSTREAM_COMMIT,
        'source_archive': 'NVSE/plugins/fonts/licenses/tNVSE-71-KR-UI-source.zip',
        'notices': [item(path, 'NVSE/plugins/fonts/licenses/' + path.name)
                    for path in (license_path, notice, archive)],
    }
    vnvkr.write_json(data / 'catalog.json', catalog)
    print(f'tNVSE DLL SHA256: {vnvkr.sha256(assets / "tnvse.dll")}')
    print(f'Corresponding source archive: {archive.stat().st_size} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.release, args.source, args.output)
