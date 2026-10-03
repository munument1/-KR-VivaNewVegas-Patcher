"""Build a manual-copy MO2 Output tree without changing the installation.

Loose translations and native record mappings merge into today's source.
Legacy plugin payloads remain supported as version-pinned copies.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile

import vnvkr
import vnvkr_yesman
import vnvkr_fonts
from tools.loose_translation import TOKEN, decode, json_values

SCHEMA = 1


def stable_context(obj, pointer):
    """Use setting bindings when present; otherwise MCM's persistent object ID."""
    current, bound = obj, None
    for depth, part in enumerate(pointer[:-1]):
        current = current[part]
        if isinstance(current, dict) and isinstance(current.get('vars'), list):
            refs = [{k: value[k] for k in ('configINI', 'form', 'numVar', 'strVar') if k in value}
                    for value in current['vars'] if isinstance(value, dict)]
            if refs and any(refs):
                bound = (refs, pointer[depth + 1:])
    identity = ['binding', *bound] if bound else ['pointer', pointer]
    return json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def ini_rows(text):
    section = ''
    for index, line in enumerate(text.splitlines(keepends=True)):
        body = line.rstrip('\r\n')
        stripped = body.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            section = stripped
        if not stripped or stripped.startswith((';', '#', '[')) or '=' not in body:
            continue
        lhs, rhs = body.split('=', 1)
        value = rhs.strip()
        quoted = len(value) >= 2 and value.startswith('"') and value.endswith('"')
        source = value[1:-1] if quoted else value
        if source:
            yield {'line': index, 'section': section, 'key': lhs.strip(), 'source': source}


def check_pair(source, dest):
    if not isinstance(dest, str) or not dest or '\n' in dest or '\r' in dest:
        raise ValueError('Invalid translation text')
    if Counter(TOKEN.findall(source)) != Counter(TOKEN.findall(dest)):
        raise ValueError('Translation changes protected tokens')
    import re
    prefix = re.match(r'#\d+\|', source)
    if prefix and not dest.startswith(prefix.group()):
        raise ValueError('Translation moves message prefix')


