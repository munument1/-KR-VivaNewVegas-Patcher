"""Install verified Output into configured MO2 storage with durable backups."""
import csv
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

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


def _atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.vnvkr-', dir=target.parent)
    os.close(fd)
    try:
        shutil.copyfile(source, name)
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def _rollback(backup, records):
    for record in reversed(records):
        target = Path(record['target'])
        if record['backup'] is None:
            target.unlink(missing_ok=True)
        else:
            _atomic_copy(backup / record['backup'], target)


def restore_backup(backup):
    require_mo2_closed()
    backup = Path(backup).resolve()
    manifest = vnvkr.read_json(backup / 'install.json')
    if manifest['state'] not in {'installed', 'installing'}:
        raise ValueError('This backup is already restored')
    for row in manifest['files']:
        if row['backup'] is not None:
            source = vnvkr.contained(backup, row['backup'])
            if vnvkr.sha256(source) != row['before_sha256']:
                raise ValueError('Backup integrity mismatch')
        path = Path(row['target'])
        current = vnvkr.sha256(path) if path.is_file() else None
        if current not in {row['after_sha256'], row['before_sha256']}:
            raise ValueError(f'File changed since installation: {path}')
    _rollback(backup, manifest['files'])
    manifest['state'] = 'restored'
    vnvkr.write_json(backup / 'install.json', manifest)


def _install_output(installation, output, report, snapshot, progress=None):
    require_mo2_closed()
    if profile_snapshot(installation) != snapshot:
        raise ValueError('MO2 프로필 또는 경로 설정이 변경되었습니다. 다시 설치해주세요.')
    data = installation.data.resolve()
    for storage in (installation.mods, installation.overwrite, installation.profile_dir):
        if storage.is_relative_to(data) or data.is_relative_to(storage):
            raise ValueError('MO2 storage overlaps game Data')
    output = Path(output).resolve()
    updates, mods, plugins = profile_updates(installation, report, snapshot)
    planned, deletes, seen = [], [], set()
    for row in report['files']:
        relative = vnvkr.virtual_path(row['output_path'])
        parts = relative.split('/')
        if parts[0] == 'mods' and len(parts) >= 3:
            target = vnvkr.contained(installation.mods, '/'.join(parts[1:]))
        elif parts[0] == 'overwrite' and len(parts) >= 2 and Path(relative).suffix.lower() not in {'.esp', '.esm'}:
            target = vnvkr.contained(installation.overwrite, '/'.join(parts[1:]))
        else:
            raise ValueError(f'Output is not an MO2 destination: {relative}')
        if target.is_relative_to(installation.data.resolve()):
            raise ValueError('MO2 storage overlaps game Data')
        source = vnvkr.contained(output, relative)
        if vnvkr.sha256(source) != row['output_sha256']:
            raise ValueError('Output integrity mismatch')
        if row.get('source_path'):
            original = Path(row['source_path'])
            if vnvkr.sha256(original) != row['source_sha256']:
                raise ValueError(f'Source changed after generation: {original}')
            if (original.resolve().is_relative_to(installation.overwrite)
                    and original.suffix.lower() in {'.esp', '.esm'}):
                deletes.append(original)
        if str(target).casefold() in seen:
            raise ValueError('Duplicate install destination')
        seen.add(str(target).casefold())
        planned.append((source, target, row['output_sha256']))
    # Backups beside Output remain outside the mod virtual filesystem.
    backup = output.with_name(output.name + '.backup')
    backup.mkdir(exist_ok=False)
    records = []
    for path, raw in updates.items():
        source = backup / 'profile-new' / path.name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(raw)
        planned.append((source, path, vnvkr.sha256(source)))
    for i, (source, target, after) in enumerate([*planned, *((None, path, None) for path in deletes)]):
        if target.exists() and not target.is_file():
            raise ValueError(f'Install destination is not a file: {target}')
        before = vnvkr.sha256(target) if target.is_file() else None
        saved = f'original/{i}' if before else None
        if saved:
            stored = backup / saved
            stored.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, stored)
            if vnvkr.sha256(stored) != before:
                raise ValueError('Backup readback failed')
        records.append({'target': str(target), 'backup': saved,
                        'before_sha256': before, 'after_sha256': after})
    manifest = {'state': 'prepared', 'profile': installation.profile,
                'created_utc': datetime.now(timezone.utc).isoformat(), 'files': records}
    vnvkr.write_json(backup / 'install.json', manifest)
    require_mo2_closed()
    if profile_snapshot(installation) != snapshot:
        raise ValueError('Profile changed before installation')
    for record in records:
        target = Path(record['target'])
        if (vnvkr.sha256(target) if target.is_file() else None) != record['before_sha256']:
            raise ValueError(f'Install target changed: {target}')
    manifest['state'] = 'installing'
    vnvkr.write_json(backup / 'install.json', manifest)
    applied = []
    try:
        if progress:
            progress('번역 파일을 MO2에 설치하고 선택한 프로필을 활성화합니다.')
        for i, (source, target, digest) in enumerate(planned):
            applied.append(records[i])
            _atomic_copy(source, target)
            if vnvkr.sha256(target) != digest:
                raise ValueError('Installed file readback failed')
        for i, path in enumerate(deletes, len(planned)):
            applied.append(records[i])
            path.unlink()
    except Exception:
        _rollback(backup, applied)
        manifest['state'] = 'rolled_back'
        vnvkr.write_json(backup / 'install.json', manifest)
        raise
    manifest['state'] = 'installed'
    vnvkr.write_json(backup / 'install.json', manifest)
    report.update(install_state='installed', backup=str(backup),
                  activated_mods=mods, activated_plugins=plugins)
    vnvkr.write_json(Path(report['report_json']), report)
    with Path(report['report_text']).open('a', encoding='utf-8') as stream:
        stream.write(f'\nMO2 설치 완료 · 프로필: {installation.profile}\n백업: {backup}\n')
    return report


def install_output(installation, output, report, snapshot, progress=None):
    # OS locks release automatically even after a crash. Never unlink a locked
    # path: another installer may already hold a handle to that same inode.
    with (installation.root / '.vnvkr-install.lock').open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('다른 패쳐가 설치 중입니다. 먼저 실행 중인 패쳐를 종료해주세요.')
        return _install_output(installation, output, report, snapshot, progress)
