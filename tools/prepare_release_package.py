"""Populate a PyInstaller build with SST data and the native XEdit backend."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import vnvkr


def validate_catalog(catalog):
    native = [entry for entry in catalog.get('files', []) if entry.get('kind') == 'plugin-records']
    invalid = [
        entry['path'] for entry in native
        if not entry.get('mappings') and not entry.get('fallback_only')
    ]
    if invalid:
        raise ValueError(f'Plugin has neither direct SST nor fallback policy: {invalid}')
    return native


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--worker', type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if not (args.dist / 'VNVKoreanPatcher.exe').is_file():
        raise FileNotFoundError(args.dist / 'VNVKoreanPatcher.exe')
    if not args.worker.is_file():
        raise FileNotFoundError(args.worker)

    catalog = vnvkr.read_json(args.catalog / 'catalog.json')
    validate_catalog(catalog)

    data = args.dist / 'TranslationData'
    backend = args.dist / 'Backend'
    for path in (data, backend):
        if path.exists():
            shutil.rmtree(path)
    shutil.copytree(args.catalog, data)
    backend.mkdir()

    runtime = root / '.tools' / 'xeditlib-native'
    copies = [
        (runtime / 'XEditLib.dll', backend / 'XEditLib.dll'),
        (runtime / 'FalloutNV.Hardcoded.dat', backend / 'FalloutNV.Hardcoded.dat'),
        (runtime / 'icudtl.dat', backend / 'icudtl.dat'),
        (runtime / 'LICENSE', backend / 'XEditLib-LICENSE.txt'),
        (args.worker, args.dist / 'VNVKRXEditWorker.exe'),
    ]
    for source, target in copies:
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, target)

    readme = args.dist / 'README.md'
    readme.write_text(
        '# Viva New Vegas 한국어 패쳐\n\n'
        'VNVKoreanPatcher.exe를 실행하고 ModOrganizer.ini가 있는 VNV MO2 인스턴스 폴더를 선택합니다.\n'
        '패쳐는 MO2/VFS의 실제 winner ESP/ESM을 읽습니다. Data는 최하위 provider입니다.\n'
        'FalloutNV.esm과 주요 DLC ESM은 Fixed ESMs를 사용하고, Classic/Mercenary/Tribal/CaravanPack은 stock VNV처럼 Data 파일을 source로 허용하되 번역본은 Fixed ESMs Output에 배치합니다.\n\n'
        '- 플러그인 번역 원본: xTranslator SST\n'
        '- 전용 SST가 없는 플러그인: 본편+DLC SST의 정확히 일치하는 override 문자열만 fallback 적용\n'
        '- MCM JSON 및 Translations 텍스트: 현재 MO2 파일에 검증된 번역만 병합\n'
        '- Node.js / Koffi / YesMan 런타임 없음\n'
        '- 플러그인은 UTF-8 적용 후 저장본을 한 번 재로드해 검증\n'
        '- 원본 MO2 파일은 직접 수정하지 않으며 Output만 생성\n',
        encoding='utf-8-sig',
    )

    files = [path for path in args.dist.rglob('*') if path.is_file()]
    print({
        'files': len(files),
        'size_mb': round(sum(path.stat().st_size for path in files) / 1024 / 1024, 1),
        'translation_data_mb': round(
            sum(path.stat().st_size for path in data.rglob('*') if path.is_file()) / 1024 / 1024, 1),
        'backend_mb': round(
            sum(path.stat().st_size for path in backend.rglob('*') if path.is_file()) / 1024 / 1024, 1),
        'node_runtime': False,
        'xdelta_runtime': False,
        'plugin_backend': 'Python ctypes + XEditLib',
    })


if __name__ == '__main__':
    main()
