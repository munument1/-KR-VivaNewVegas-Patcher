"""Populate a PyInstaller onedir build with release data and native backends."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import vnvkr

MAX_PACKAGED_DELTA_BYTES = 16 * 1024 * 1024


def strip_oversized_verified_deltas(data: Path, limit: int = MAX_PACKAGED_DELTA_BYTES):
    """Keep record mappings but omit deltas that make the release needlessly huge."""
    catalog_path = data / 'catalog.json'
    catalog = vnvkr.read_json(catalog_path)
    oversized = []
    for entry in catalog.get('files', []):
        spec = entry.get('verified_delta')
        if entry.get('kind') != 'plugin-records' or not spec:
            continue
        payload = vnvkr.contained(data, spec['payload'])
        if not payload.is_file():
            raise FileNotFoundError(payload)
        if payload.stat().st_size <= limit:
            continue
        if not entry.get('mappings'):
            raise ValueError(f"Cannot drop delta without record mappings: {entry['path']}")
        oversized.append((entry, payload, payload.stat().st_size))

    if not oversized:
        return []

    removed = []
    for entry, payload, size in oversized:
        removed.append({'path': entry['path'], 'payload': entry['verified_delta']['payload'], 'bytes': size})
        del entry['verified_delta']
    for payload in {payload for _, payload, _ in oversized}:
        payload.unlink()
    catalog['verified_delta_files'] = sum(
        bool(entry.get('verified_delta'))
        for entry in catalog.get('files', [])
        if entry.get('kind') == 'plugin-records')
    vnvkr.write_json(catalog_path, catalog)
    return removed


def prune_koffi_platforms(koffi: Path):
    """The packaged Node runtimes are Windows x64, so other Koffi binaries are dead weight."""
    binaries = koffi / 'build' / 'koffi'
    required = binaries / 'win32_x64' / 'koffi.node'
    if not required.is_file():
        raise FileNotFoundError(required)
    removed = []
    for child in binaries.iterdir():
        if child.is_dir() and child.name != 'win32_x64':
            removed.append(child.name)
            shutil.rmtree(child)
    return removed


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dist',type=Path,required=True)
    p.add_argument('--catalog',type=Path,required=True)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if not (a.dist/'VNVKoreanPatcher.exe').is_file():
        raise FileNotFoundError(a.dist/'VNVKoreanPatcher.exe')
    catalog = vnvkr.read_json(a.catalog / 'catalog.json')
    native = [entry for entry in catalog['files'] if entry.get('kind') == 'plugin-records']
    verified = [entry for entry in native if entry.get('verified_delta')]
    missing = [entry for entry in native if not entry.get('verified_delta')]
    # A plugin may intentionally ship without an xdelta fast path as long as it
    # retains record mappings for the native xEditLib merge fallback.
    invalid_missing = [entry['path'] for entry in missing if not entry.get('mappings')]
    if invalid_missing:
        raise ValueError(f'Release catalog has no delta or record mappings: {invalid_missing}')
    for entry in verified:
        spec = entry['verified_delta']
        payload = vnvkr.contained(a.catalog, spec['payload'])
        if not payload.is_file() or vnvkr.sha256(payload) != spec['payload_sha256']:
            raise ValueError(f'Verified delta payload is missing/corrupt: {entry["path"]}')

    data=a.dist/'TranslationData'; backend=a.dist/'Backend'
    for path in (data,backend):
        if path.exists(): shutil.rmtree(path)
    shutil.copytree(a.catalog,data)
    packaged_catalog = vnvkr.read_json(data / 'catalog.json')
    packaged_catalog['verified_delta_files'] = sum(
        bool(entry.get('verified_delta'))
        for entry in packaged_catalog.get('files', [])
        if entry.get('kind') == 'plugin-records')
    vnvkr.write_json(data / 'catalog.json', packaged_catalog)
    stripped_deltas = strip_oversized_verified_deltas(data)
    backend.mkdir()
    copies=[
        (root/'.tools/yesman-node-utf8/node.exe',backend/'node.exe'),
        (root/'.tools/yesman-node-1252/node.exe',backend/'node-1252.exe'),
        (root/'.tools/xdelta3-3.2.0-windows-x86_64/xdelta3.exe',backend/'xdelta3.exe'),
        (root/'.tools/xdelta3-3.2.0-windows-x86_64/README.md',backend/'xdelta-README.md'),
        (root/'tools/yesman_text.cjs',backend/'yesman_text.cjs'),
        (root/'.tools/yesman-node-utf8/NODE_LICENSE.txt',backend/'NODE_LICENSE.txt'),
        (root/'tools/xdelta_source.json',backend/'xdelta_source.json')]
    for source,target in copies:
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source,target)
    # The runtime adapter only imports xeditlib and koffi.  Copying the whole
    # YesMan-AI node_modules tree bloats the release with tools the patcher never uses.
    modules = root/'.tools/YesMan-AI/node_modules'
    for name in ('xeditlib', 'koffi'):
        source = modules/name
        if not source.is_dir():
            raise FileNotFoundError(source)
        shutil.copytree(source, backend/'node_modules'/name)
    removed_koffi_platforms = prune_koffi_platforms(backend/'node_modules'/'koffi')
    readme=a.dist/'README.md'
    readme.write_text(
        '# Viva New Vegas 한국어 패쳐\n\n'
        'VNVKoreanPatcher.exe를 실행하고 ModOrganizer.ini가 있는 VNV 폴더를 선택한 뒤 Output을 생성합니다.\n'
        '생성된 Output\\mods 내용을 VNV MO2 폴더에 복사하세요. 원본 게임/VNV 파일은 패쳐가 직접 수정하지 않습니다.\n\n'
        '- 정확히 검증된 VNV 원본: xdelta 빠른 경로 사용\n'
        '- 업데이트된 플러그인: 레코드 단위 YesMan/xEditLib 병합 경로 사용\n'
        '- tNVSE 71 이상 필요. tNVSE DLL은 배포물에 포함하지 않음\n'
        '- KR-RADIO 호환 ESP는 아직 별도 작업 중\n', encoding='utf-8-sig')
    files=[p for p in a.dist.rglob('*') if p.is_file()]
    size=sum(p.stat().st_size for p in files)
    print({'files':len(files),'size_mb':round(size/1024/1024,1),
           'translation_data_mb':round(sum(p.stat().st_size for p in data.rglob('*') if p.is_file())/1024/1024,1),
           'backend_mb':round(sum(p.stat().st_size for p in backend.rglob('*') if p.is_file())/1024/1024,1),
           'oversized_deltas_omitted': stripped_deltas,
           'koffi_platforms_removed': removed_koffi_platforms})


if __name__=='__main__':
    main()
