"""Official xEditLib record merging in an isolated copied Data directory."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import vnvkr

# New Vegas also uses extender format specifiers, not just C printf tokens.
FORMAT = re.compile(r'%%|(?<!\d)%(?:\d+\$)?[-+#0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[a-zA-Z]|</?(?:font|br|img|div|p)(?:\s[^<>]*)?/?>', re.IGNORECASE)


def validate_mapping(row):
    from collections import Counter
    if not all(isinstance(row.get(k), str) for k in ('owner', 'id', 'signature', 'field', 'path', 'source', 'dest')):
        raise ValueError('Invalid plugin translation mapping')
    if not re.fullmatch(r'[0-9a-f]{6}', row['id']) or not re.fullmatch(r'[A-Z0-9_]{4}', row['signature']):
        raise ValueError('Invalid plugin record identity')
    if '\ufffd' in row['source'] or '\ufffd' in row['dest']:
        raise ValueError('Unresolved plugin text encoding')
    if Counter(FORMAT.findall(row['source'])) != Counter(FORMAT.findall(row['dest'])):
        raise ValueError('Plugin translation changes protected tokens')


def runtime(codepage=65001):
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    packaged = root / 'Backend'
    node = (packaged / ('node-1252.exe' if codepage == 1252 else 'node.exe') if packaged.is_dir()
            else root / ('.tools/yesman-node-1252/node.exe' if codepage == 1252 else '.tools/yesman-node-utf8/node.exe'))
    modules = packaged / 'node_modules' if packaged.is_dir() else root / '.tools/YesMan-AI/node_modules'
    adapter = packaged / 'yesman_text.cjs' if packaged.is_dir() else root / 'tools/yesman_text.cjs'
    for required in (node, adapter, modules / 'xeditlib/XEditLib.dll'):
        if not required.is_file():
            raise FileNotFoundError(f'New Vegas record backend is missing: {required}')
    return node, adapter, modules


def run_adapter(request, job, phase):
    node, adapter, modules = runtime(request.get('readCodepage', 65001))
    path = job / f'{phase}.request.json'
    vnvkr.write_json(path, request)
    env = os.environ.copy()
    env['VNVKR_NODE_MODULES'] = str(modules)
    result = subprocess.run([str(node), str(adapter), str(path)], capture_output=True,
                            env=env, timeout=1800, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (job / f'{phase}.log').write_bytes(result.stdout + result.stderr)
    if result.returncode:
        message = result.stderr.decode('utf-8', errors='replace').replace('\x00', '')[-3000:]
        raise ValueError(f'New Vegas record {phase} failed: {message}')
    return vnvkr.read_json(Path(request['output']))


def merge_plugins(installation, entries, catalog, job, source_overrides=None):
    """Load current plugins, set matched display text, then verify a fresh load.

    No plugin binary parser/writer is implemented here. The official native
    library owns every plugin read and write, and receives only copied inputs.
    """
    runtime()  # Check availability before copying a large installation.
    job.mkdir()
    game = job / 'Game'
    data = game / 'Data'
    data.mkdir(parents=True)
    source_overrides = source_overrides or {}
    overrides = {name.casefold(): source for name, source in source_overrides.items()}
    plugins = list(installation.active)
    plugins.extend(name for name in source_overrides if name.casefold() not in {p.casefold() for p in plugins})
    original_hashes = {}
    for plugin in plugins:
        source = overrides.get(plugin.casefold()) or installation.source(plugin)
        original_hashes[source] = vnvkr.sha256(source)
        shutil.copyfile(source, data / plugin)
    maps = {}
    for entry in entries:
        for row in entry['mappings']:
            validate_mapping(row)
        maps[entry['path']] = entry['mappings']
    translated = job / 'Translated'
    request = {'game': str(game), 'plugins': plugins, 'targets': list(maps),
               'fields': catalog['plugin_fields'], 'mappings': maps, 'mode': 'apply',
               'outDir': str(translated), 'output': str(job / 'apply.json')}
    # Independent CP1252 snapshot checks the original legacy strings as well as
    # structures. UTF-8 alone collapses malformed/legacy bytes to U+FFFD.
    snapshot_request = {k: request[k] for k in ('game', 'plugins', 'targets', 'fields')}
    snapshot_request.update(mode='snapshot', readCodepage=1252, output=str(job / 'legacy-before.json'))
    legacy = run_adapter(snapshot_request, job, 'legacy-before')
    legacy_sources = {file['plugin']: file['rows'] for file in legacy['files']}
    request['legacySources'] = legacy_sources
    applied = run_adapter(request, job, 'apply')
    expected, changes = {}, {}
    stats = {}
    for file in applied['files']:
        plugin = file['plugin']
        expected[plugin] = file['beforeHashes']
        changes[plugin] = file['changed']
        stats[plugin] = {'translated': len(file['changed']), 'unmatched': len(file['missing']),
                         'unmatched_entries': file['missing'], 'records_verified': len(file['beforeHashes'])}
        shutil.copyfile(translated / plugin, data / plugin)
    request.update(mode='verify', expected=expected, changes=changes,
                   expectedHeaders={file['plugin']: file['headerHash'] for file in applied['files']},
                   includeRows=False, output=str(job / 'verify.json'))
    request.pop('outDir')
    verified = run_adapter(request, job, 'verify')
    by_name = {file['plugin']: file for file in verified['files']}
    for file in applied['files']:
        if file['masters'] != by_name[file['plugin']]['masters']:
            raise ValueError('Master list changed during translation')
    request.update(mode='verifyLegacy', readCodepage=1252, output=str(job / 'legacy-verify.json'),
                   expected={file['plugin']: file['beforeHashes'] for file in legacy['files']},
                   expectedHeaders={file['plugin']: file['headerHash'] for file in legacy['files']})
    run_adapter(request, job, 'legacy-verify')
    for values in stats.values():
        values['verification'] = 'UTF8_and_CP1252_fresh_readback; header_records_and_unmodified_text'
    for source, before in original_hashes.items():
        if vnvkr.sha256(source) != before:
            raise ValueError(f'Source changed during generation: {source}')
    return translated, stats
