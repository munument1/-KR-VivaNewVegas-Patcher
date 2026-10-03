"""Populate a PyInstaller onedir build with release data and native backends."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import vnvkr


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dist',type=Path,required=True)
    p.add_argument('--catalog',type=Path,required=True)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if not (a.dist/'VNVKoreanPatcher.exe').is_file():
        raise FileNotFoundError(a.dist/'VNVKoreanPatcher.exe')
    data=a.dist/'TranslationData'; backend=a.dist/'Backend'
    for path in (data,backend):
        if path.exists(): shutil.rmtree(path)
    shutil.copytree(a.catalog,data)
    backend.mkdir()
    copies=[
        (root/'.tools/yesman-node-utf8/node.exe',backend/'node.exe'),
        (root/'.tools/yesman-node-1252/node.exe',backend/'node-1252.exe'),
        (root/'.tools/xdelta3-3.2.0-windows-x86_64/xdelta3.exe',backend/'xdelta3.exe'),
        (root/'tools/yesman_text.cjs',backend/'yesman_text.cjs'),
        (root/'.tools/yesman-node-utf8/NODE_LICENSE.txt',backend/'NODE_LICENSE.txt'),
        (root/'tools/xdelta_source.json',backend/'xdelta_source.json')]
    for source,target in copies:
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source,target)
    shutil.copytree(root/'.tools/YesMan-AI/node_modules',backend/'node_modules')
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
           'backend_mb':round(sum(p.stat().st_size for p in backend.rglob('*') if p.is_file())/1024/1024,1)})


if __name__=='__main__':
    main()
