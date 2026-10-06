"""Build the VNV release catalog from xTranslator SST dictionaries."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import vnvkr
import vnvkr_xedit
from vnvkr_sst import read_sst

FLAT_SIGNATURES = {
    'CELL','WRLD','REFR','ACRE','ACTI','ARMO','ARMA','WEAP','MISC','KEYM',
    'ALCH','CLAS','RACE','HDPT','HAIR','EYES','CSNO','AMEF','REPU','RCCT',
    'FURN','MSET','COBJ','IMOD','CMNY','LIGH','GMST','PROJ','CCRD','DOOR',
    'NPC_','CREA','CONT','ENCH','TACT','MGEF','AMMO','CDCK','BOOK','RCPE',
    'MSTT','CHAL','INGR','CHIP','SPEL','NOTE','EXPL','DIAL','LSCR','WATR','ALOC',
}

OFFICIAL = {
    'falloutnv.esm','deadmoney.esm','honesthearts.esm','oldworldblues.esm',
    'lonesomeroad.esm','gunrunnersarsenal.esm','classicpack.esm',
    'mercenarypack.esm','tribalpack.esm','caravanpack.esm',
}


def _usable(entry) -> bool:
    if entry.rec.startswith('TES4') or entry.rec == '********':
        return False
    status_flags = (entry.flags >> 8) & 0xFF
    if status_flags & 0x40:
        return False
    return bool(entry.source and entry.source != entry.dest
                and '\ufffd' not in entry.source and '\ufffd' not in entry.dest)


def _structural_index(entry: dict):
    exact = defaultdict(set)
    loose = defaultdict(set)
    for row in entry.get('mappings', []):
        key = (
            row.get('owner', '').casefold(),
            row.get('id', '').casefold(),
            row.get('signature', ''),
            row.get('field', ''),
            row.get('source', ''),
        )
        if row.get('path'):
            exact[key].add(row['path'])
            loose[key[:-1]].add(row['path'])
    return exact, loose


def _derive_path(signature: str, field: str):
    if signature not in FLAT_SIGNATURES:
        return None
    if signature == 'REFR' and field == 'FULL':
        return None
    if signature == 'NOTE' and field == 'TNAM':
        return r'TNAM\Text'
    return field


def export_for_entry(sst_path: Path, old_entry: dict):
    sst = read_sst(sst_path)
    if not sst.plugins:
        raise ValueError(f'SST has no plugin header: {sst_path}')
    exact, loose = _structural_index(old_entry)
    rows = []
    stats = {
        'sst_entries': len(sst.entries),
        'usable': 0,
        'mapped': 0,
        'zero_form_skipped': 0,
        'pathless_direct': 0,
        'old_or_unchanged_skipped': 0,
        'unsafe_mapping_skipped': 0,
    }
    for item in sst.entries:
        if not _usable(item):
            stats['old_or_unchanged_skipped'] += 1
            continue
        stats['usable'] += 1
        local_id = item.form_id & 0x00FFFFFF
        owner_index = (item.form_id >> 24) & 0xFF
        if local_id == 0:
            stats['zero_form_skipped'] += 1
            continue
        if owner_index >= len(sst.plugins):
            stats['pathless_direct'] += 1
            continue
        owner = sst.plugins[owner_index]
        signature = item.rec[:4]
        field = item.rec[4:]
        form_id = f'{local_id:06x}'
        key = (owner.casefold(), form_id, signature, field, item.source)
        paths = exact.get(key, set())
        if len(paths) != 1:
            paths = loose.get(key[:-1], set())
        path = next(iter(paths)) if len(paths) == 1 else _derive_path(signature, field)
        if not path:
            # Direct SST can still match safely by owner/FormID/signature/field/source.
            # The worker rejects ambiguous destinations. Base/DLC fallback requires
            # an exact path, so pathless rows are never used for inheritance.
            path = ''
            stats['pathless_direct'] += 1
        row = {
            'owner': owner.casefold(),
            'id': form_id,
            'signature': signature,
            'field': field,
            'path': path,
            'source': item.source,
            'dest': item.dest,
            'rec_id': item.rec_id,
            'rec_id_max': item.rec_id_max,
            'string_id': item.string_id,
            'origin': 'sst_direct',
        }
        try:
            vnvkr_xedit.validate_mapping(row)
        except ValueError:
            # Keep the release conservative. SST rows that alter printf/font
            # control tokens are reported for dictionary cleanup instead of
            # aborting the user's whole patch run.
            stats['unsafe_mapping_skipped'] += 1
            continue
        rows.append(row)
        stats['mapped'] += 1
    return rows, stats, sst


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-catalog', type=Path, required=True)
    parser.add_argument('--sst-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mcm-direct', type=Path, default=ROOT / 'data/mcm_direct_mappings.json')
    args = parser.parse_args()

    base = args.base_catalog.resolve()
    out = args.output.resolve()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(base, out)
    catalog_path = out / 'catalog.json'
    catalog = vnvkr.read_json(catalog_path)

    # Add reviewed direct-display MCM JSON mappings that are not backed by a
    # separate $key translation INI. Token-only JSON files need no direct edit.
    if args.mcm_direct and args.mcm_direct.is_file():
        mcm_spec = vnvkr.read_json(args.mcm_direct)
        if mcm_spec.get('schema_version') != 1:
            raise ValueError('Unsupported MCM direct mapping schema')
        by_loose_key = {
            (entry.get('original_provider', '').casefold(), entry.get('path', '').casefold()): i
            for i, entry in enumerate(catalog.get('files', []))
            if entry.get('kind') in {'json', 'ini'}
        }
        for item in mcm_spec.get('files', []):
            entry = {
                'path': vnvkr.virtual_path(item['path']),
                'kind': 'json',
                'original_provider': item['provider'],
                'baseline_sha256': item['baseline_sha256'],
                'mappings': item['mappings'],
                'translation_source': 'reviewed_mcm_direct_json',
            }
            for row in entry['mappings']:
                if not all(isinstance(row.get(k), str) for k in ('context', 'source', 'dest')):
                    raise ValueError(f'Invalid MCM direct mapping: {entry["path"]}')
                from vnvkr_output import check_pair
                check_pair(row['source'], row['dest'])
            key = (entry['original_provider'].casefold(), entry['path'].casefold())
            if key in by_loose_key:
                catalog['files'][by_loose_key[key]] = entry
            else:
                by_loose_key[key] = len(catalog['files'])
                catalog['files'].append(entry)
        catalog['mcm_direct_json'] = {
            'files': len(mcm_spec.get('files', [])),
            'mappings': sum(len(x.get('mappings', [])) for x in mcm_spec.get('files', [])),
        }

    by_target = {}
    for path in args.sst_dir.glob('*_en_ko.sst'):
        sst = read_sst(path)
        if not sst.plugins:
            continue
        target = sst.plugins[-1].casefold()
        if target in by_target:
            raise ValueError(f'Duplicate direct SST target {target}: {by_target[target].name}, {path.name}')
        by_target[target] = path

    plugin_stats = []
    fallback_only = []
    for entry in catalog.get('files', []):
        if entry.get('kind') != 'plugin-records':
            continue

        # xdelta outputs belong to the old mapping snapshot and must never bypass
        # the authoritative SST pipeline.
        entry.pop('verified_delta', None)
        old_rows = list(entry.get('mappings', []))
        owner_hints = sorted({
            row.get('owner', '').casefold() for row in old_rows
            if row.get('owner', '').casefold() in OFFICIAL
        })
        if owner_hints:
            entry['fallback_owner_hints'] = owner_hints

        sst_path = by_target.get(entry['path'].casefold())
        if not sst_path:
            entry['mappings'] = []
            entry['fallback_only'] = True
            entry['translation_source'] = 'base_dlc_sst_fallback'
            fallback_only.append(entry['path'])
            plugin_stats.append({'plugin': entry['path'], 'mode': 'fallback_only', 'mappings': 0})
            continue

        rows, stats, sst = export_for_entry(sst_path, entry)
        entry['mappings'] = rows
        entry['sst_source'] = sst_path.name
        entry['sst_format'] = sst.format
        entry['sst_plugins'] = sst.plugins
        entry['sst_stats'] = stats
        entry['translation_source'] = 'xtranslator_sst'
        if rows:
            entry.pop('fallback_only', None)
        else:
            # Some old SSTs contain only FormID=0/source-only entries. Keep the
            # plugin eligible for the safe base/DLC fallback instead of guessing
            # which record a source-only row belongs to.
            entry['fallback_only'] = True
        plugin_stats.append({
            'plugin': entry['path'],
            'mode': 'direct_sst',
            'sst': sst_path.name,
            'mappings': len(rows),
            **stats,
        })

    # v1.0.6 translation scope is deliberately narrow: existing MO2 plugins,
    # MCM JSON and translation text files. Old radio/UI runtime overlays and
    # translated texture payloads are not part of the SST patcher.
    catalog.pop('asset_bundle', None)
    catalog.pop('runtime_mods', None)
    catalog.pop('radio_caption_backend', None)
    catalog.pop('verified_delta_backend', None)
    catalog['verified_delta_files'] = 0
    catalog['plugin_translation_source'] = 'xTranslator SST direct + FalloutNV/DLC SST fallback'
    catalog['updated_plugin_backend'] = 'Python ctypes + XEditLib'
    catalog['sst_source_policy'] = {
        'authoritative_source': 'xTranslator UserDictionaries/FalloutNV',
        'direct_priority': True,
        'fallback_masters': sorted(OFFICIAL),
        'zero_form_policy': 'skip_unstable_source_only_rows',
        'path_metadata': 'reviewed catalog path or safe flat-field derivation',
    }
    catalog['sst_build'] = {
        'source_files': len(by_target),
        'fallback_only_plugins': fallback_only,
        'plugins': plugin_stats,
    }
    vnvkr.write_json(catalog_path, catalog)

    deltas = out / 'verified-deltas'
    if deltas.exists():
        shutil.rmtree(deltas)

    report = {
        'direct_sst_plugins': sum(x['mode'] == 'direct_sst' for x in plugin_stats),
        'fallback_only_plugins': fallback_only,
        'direct_mappings': sum(x['mappings'] for x in plugin_stats),
        'pathless_direct_rows': sum(x.get('pathless_direct', 0) for x in plugin_stats),
        'zero_form_skipped': sum(x.get('zero_form_skipped', 0) for x in plugin_stats),
        'unsafe_mapping_skipped': sum(x.get('unsafe_mapping_skipped', 0) for x in plugin_stats),
        'output': str(out),
    }
    vnvkr.write_json(out / 'sst-build-report.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
