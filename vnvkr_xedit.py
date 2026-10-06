"""Native XEditLib translation backend for Viva New Vegas."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import vnvkr

FORMAT = re.compile(
    r'%%|(?<!\d)%(?:\d+\$)?[-+#0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[a-zA-Z]|'
    r'</?(?:font|br|img|div|p)(?:\s[^<>]*)?/?>',
    re.IGNORECASE,
)


def validate_mapping(row):
    from collections import Counter
    if not all(isinstance(row.get(k), str)
               for k in ('owner', 'id', 'signature', 'field', 'path', 'source', 'dest')):
        raise ValueError('Invalid plugin translation mapping')
    if not re.fullmatch(r'[0-9a-f]{6}', row['id'].lower()):
        raise ValueError('Invalid plugin record FormID')
    if not re.fullmatch(r'[A-Z0-9_]{4}', row['signature']):
        raise ValueError('Invalid plugin record signature')
    if '\ufffd' in row['source'] or '\ufffd' in row['dest']:
        raise ValueError('Unresolved plugin text encoding')
    if Counter(FORMAT.findall(row['source'])) != Counter(FORMAT.findall(row['dest'])):
        raise ValueError('Plugin translation changes protected tokens')


def runtime():
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    if getattr(sys, 'frozen', False):
        worker = root / 'VNVKRXEditWorker.exe'
        backend = root / 'Backend'
    else:
        worker = root / '.tools/vnvkr-xedit-worker/VNVKRXEditWorker.exe'
        backend = root / '.tools/xeditlib-native'
    for required in (
        worker,
        backend / 'XEditLib.dll',
        backend / 'FalloutNV.Hardcoded.dat',
        backend / 'icudtl.dat',
    ):
        if not required.is_file():
            raise FileNotFoundError(f'New Vegas record backend is missing: {required}')
    return worker, backend


def _xedit_isolation_args(request, job):
    """Keep xEdit profile/cache/temp/log I/O inside the current patch job."""
    root = job / 'XEditIsolation'
    paths = {name: root / name for name in ('Saves', 'Backups', 'Cache', 'Temp', 'Scripts')}
    for directory in (root, *paths.values()):
        directory.mkdir(parents=True, exist_ok=True)
    plugins_file = root / 'plugins.txt'
    plugins_file.write_text('\n'.join(request.get('plugins', ())) + '\n', encoding='cp1252')
    game = Path(request['game'])
    return [
        f'-D:{game / "Data"}',
        f'-M:{root}{os.sep}',
        f'-I:{root / "Fallout.ini"}',
        f'-CustomIni:{root / "FalloutCustom.ini"}',
        f'-G:{paths["Saves"]}{os.sep}',
        f'-P:{plugins_file}',
        f'-B:{paths["Backups"]}{os.sep}',
        f'-C:{paths["Cache"]}{os.sep}',
        f'-T:{paths["Temp"]}{os.sep}',
        f'-S:{paths["Scripts"]}{os.sep}',
        f'-R:{root / "xelib.log"}',
    ]


def run_worker(request, job, phase):
    worker, backend = runtime()
    path = job / f'{phase}.request.json'
    vnvkr.write_json(path, request)
    env = os.environ.copy()
    env['VNVKR_XEDIT_RUNTIME'] = str(backend)
    command = [str(worker), str(path), *_xedit_isolation_args(request, job)]
    result = subprocess.run(
        command,
        capture_output=True,
        env=env,
        timeout=1800,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    (job / f'{phase}.log').write_bytes(result.stdout + result.stderr)
    if result.returncode:
        message = (result.stderr or result.stdout).decode('utf-8', errors='replace').replace('\x00', '')[-4000:]
        raise ValueError(f'New Vegas record {phase} failed: {message}')
    return vnvkr.read_json(Path(request['output']))


def _session_plugins(installation, entries, source_overrides):
    """Use only the load-order prefix needed by the selected targets."""
    active = list(installation.active)
    if source_overrides:
        plugins = active[:]
        present = {name.casefold() for name in plugins}
        plugins.extend(name for name in source_overrides if name.casefold() not in present)
        return plugins
    targets = {entry['path'].casefold() for entry in entries}
    positions = [index for index, name in enumerate(active) if name.casefold() in targets]
    if len(positions) != len(targets):
        return active
    return active[:max(positions) + 1] if positions else active


def merge_plugins(installation, entries, catalog, job, source_overrides=None,
                  fallback_mappings=None, fallback_targets=None, progress=None):
    """Apply SST text to current MO2 plugins and verify one fresh UTF-8 reload.

    There is deliberately no whole-plugin CP1252 snapshot/reload pass. Direct
    SST mapping is exact; base/DLC fallback is stricter still and requires the
    same owner/FormID/signature/field/path/source before a string is changed.
    """
    runtime()
    def emit(message):
        if progress:
            progress(message)

    job.mkdir()
    game = job / 'Game'
    data = game / 'Data'
    data.mkdir(parents=True)
    source_overrides = source_overrides or {}
    fallback_mappings = fallback_mappings or []
    fallback_targets = set(fallback_targets or ())
    overrides = {name.casefold(): source for name, source in source_overrides.items()}
    plugins = _session_plugins(installation, entries, source_overrides)

    original_hashes = {}
    for plugin in plugins:
        source = overrides.get(plugin.casefold()) or installation.source(plugin)
        original_hashes[source] = vnvkr.sha256(source)
        shutil.copyfile(source, data / plugin)

    maps = {}
    for entry in entries:
        for row in entry.get('mappings', []):
            validate_mapping(row)
        maps[entry['path']] = entry.get('mappings', [])
    for row in fallback_mappings:
        validate_mapping(row)

    translated = job / 'Translated'
    request = {
        'game': str(game),
        'plugins': plugins,
        'targets': list(maps),
        'fields': catalog['plugin_fields'],
        'mappings': maps,
        'fallbackMappings': fallback_mappings,
        'fallbackTargets': sorted(fallback_targets),
        'mode': 'apply',
        'includeRows': False,
        'outDir': str(translated),
        'output': str(job / 'apply.json'),
    }

    emit('플러그인: SST 번역을 적용하고 있습니다.')
    applied = run_worker(request, job, 'apply')

    expected, changes, indexes, stats = {}, {}, {}, {}
    for file in applied['files']:
        plugin = file['plugin']
        expected[plugin] = file['beforeHashes']
        changes[plugin] = file['changed']
        indexes[plugin] = file['recordIndexHash']
        inherited = sum(row.get('mappingOrigin') == 'base_dlc_sst_fallback'
                        for row in file['changed'])
        stats[plugin] = {
            'translated': len(file['changed']),
            'fallback_translated': inherited,
            'direct_sst_translated': len(file['changed']) - inherited,
            'unmatched': len(file['missing']),
            'unmatched_entries': file['missing'],
            'records_verified': len(file['beforeHashes']),
            'records_indexed': file['recordCount'],
            'translation_source': 'xTranslator_SST',
        }
        shutil.copyfile(translated / plugin, data / plugin)

    request.pop('fallbackMappings', None)
    request.pop('fallbackTargets', None)
    request.pop('outDir', None)
    request.update(
        mode='verify',
        expected=expected,
        changes=changes,
        expectedHeaders={file['plugin']: file['headerHash'] for file in applied['files']},
        expectedRecordIndexes=indexes,
        output=str(job / 'verify.json'),
    )

    emit('플러그인: 저장 결과를 한 번 다시 열어 검증하고 있습니다.')
    verified = run_worker(request, job, 'verify')
    by_name = {file['plugin']: file for file in verified['files']}
    for file in applied['files']:
        if file['masters'] != by_name[file['plugin']]['masters']:
            raise ValueError('Master list changed during translation')

    for values in stats.values():
        values['verification'] = (
            'UTF8 fresh readback; master/header/record-index + exact changed-record structure'
        )
    for source, before in original_hashes.items():
        if vnvkr.sha256(source) != before:
            raise ValueError(f'Source changed during generation: {source}')
    return translated, stats
