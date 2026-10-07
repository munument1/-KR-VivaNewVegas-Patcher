"""Prepare MO2 profile text inside Output; never write into the instance."""
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
        raise RuntimeError('MO2를 종료한 다음 설치해주세요. 실행 중에는 프로필 변경이 저장되지 않을 수 있습니다.')


def profile_snapshot(installation):
    paths = [installation.root / 'ModOrganizer.ini',
             *(installation.profile_dir / name for name in PROFILE_FILES)]
    return {str(path): path.read_bytes() if path.exists() else None for path in paths}


def _text(raw, encoding):
    return (raw or b'').decode(encoding).splitlines()


def _encode(lines, raw, encoding):
    newline = '\r\n' if raw and b'\r\n' in raw else '\n'
    codec = encoding if encoding != 'utf-8-sig' or raw and raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
    return (newline.join(lines) + newline).encode(codec)


def profile_updates(installation, report, snapshot):
    fonts = report.get('fonts', {})
    required = set(report.get('assets', {}).get('mods_requiring_activation', []))
    required.update(report.get('runtime_mods', {}).get('mods_requiring_activation', []))
    priority = []
    if any(row['output_path'].startswith(f'mods/{OVERLAY}/') for row in report['files']):
        priority.append(OVERLAY)
    if fonts.get('mod') and (fonts.get('requires_activation') or fonts.get('requires_priority_check')):
        priority.append(fonts['mod'])
    required.update(priority)
    for mod in required:
        if '/' in vnvkr.virtual_path(mod):
            raise ValueError('Invalid activation mod')
    path = installation.profile_dir / 'modlist.txt'
    raw = snapshot[str(path)]
    lines = _text(raw, 'utf-8-sig')
    top = {mod.casefold() for mod in priority}
    needed = {mod.casefold(): mod for mod in required}
    kept, present = [], set()
    for line in lines:
        if line[:1] in {'+', '-'}:
            key = line[1:].casefold()
            if key in top:
                continue
            if key in needed:
                if key in present:
                    continue
                line = '+' + line[1:]
                present.add(key)
        kept.append(line)
    new = ['+' + mod for mod in sorted(required) if mod.casefold() not in present and mod.casefold() not in top]
    # MO2 stores highest priority first. Existing unrelated mods keep their order.
    lines = ['+' + mod for mod in reversed(priority)] + new + kept
    changes = {path: _encode(lines, raw, 'utf-8-sig')}
    plugins = report.get('runtime_mods', {}).get('plugins_requiring_activation', [])
    for plugin in plugins:
        if '/' in vnvkr.virtual_path(plugin) or Path(plugin).suffix.casefold() not in {'.esp', '.esm'}:
            raise ValueError('Invalid activation plugin')
    for name, encoding in [('plugins.txt', 'cp1252'), ('loadorder.txt', 'utf-8-sig')]:
        path = installation.profile_dir / name
        raw = snapshot[str(path)]
        lines = _text(raw, encoding)
        if name == 'loadorder.txt' and not any(line and not line.startswith('#') for line in lines):
            lines = list(installation.active)
        present = {line.strip().casefold() for line in lines if not line.lstrip().startswith('#')}
        for plugin in plugins:
            if plugin.casefold() not in present:
                if Path(plugin).suffix.casefold() == '.esm':
                    position = next((i for i, line in enumerate(lines) if line.lower().endswith('.esp')), len(lines))
                    lines.insert(position, plugin)
                else:
                    lines.append(plugin)
                present.add(plugin.casefold())
        changes[path] = _encode(lines, raw, encoding)
    return changes, sorted(required), plugins



def prepare_profiles(installation, stage, report, snapshot):
    if profile_snapshot(installation) != snapshot:
        raise ValueError('MO2 프로필 또는 경로 설정이 변경되었습니다. 다시 생성해주세요.')
    changes, mods, plugins = profile_updates(installation, report, snapshot)
    files = []
    for original, raw in changes.items():
        relative = f'profiles/{installation.profile}/{original.name}'
        target = vnvkr.contained(stage, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files.append({'output_path': relative, 'destination': str(original),
                      'output_sha256': vnvkr.sha256(target)})
    instructions = (
        'MO2를 종료한 상태에서 아래 파일을 복사해 덮어쓰세요. 패처는 MO2나 게임 파일을 직접 변경하지 않습니다.\n'
        '복사 전 기존 모드 파일과 선택한 프로필 폴더를 백업하세요.\n\n'
        f'Output/mods 안의 모드 폴더들 → {installation.mods}\n'
        f'Output/profiles/{installation.profile} 안의 3개 텍스트 파일 → {installation.profile_dir}\n'
    )
    if (stage / 'overwrite').exists():
        instructions += f'Output/overwrite 안의 파일들 → {installation.overwrite} (기존 Overwrite 제공 파일이 있는 경우만)\n'
    instructions += (
        '\nMods 파일을 먼저 병합하고 프로필 텍스트를 마지막에 덮어쓰세요. 복사가 끝나면 MO2를 다시 여세요.\n'
        '모드나 프로필 설정을 바꿨다면 오래된 Output의 프로필 파일을 복사하지 말고 새 Output을 생성하세요.\n'
        '출력에 없는 기존 파일을 삭제하지 마세요. Output은 생성물이며 실제 설치 완료를 의미하지 않습니다.\n'
    )
    (stage / 'INSTALL.txt').write_text(instructions, encoding='utf-8-sig')
    report.update(install_state='manual_copy_required', profile_files=files,
                  prepared_mods=mods, prepared_plugins=plugins,
                  copy_instructions=str(Path(report['output']) / 'INSTALL.txt'))