def make_catalog(workspace, work_dir, output, plugin_maps=None, plugin_fields=None):
    """Package text mappings and user-completed plugins, not proprietary originals."""
    if output.exists():
        raise FileExistsError(output)
    work = vnvkr.read_json(work_dir / 'work.json')
    translations = vnvkr.read_json(work_dir / 'translations.json')
    baseline = vnvkr.read_json(workspace / 'source_manifest.json')
    base_plugins = {row['data_path'].casefold(): row for row in baseline['files']
                    if row['category'] == '01_Plugins'}
    files, payloads, rejected = [], [], []
    native = vnvkr.read_json(plugin_maps) if plugin_maps else None
    if native and not plugin_fields:
        raise ValueError('Native mappings require the verified plugin display schema')
    for info in work['files']:
        original = workspace / info['path']
        if vnvkr.sha256(original) != info['sha256']:
            raise ValueError(f'Translation source changed: {original}')
        parts = Path(info['path']).parts
        relative = vnvkr.virtual_path(Path(*parts[2:]).as_posix())
        text, _ = decode(original)
        obj = json.loads(text) if original.suffix.lower() == '.json' else None
        mappings = []
        for entry in work['entries']:
            if entry['path'] != info['path']:
                continue
            dest = translations[entry['id']]
            check_pair(entry['source'], dest)
            row = {'source': entry['source'], 'dest': dest}
            if obj is not None:
                row['context'] = stable_context(obj, entry['pointer'])
            else:
                row.update(section=entry['section'], key=entry['key'])
            mappings.append(row)
        files.append({'path': relative, 'kind': 'json' if obj is not None else 'ini',
                      'original_provider': parts[1], 'baseline_sha256': info['sha256'],
                      'mappings': mappings})
    for plugin in sorted((workspace / '01_Plugins/번역 완료').glob('*')):
        if plugin.suffix.casefold() not in {'.esp', '.esm'}:
            continue
        reference = base_plugins[plugin.name.casefold()]
        if native:
            accepted = []
            for row in native['mappings'][plugin.name]:
                try:
                    vnvkr_yesman.validate_mapping(row)
                except ValueError as error:
                    rejected.append({'plugin': plugin.name, **row, 'reason': str(error)})
                else:
                    accepted.append(row)
            files.append({'path': plugin.name, 'kind': 'plugin-records',
                          'baseline_sha256': reference['sha256'], 'mappings': accepted,
                          'review': 'user_completed_texts; output_structure_readback_required',
                          'input_validation_scope': native.get('validation_scope', 'native_nontext_comparison')})
            continue
        payload = f'plugins/{plugin.name}'
        files.append({'path': plugin.name, 'kind': 'plugin-copy',
                      'baseline_sha256': reference['sha256'],
                      'payload': payload, 'payload_sha256': vnvkr.sha256(plugin),
                      'review': 'user_completed; record_validation_pending'})
        payloads.append((plugin, payload))
    # User-completed optional copies stay in their own installed provider folders.
    # Inactive variants are translated without enabling them or changing profiles.
    for number, reference in enumerate(row for row in baseline['files'] if row['category'] == '99_Optional_Plugins'):
        plugin = workspace / reference['output']
        if not plugin.is_file():
            continue
        if native:
            optional_key = f"{reference['provider']}/{reference['data_path']}"
            optional_rows = native.get('optional_mappings', {}).get(optional_key)
            if optional_rows is None:
                raise ValueError(f'Missing optional record mappings: {optional_key}')
            accepted = []
            for row in optional_rows:
                try:
                    vnvkr_yesman.validate_mapping(row)
                except ValueError as error:
                    rejected.append({'plugin': plugin.name, 'provider': reference['provider'], **row, 'reason': str(error)})
                else:
                    accepted.append(row)
            files.append({'path': vnvkr.virtual_path(reference['data_path']), 'kind': 'plugin-records',
                          'provider': vnvkr.virtual_path(reference['provider']), 'optional': True,
                          'baseline_sha256': reference['sha256'], 'mappings': accepted,
                          'review': 'user_completed_texts; output_structure_readback_required'})
            continue
        payload = f'optional/{number}/{plugin.name}'
        files.append({'path': vnvkr.virtual_path(reference['data_path']), 'kind': 'plugin-copy',
                      'provider': vnvkr.virtual_path(reference['provider']), 'optional': True,
                      'baseline_sha256': reference['sha256'],
                      'payload': payload, 'payload_sha256': vnvkr.sha256(plugin),
                      'review': 'user_completed; record_validation_pending'})
        payloads.append((plugin, payload))
    if not files:
        raise ValueError('No translation data')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vnvkr-catalog-', dir=output.parent) as tmp:
        stage = Path(tmp) / 'catalog'
        stage.mkdir()
        for source, relative in payloads:
            target = vnvkr.contained(stage, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        metadata = {'schema_version': SCHEMA, 'files': files,
            'updated_plugin_backend': 'YesManAI/xEditLib' if native else 'not_available',
            'game_validation': 'not_run'}
        if native:
            metadata['plugin_fields'] = vnvkr.read_json(plugin_fields)['fields']
            metadata['mapping_review'] = native.get('report', [])
            metadata['input_validation_scope'] = native.get('validation_scope', 'native_nontext_comparison')
            metadata['output_verification'] = 'fresh_native_readback_required'
            metadata['rejected_mappings'] = rejected
        vnvkr.write_json(stage / 'catalog.json', metadata)
        stage.rename(output)
    return {'files': len(files), 'catalog': str(output)}


def merge_loose(source, entry):
    text, encoding = decode(source)
    matches = defaultdict(set)
    for row in entry['mappings']:
        check_pair(row['source'], row['dest'])
        identity = row['context'] if entry['kind'] == 'json' else (row['section'], row['key'])
        matches[(identity, row['source'])].add(row['dest'])
    missing, translated, unchanged = [], 0, 0
    if entry['kind'] == 'json':
        obj = json.loads(text)
        items = [{'pointer': list(pointer), 'source': value,
                  'context': stable_context(obj, list(pointer))} for pointer, value in json_values(obj)]
    else:
        items = list(ini_rows(text))
        lines = text.splitlines(keepends=True)
    for item in items:
        identity = item['context'] if entry['kind'] == 'json' else (item['section'], item['key'])
        destinations = matches.get((identity, item['source']), set())
        if len(destinations) != 1:
            missing.append({**item, 'reason': 'ambiguous' if destinations else 'unmatched'})
            continue
        dest = next(iter(destinations))
        if dest == item['source']:
            unchanged += 1
            continue
        translated += 1
        if entry['kind'] == 'json':
            container = obj
            for part in item['pointer'][:-1]:
                container = container[part]
            container[item['pointer'][-1]] = dest
        else:
            line = lines[item['line']]
            newline = '\r\n' if line.endswith('\r\n') else ('\n' if line.endswith('\n') else '')
            body = line[:-len(newline)] if newline else line
            lhs, rhs = body.split('=', 1)
            lead, trail = rhs[:len(rhs) - len(rhs.lstrip())], rhs[len(rhs.rstrip()):]
            quoted = rhs.strip().startswith('"') and rhs.strip().endswith('"')
            lines[item['line']] = lhs + '=' + lead + ('"' + dest + '"' if quoted else dest) + trail + newline
    result = (json.dumps(obj, ensure_ascii=False, indent='\t') + '\n'
              if entry['kind'] == 'json' else ''.join(lines))
    return result.encode(encoding), {'translated': translated, 'unchanged_by_design': unchanged,
                                   'unmatched': len(missing), 'unmatched_entries': missing}


def destination(installation, source, virtual=None):
    # A single copy operation can represent only descendants of the selected root.
    resolved = source.resolve()
    if not resolved.is_relative_to(installation.root):
        # Official starter packs are in Steam Data, outside the MO2 instance.
        # Put their translated copies beside the already enabled Fixed ESM master.
        # This needs no game-directory write or profile activation change.
        if virtual and resolved.is_relative_to(installation.data.resolve()):
            master = installation.providers.get('falloutnv.esm', [])
            if master:
                provider = Path(master[-1]['physical']).resolve().parent
                if provider.parent == installation.mods and provider.is_relative_to(installation.root):
                    target = provider / vnvkr.virtual_path(virtual)
                    return vnvkr.virtual_path(target.relative_to(installation.root).as_posix())
        raise ValueError(f'Source is outside the MO2 root; cannot mirror it in one Output: {source}')
    return vnvkr.virtual_path(resolved.relative_to(installation.root).as_posix())


def verified_delta(entry, catalog_dir, source):
    spec = entry.get('verified_delta')
    if not spec:
        return None
    for key in ('source_sha256', 'target_sha256', 'payload_sha256'):
        if not isinstance(spec.get(key), str) or not vnvkr.HASH.fullmatch(spec[key]):
            raise ValueError(f'Invalid verified delta metadata: {entry["path"]}')
    if type(spec.get('target_size')) is not int or spec['target_size'] < 0:
        raise ValueError(f'Invalid verified delta size: {entry["path"]}')
    if vnvkr.sha256(source) != spec['source_sha256']:
        return None
    patch = vnvkr.contained(catalog_dir, spec['payload'])
    if vnvkr.sha256(patch) != spec['payload_sha256']:
        raise ValueError(f'Verified delta integrity mismatch: {entry["path"]}')
    return patch, spec


def build_output(installation, catalog_dir, output):
    output = output.resolve()
    installation.guard_output(output)
    # This interface prepares manual overwrite files outside MO2, never a live mod.
    if output.is_relative_to(installation.root) or output.is_relative_to(installation.mods):
        raise ValueError('Output must be outside the MO2 installation and mods directories')
    report_path = output.with_name(output.name + '.report.json')
    if report_path.exists():
        raise FileExistsError(report_path)
    catalog = vnvkr.read_json(catalog_dir / 'catalog.json')
    if catalog.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported catalog format')
    # Optional providers may deliberately contain the same virtual plugin name.
    if catalog['files'] or not (catalog.get('font_bundle') or catalog.get('asset_bundle')):
        vnvkr.validate_entries([{'path': (f"optional/{vnvkr.virtual_path(e['provider'])}/{e['path']}"
                                         if e.get('optional') else f"active/{e['path']}")}
                               for e in catalog['files']])
    report = {'mo2_root': str(installation.root), 'profile': installation.profile,
              'output': str(output), 'created_utc': datetime.now(timezone.utc).isoformat(),
              'files': [], 'skipped': [], 'warnings': installation.warnings,
              'install_state': 'manual_copy_required', 'game_validation': 'not_run',
              'updated_plugin_backend': catalog.get('updated_plugin_backend', 'not_available')}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vnvkr-output-', dir=output.parent) as tmp:
        stage = Path(tmp) / 'Output'
        stage.mkdir()
        seen = set()
        active_native = [entry for entry in catalog['files'] if entry['kind'] == 'plugin-records'
                         and not entry.get('optional')
                         and entry['path'].casefold() in installation.active_keys
                         and entry['path'].casefold() in installation.providers]
        fast_native = {}
        for entry in active_native:
            source = installation.source(entry['path'])
            fast = verified_delta(entry, catalog_dir, source)
            if fast:
                fast_native[entry['path'].casefold()] = fast
        native_entries = [entry for entry in active_native if entry['path'].casefold() not in fast_native]
        native_files, native_stats = (None, {})
        if native_entries:
            native_files, native_stats = vnvkr_yesman.merge_plugins(installation, native_entries, catalog,
                                                                   Path(tmp) / 'NativeJob')
        delta_engine = None
        for entry in catalog['files']:
            key = entry['path'].casefold()
            chain = installation.providers.get(key)
            if entry.get('optional'):
                if entry['kind'] not in {'plugin-copy', 'plugin-records'} or '/' in vnvkr.virtual_path(entry['provider']):
                    raise ValueError('Invalid optional provider')
                source = vnvkr.contained(installation.mods, f"{entry['provider']}/{entry['path']}")
                chain = [{'provider': entry['provider']}]
                if not source.is_file():
                    report['skipped'].append({'path': entry['path'], 'provider': entry['provider'], 'reason': 'not_installed'})
                    continue
            else:
                if not chain or (entry['kind'] in {'plugin-copy', 'plugin-records'} and key not in installation.active_keys):
                    report['skipped'].append({'path': entry['path'], 'reason': 'not_enabled_or_not_installed'})
                    continue
                source = installation.source(entry['path'])
            original_hash = vnvkr.sha256(source)
            relative = destination(installation, source, entry['path'])
            if relative.casefold() in seen:
                raise ValueError(f'Duplicate physical output: {relative}')
            seen.add(relative.casefold())
            target = vnvkr.contained(stage, relative)
            result = {'path': entry['path'], 'output_path': relative,
                      'provider': chain[-1]['provider'], 'source_sha256': original_hash,
                      'source_updated': original_hash != entry['baseline_sha256']}
            if entry['kind'] == 'plugin-records':
                fast = (verified_delta(entry, catalog_dir, source) if entry.get('optional')
                        else fast_native.get(key))
                if fast:
                    patch, spec = fast
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if delta_engine is None:
                        delta_engine = vnvkr.engine(None)
                    vnvkr.delta(delta_engine, 'decode', source, patch, target)
                    if target.stat().st_size != spec['target_size'] or vnvkr.sha256(target) != spec['target_sha256']:
                        raise ValueError(f'Verified delta output mismatch: {entry["path"]}')
                    statistics = {'translated': spec.get('translated', len(entry['mappings'])),
                                  'unmatched': spec.get('unmatched', 0),
                                  'records_verified': spec.get('records_verified', 0),
                                  'verification': spec.get('verification', 'verified_delta_roundtrip')}
                    result.update(statistics, status='exact_source_verified_delta')
                else:
                    if entry.get('optional'):
                        # A same-name inactive variant gets its own copied session.
                        # Never swap a live provider or alter profile activation.
                        optional_files, optional_stats = vnvkr_yesman.merge_plugins(
                            installation, [entry], catalog, Path(tmp) / f'OptionalJob{len(seen)}',
                            source_overrides={entry['path']: source})
                        native_source, statistics = optional_files / entry['path'], optional_stats[entry['path']]
                    else:
                        native_source, statistics = native_files / entry['path'], native_stats[entry['path']]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(native_source, target)
                    result.update(statistics, status='matched_text_only; native_readback_verified')
            elif entry['kind'] == 'plugin-copy':
                payload = vnvkr.contained(catalog_dir, entry['payload'])
                if vnvkr.sha256(payload) != entry['payload_sha256']:
                    raise ValueError(f'Plugin payload integrity mismatch: {entry["path"]}')
                if original_hash != entry['baseline_sha256']:
                    report['skipped'].append({**result, 'reason': 'updated_plugin_needs_record_backend',
                                             'translation_applied': False})
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(payload, target)
                result['status'] = 'user_completed_copy; record_validation_pending'
            elif entry['kind'] in {'ini', 'json'}:
                raw, stats = merge_loose(source, entry)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                result.update(stats, status='merged_into_current_source')
            else:
                raise ValueError(f'Unsupported translation kind: {entry["kind"]}')
            if vnvkr.sha256(source) != original_hash:
                raise ValueError(f'Source changed during generation: {source}')
            result['output_sha256'] = vnvkr.sha256(target)
            report['files'].append(result)
        if catalog.get('font_bundle'):
            font_files, font_status = vnvkr_fonts.build_fonts(installation, catalog_dir,
                                                            catalog['font_bundle'], stage, seen)
            report['files'].extend(font_files)
            report['fonts'] = font_status
        if catalog.get('asset_bundle'):
            asset_files, asset_status = build_assets(installation, catalog_dir, catalog['asset_bundle'], stage, seen,
                                                    report.get('fonts', {}).get('mod'))
            report['files'].extend(asset_files)
            report['assets'] = asset_status
        if catalog.get('runtime_mods'):
            runtime_files, runtime_status = build_runtime_mods(installation, catalog_dir, catalog['runtime_mods'], stage, seen)
            report['files'].extend(runtime_files)
            report['runtime_mods'] = runtime_status
        if not report['files']:
            raise ValueError('No applicable translation files; no Output was published')
        # Read back every artifact before publishing the tree.
        for row in report['files']:
            if vnvkr.sha256(vnvkr.contained(stage, row['output_path'])) != row['output_sha256']:
                raise ValueError('Output readback failed')
        stage.rename(output)
    vnvkr.write_json(report_path, report)
    return report


def build_runtime_mods(installation, catalog_dir, specs, stage, seen):
    """Publish small Korean runtime mods that do not replace existing VNV providers."""
    files, activate_mods, activate_plugins = [], set(), set()
    for spec in specs:
        mod = vnvkr.virtual_path(spec['mod'])
        if '/' in mod:
            raise ValueError('Invalid runtime mod folder')
        if mod not in installation.mods_enabled:
            activate_mods.add(mod)
        for plugin in spec.get('plugins', []):
            activate_plugins.add(vnvkr.virtual_path(plugin))
        for entry in spec['files']:
            relative = vnvkr.virtual_path(entry['path'])
            payload = vnvkr.contained(catalog_dir, entry['payload'])
            if vnvkr.sha256(payload) != entry['payload_sha256']:
                raise ValueError(f'Runtime payload integrity mismatch: {mod}/{relative}')
            output_path = f'mods/{mod}/{relative}'
            if output_path.casefold() in seen:
                raise ValueError(f'Duplicate runtime output: {output_path}')
            seen.add(output_path.casefold())
            target = vnvkr.contained(stage, output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(payload, target)
            files.append({'path': relative, 'output_path': output_path, 'provider': mod,
                          'source_sha256': None, 'output_sha256': vnvkr.sha256(target),
                          'status': 'runtime_mod_copy'})
    return files, {'mods_requiring_activation': sorted(activate_mods),
                   'plugins_requiring_activation': sorted(activate_plugins),
                   'game_validation': 'not_run'}


def build_assets(installation, catalog_dir, spec, stage, seen, fallback_provider=None):
    """Mirror the current loose asset provider, or use the Korean font overlay."""
    default = vnvkr.virtual_path(fallback_provider or spec['default_mod'])
    if '/' in default:
        raise ValueError('Invalid asset mod folder')
    files, activation = [], set()
    for entry in spec['files']:
        relative = vnvkr.virtual_path(entry['path'])
        if not relative.casefold().startswith('textures/') or Path(relative).suffix.casefold() != '.dds':
            raise ValueError('Unexpected translated texture path')
        payload = vnvkr.contained(catalog_dir, entry['payload'])
        if vnvkr.sha256(payload) != entry['payload_sha256']:
            raise ValueError('Texture payload integrity mismatch')
        candidates = [vnvkr.contained(installation.mods, f'{name}/{relative}')
                      for name in reversed(installation.mods_enabled)]
        candidates.insert(0, vnvkr.contained(installation.overwrite, relative))
        source = next((p for p in candidates if p.is_file()), None)
        if source and not source.is_relative_to(installation.root):
            raise ValueError('Texture provider is outside the selected MO2 root')
        if source and source.is_relative_to(installation.root):
            output_path = source.relative_to(installation.root).as_posix()
            provider = source.relative_to(installation.mods).parts[0] if source.is_relative_to(installation.mods) else 'MO2:overwrite'
        else:
            provider, output_path = default, f'mods/{default}/{relative}'
            if default not in installation.mods_enabled:
                activation.add(default)
        if output_path.casefold() in seen:
            raise ValueError(f'Duplicate asset output: {output_path}')
        seen.add(output_path.casefold())
        before = vnvkr.sha256(source) if source else None
        target = vnvkr.contained(stage, output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(payload, target)
        if source and vnvkr.sha256(source) != before:
            raise ValueError('Texture source changed during generation')
        files.append({'path': relative, 'output_path': output_path, 'provider': provider,
                      'source_sha256': before, 'output_sha256': vnvkr.sha256(target),
                      'status': 'translated_texture_copy'})
    return files, {'mods_requiring_activation': sorted(activation), 'game_validation': 'not_run'}


def main():
    parser = argparse.ArgumentParser(description='Generate a manual-copy VNV Korean Output tree')
    commands = parser.add_subparsers(dest='command', required=True)
    catalog = commands.add_parser('catalog')
    catalog.add_argument('--workspace', type=Path, required=True)
    catalog.add_argument('--work-dir', type=Path, required=True)
    catalog.add_argument('--output', type=Path, required=True)
    catalog.add_argument('--plugin-maps', type=Path)
    catalog.add_argument('--plugin-fields', type=Path)
    run = commands.add_parser('output')
    run.add_argument('--mo2-root', type=Path, required=True)
    run.add_argument('--profile')
    run.add_argument('--catalog', type=Path, required=True)
    run.add_argument('--output', type=Path, default=Path('Output'))
    args = parser.parse_args()
    if args.command == 'catalog':
        result = make_catalog(args.workspace, args.work_dir, args.output, args.plugin_maps, args.plugin_fields)
    else:
        result = build_output(vnvkr.Installation(args.mo2_root, args.profile), args.catalog, args.output)
        result = {'files': len(result['files']), 'skipped': len(result['skipped']),
                  'output': str(args.output.resolve()), 'report': str(args.output.resolve()) + '.report.json'}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
