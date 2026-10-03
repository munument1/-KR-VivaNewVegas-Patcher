from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ui-esp', type=Path, required=True)
    parser.add_argument('--radio-root', type=Path, required=True)
    parser.add_argument('--radio-dll', type=Path, required=True)
    args = parser.parse_args()

    if args.output.exists():
        raise FileExistsError(args.output)
    shutil.copytree(args.base, args.output)

    payload_root = args.output / 'runtime-payloads'
    specs = [
        {
            'mod': 'VNV Korean UI Strings',
            'plugins': ['VNVKR UI Strings.esp'],
            'sources': [('VNVKR UI Strings.esp', args.ui_esp)],
        },
        {
            'mod': 'VNV Korean Radio Captions',
            'plugins': [],
            'sources': [
                ('NVSE/Plugins/MojaveRadioCaptions.dll', args.radio_dll),
                ('NVSE/Plugins/MojaveRadioCaptions.ini', args.radio_root / 'NVSE/Plugins/MojaveRadioCaptions.ini'),
                ('menus/prefabs/MojaveRadioCaptions/MojaveRadioCaptions.xml', args.radio_root / 'menus/prefabs/MojaveRadioCaptions/MojaveRadioCaptions.xml'),
                ('uio/public/MojaveRadioCaptions.txt', args.radio_root / 'uio/public/MojaveRadioCaptions.txt'),
                ('LICENSE', args.radio_root.parent / 'LICENSE'),
                ('THIRD_PARTY_NOTICES.md', args.radio_root.parent / 'THIRD_PARTY_NOTICES.md'),
            ],
        },
    ]

    runtime_mods = []
    for spec in specs:
        files = []
        for relative, source in spec['sources']:
            if not source.is_file():
                raise FileNotFoundError(source)
            payload = Path('runtime-payloads') / spec['mod'] / Path(relative)
            target = args.output / payload
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            files.append({'path': Path(relative).as_posix(),
                          'payload': payload.as_posix(),
                          'payload_sha256': sha256(target)})
        runtime_mods.append({'mod': spec['mod'], 'plugins': spec['plugins'], 'files': files})

    catalog_path = args.output / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    catalog['runtime_mods'] = runtime_mods
    catalog['package_status'] = 'release_candidate_20261004'
    catalog['radio_caption_backend'] = {
        'name': 'MojaveRadioCaptions',
        'encoding_fix': 'preserve_valid_utf8_then_cp1252_fallback',
    }
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'catalog': str(args.output), 'runtime_mods': len(runtime_mods),
                      'runtime_files': sum(len(m['files']) for m in runtime_mods)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
