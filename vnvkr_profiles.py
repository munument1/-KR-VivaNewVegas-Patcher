"""Read MO2 profiles and write manual installation instructions only."""
import csv
import io
import os
from pathlib import Path
import subprocess
import vnvkr

PROFILE_FILES = ('modlist.txt', 'plugins.txt', 'loadorder.txt')
OVERLAY = 'VNV Korean Translations'


def require_mo2_closed():
    if os.name != 'nt':
        return
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True,
                            text=True, errors='replace', timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('MO2 실행 상태를 확인할 수 없습니다. 다시 시도해주세요.')
    if any(row and row[0].casefold() == 'modorganizer.exe'
           for row in csv.reader(io.StringIO(result.stdout))):
        raise RuntimeError('MO2를 종료한 다음 생성해주세요.')


def profile_snapshot(installation):
    paths = [installation.root / 'ModOrganizer.ini',
             *(installation.profile_dir / name for name in PROFILE_FILES)]
    return {str(path): path.read_bytes() if path.exists() else None for path in paths}


def manual_activation(report):
    mods = set(report.get('assets', {}).get('mods_requiring_activation', []))
    runtime = report.get('runtime_mods', {})
    mods.update(runtime.get('mods_requiring_activation', []))
    fonts = report.get('fonts', {})
    if fonts.get('mod'):
        mods.add(fonts['mod'])
    if any(row['output_path'].startswith(f'mods/{OVERLAY}/') for row in report['files']):
        mods.add(OVERLAY)
    for mod in mods:
        if '/' in vnvkr.virtual_path(mod):
            raise ValueError('Invalid activation mod')
    plugins = sorted(set(runtime.get('plugins_requiring_activation', [])))
    for plugin in plugins:
        if '/' in vnvkr.virtual_path(plugin) or Path(plugin).suffix.casefold() not in {'.esp', '.esm'}:
            raise ValueError('Invalid activation plugin')
    return sorted(mods), plugins


def prepare_instructions(installation, stage, report, snapshot):
    if profile_snapshot(installation) != snapshot:
        raise ValueError('MO2 프로필 또는 경로 설정이 변경되었습니다. 다시 생성해주세요.')
    mods, plugins = manual_activation(report)
    instructions = (
        'MO2를 종료하고 기존 모드 파일을 백업한 뒤 아래 경로로 복사해 병합하세요.\n'
        '패쳐는 MO2와 게임 원본을 직접 변경하지 않습니다.\n'
        '프로필 파일은 생성하거나 변경하지 않습니다. 이전 Output의 profiles 폴더도 복사하지 마세요.\n\n'
        f'Output/mods 안의 모드 폴더들 → {installation.mods}\n'
    )
    if (stage / 'overwrite').exists():
        instructions += f'Output/overwrite 안의 파일들 → {installation.overwrite}\n'
    instructions += '\n복사 후 MO2에서 다음 한국어 모드의 활성화 상태를 직접 확인하세요:\n'
    instructions += ''.join(f'- {name}\n' for name in mods) or '- 새로 활성화할 모드 없음\n'
    if report.get('fonts', {}).get('mod'):
        instructions += f'폰트 모드 "{report["fonts"]["mod"]}"는 원본 tNVSE보다 높은 MO2 우선순위에 두세요.\n'
    if plugins:
        instructions += '\nMO2 오른쪽 플러그인 목록에서 활성화 확인:\n'
        instructions += ''.join(f'- {name}\n' for name in plugins)
    instructions += (
        '\n다른 모드·플러그인의 활성화 상태와 순서는 사용자가 유지합니다. 전체 ESP를 일괄 활성화하지 마세요.\n'
        '모드팩 업데이트나 모드 변경 후에는 이전 Output을 재사용하지 말고 새로 생성하세요.\n'
        '출력에 없는 기존 파일·프로필·사용자 설정·세이브는 삭제하지 마세요.\n'
        'Output 생성은 실제 설치 완료를 의미하지 않습니다.\n'
    )
    (stage / 'INSTALL.txt').write_text(instructions, encoding='utf-8-sig')
    report.update(install_state='manual_copy_required', profile_files=[],
                  manual_activation_mods=mods, manual_activation_plugins=plugins,
                  copy_instructions=str(Path(report['output']) / 'INSTALL.txt'))
