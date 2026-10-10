"""Headless UTF-8 XEditLib worker for VNV Korean Patcher.

The parent process prepares an isolated copy of the current MO2 load-order prefix.
This worker applies direct SST mappings first, then base/DLC SST fallback mappings
for exact owner/FormID/signature/field/path/source matches. It performs no network I/O.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from vnvkr_xelib import XEditLib
from vnvkr_plugin_text import write_plugin

FLAT_SIGNATURES = {
    'CELL','WRLD','REFR','ACRE','ACTI','ARMO','ARMA','WEAP','MISC','KEYM',
    'ALCH','CLAS','RACE','HDPT','HAIR','EYES','CSNO','AMEF','REPU','RCCT','FURN','MSET','COBJ','IMOD',
    'CMNY','LIGH','GMST','PROJ','CCRD','DOOR','NPC_','CREA','CONT','ENCH','TACT','MGEF','AMMO','CDCK',
    'BOOK','RCPE','MSTT','CHAL','INGR','CHIP','SPEL','NOTE','EXPL','DIAL','LSCR','WATR','ALOC',
}
DISPLAY_CONTAINERS = {'XMRK','EPFT','RDAT'}
FIELD_RE = re.compile(r'^([A-Z0-9_]{4})(?: -|$)')


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def sha_obj(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode('utf-8')).hexdigest()


def runtime_dir() -> Path:
    explicit = os.environ.get('VNVKR_XEDIT_RUNTIME')
    if explicit:
        return Path(explicit).resolve()
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent / 'Backend'
    fallback = Path(__file__).resolve().parent / '.tools' / 'xeditlib-native'
    if fallback.is_dir():
        return fallback
    raise FileNotFoundError('XEditLib runtime directory is not configured')


def field_name(x: XEditLib, handle: int):
    match = FIELD_RE.match(x.name(handle))
    return match.group(1) if match else None


def text_fields(x: XEditLib, record: int, wanted: set[str]):
    found = []
    signature = x.signature(record)
    if signature in FLAT_SIGNATURES:
        for field in wanted:
            paths = (['FULL', r'XMRK\FULL'] if signature == 'REFR' and field == 'FULL'
                     else [r'TNAM\Text'] if signature == 'NOTE' and field == 'TNAM'
                     else [field])
            for relative in paths:
                if not x.has_element(record, relative):
                    continue
                child = x.get_element(record, relative)
                try:
                    if x.value_type(child) in (3, 4):
                        found.append({'field': field, 'path': relative, 'source': x.get_value(child)})
                finally:
                    x.release(child)
        return found

    def walk(handle: int, inherited=None, prefix=''):
        try:
            children = x.get_elements(handle)
        except Exception:
            return
        for child in children:
            try:
                if x.element_type(child) in (0, 1, 2, 10, 11, 13):
                    continue
                named = field_name(x, child)
                field = named or inherited
                part = x.path_name(child, True) or x.path_name(child, False) or x.name(child)
                relative = prefix + '\\' + part if prefix else part
                value_type = x.value_type(child)
                if field and field in wanted and value_type in (3, 4):
                    found.append({'field': field, 'path': relative, 'source': x.get_value(child)})
                elif value_type in (9, 10, 11) and (
                        not named or named in wanted or named in DISPLAY_CONTAINERS):
                    walk(child, field, relative)
            finally:
                x.release(child)
    walk(record)
    return found


class IdentityCache:
    def __init__(self, x: XEditLib):
        self.x = x
        self.files = {}

    def identity(self, file_handle: int, record: int):
        if file_handle not in self.files:
            self.files[file_handle] = {
                'masters': self.x.get_master_names(file_handle),
                'name': self.x.name(file_handle),
            }
        local = self.x.get_form_id(record, True)
        meta = self.files[file_handle]
        index = local >> 24
        owner = meta['masters'][index] if index < len(meta['masters']) else meta['name']
        return {
            'owner': owner.lower(),
            'id': format(local & 0xFFFFFF, '06x'),
            'signature': self.x.signature(record),
        }


def row_key(row) -> str:
    return '|'.join((row['owner'].lower(), row['id'].lower(), row['signature']))


def record_json(x: XEditLib, record: int):
    signature = x.signature(record)
    if signature in {'CELL', 'DIAL', 'WRLD'}:
        obj = {}
        for child in x.get_elements(record):
            try:
                if x.element_type(child) not in (0, 1, 2) and not x.name(child).startswith('Child Group'):
                    obj.update(json.loads(x.element_to_json(child)))
            finally:
                x.release(child)
    else:
        obj = json.loads(x.element_to_json(record))
    if isinstance(obj.get('Record Header'), dict):
        obj['Record Header'].pop('Data Size', None)
    group = x.get_element_group(record)
    try:
        obj['$parent'] = x.path(group, True, True)
    finally:
        x.release(group)
    return obj


def digest(x: XEditLib, record: int) -> str:
    return sha_obj(record_json(x, record))


def header_digest(x: XEditLib, file_handle: int) -> str:
    header = x.get_element(file_handle, 'File Header')
    try:
        obj = json.loads(x.element_to_json(header))
    finally:
        x.release(header)
    if isinstance(obj.get('Record Header'), dict):
        obj['Record Header'].pop('Data Size', None)
    if isinstance(obj.get('HEDR - Header'), dict):
        obj['HEDR - Header'].pop('Number of Records', None)
    onam = obj.get('ONAM - Overriden Forms')
    if isinstance(onam, list):
        onam.sort()
    return sha_obj(obj)


def select_destination(item, direct_candidates, fallback_candidates):
    def matches(candidates, exact_path):
        values = {
            c['dest'] for c in candidates
            if c['field'] == item['field']
            and c['source'] == item['source']
            and (not exact_path or c['path'] == item['path'])
        }
        return values

    # Direct SST always wins. Prefer exact xEdit path; source+field is only a
    # fallback for stable flat records where the SST has no path information.
    direct = matches(direct_candidates, True)
    if not direct:
        direct = matches(direct_candidates, False)
    if direct:
        return direct, 'sst_direct'

    # Base/DLC inheritance is deliberately stricter: an override must retain the
    # exact field path as well as owner/FormID/signature/source.
    inherited = matches(fallback_candidates, True)
    if inherited:
        return inherited, 'base_dlc_sst_fallback'
    return set(), None


def run(request: dict):
    root = runtime_dir()
    dll = root / 'XEditLib.dll'
    if not dll.is_file():
        raise FileNotFoundError(dll)
    if ctypes.windll.kernel32.GetACP() != 65001:
        raise RuntimeError('VNVKR XEdit worker must run with UTF-8 active code page')

    x = XEditLib(dll)
    game = Path(request['game']).resolve()
    fallback_targets = {x.lower() for x in request.get('fallbackTargets', [])}
    fallback_by_record = {}
    for mapping in request.get('fallbackMappings') or []:
        fallback_by_record.setdefault(row_key(mapping), []).append(mapping)

    result = {'engine': 'Python/ctypes/XEditLib', 'acp': 65001, 'files': []}
    fields_by_sig = {sig: set(fields) for sig, fields in (request.get('fields') or {}).items()}

    x.init()
    try:
        x.set_language('English')
        x.set_game_path(str(game) + os.sep)
        x.set_game_mode(x.GM_FNV)
        x.load_plugins('\n'.join(request['plugins']), True, False)
        x.wait_for_loader()

        targets = request.get('targets') or request['plugins']
        for plugin in targets:
            # XEditLib may recycle numeric handles after Release(). Never keep
            # file metadata cached across target files under the old handle.
            identities = IdentityCache(x)
            file_handle = x.file_by_name(plugin)
            rows, changed, missing, before_hashes = [], [], [], []
            try:
                head_hash = header_digest(x, file_handle)
                expected_header = request.get('expectedHeaders', {}).get(plugin)
                if expected_header and expected_header != head_hash:
                    raise RuntimeError('Plugin header readback mismatch ' + plugin)

                expected = {row_key(r): r for r in request.get('expected', {}).get(plugin, [])}
                expected_changes = {}
                for update in request.get('changes', {}).get(plugin, []):
                    expected_changes.setdefault(row_key(update), []).append(update)

                mappings = (request.get('mappings') or {}).get(plugin, [])
                direct_by_record = {}
                for mapping in mappings:
                    direct_by_record.setdefault(row_key(mapping), []).append(mapping)
                allow_fallback = plugin.lower() in fallback_targets

                all_records = x.get_records(file_handle, '', True)
                record_index_keys = []
                verified = set()
                for record in sorted(all_records, reverse=True):
                    try:
                        signature = x.signature(record)
                        if signature == 'TES4':
                            continue
                        ident = identities.identity(file_handle, record)
                        record_key = row_key(ident)
                        record_index_keys.append(record_key)

                        mode = request.get('mode')
                        direct_candidates = direct_by_record.get(record_key, [])
                        inherited_candidates = fallback_by_record.get(record_key, []) if allow_fallback else []
                        prior = expected.get(record_key)

                        needs_items = (
                            mode == 'apply' and (direct_candidates or inherited_candidates)
                        ) or (
                            mode == 'verify' and prior is not None
                        )
                        if not needs_items:
                            continue

                        edid = ''
                        if x.has_element(record, 'EDID'):
                            edid = x.get_value(record, 'EDID')
                        wanted = fields_by_sig.get(signature)
                        items = (text_fields(x, record, wanted)
                                 if wanted and (signature != 'GMST' or edid.startswith('s'))
                                 else [])

                        if mode == 'verify':
                            verified.add(record_key)
                            for update in expected_changes.get(record_key, []):
                                if x.get_value(record, update['path']) != update['dest']:
                                    raise RuntimeError('Translation readback mismatch ' + record_key)
                                x.set_value(record, update['path'], update['source'])
                            if digest(x, record) != prior['hash']:
                                raise RuntimeError('Record structure readback mismatch ' + record_key)
                            continue

                        original_digest = digest(x, record)
                        updates = []
                        for item in items:
                            row = {**ident, 'edid': edid, **item}
                            values, origin = select_destination(row, direct_candidates, inherited_candidates)
                            if not values:
                                # Only direct SST mismatches are reported. A fallback miss simply
                                # means the override has diverged from the base/DLC source text.
                                if direct_candidates:
                                    missing.append({**row, 'reason': 'direct_sst_no_match',
                                                    'mappingOrigin': 'sst_direct'})
                                continue
                            if len(values) != 1:
                                missing.append({**row, 'reason': 'ambiguous_translation',
                                                'mappingOrigin': origin})
                                continue
                            dest = next(iter(values))
                            if dest == row['source']:
                                continue
                            if '\ufffd' in row['source']:
                                missing.append({**row, 'reason': 'source_encoding_unreadable',
                                                'mappingOrigin': origin})
                                continue
                            x.set_value(record, row['path'], dest)
                            updates.append({**row, 'dest': dest, 'mappingOrigin': origin})

                        if updates:
                            for update in updates:
                                x.set_value(record, update['path'], update['source'])
                            if digest(x, record) != original_digest:
                                raise RuntimeError('Unexpected non-text mutation ' + record_key)
                            for update in updates:
                                x.set_value(record, update['path'], update['dest'])
                            before_hashes.append({**ident, 'hash': original_digest})
                            changed.extend(updates)
                        if request.get('includeRows'):
                            rows.extend({**ident, 'edid': edid, **item} for item in items)
                    finally:
                        x.release(record)

                record_index_keys.sort()
                record_index_hash = hashlib.sha256(
                    '\n'.join(record_index_keys).encode('utf-8')).hexdigest()
                expected_index = (request.get('expectedRecordIndexes') or {}).get(plugin)
                if expected_index and expected_index != record_index_hash:
                    raise RuntimeError('Record index readback mismatch ' + plugin)
                if request.get('mode') == 'verify' and len(verified) != len(expected):
                    raise RuntimeError('Records missing from readback ' + plugin)

                if request.get('mode') == 'apply':
                    out_dir = Path(request['outDir']).resolve()
                    out_dir.mkdir(parents=True, exist_ok=True)
                    target = out_dir / plugin
                    if target.exists():
                        raise FileExistsError(target)
                    write_plugin(game / 'Data' / plugin, target, changed,
                                 x.get_master_names(file_handle))

                result['files'].append({
                    'plugin': plugin,
                    'masters': x.get_master_names(file_handle),
                    'headerHash': head_hash,
                    'recordIndexHash': record_index_hash,
                    'recordCount': len(record_index_keys),
                    'rows': rows,
                    'changed': changed,
                    'missing': missing,
                    'beforeHashes': before_hashes,
                })
            finally:
                x.release(file_handle)
    finally:
        x.close()
    return result


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--print-acp':
        print(ctypes.windll.kernel32.GetACP())
        return 0
    if len(sys.argv) < 2:
        raise SystemExit('usage: VNVKRXEditWorker <request.json> [xEdit isolation switches]')
    request_path = Path(sys.argv[1]).resolve()
    request = json.loads(request_path.read_text(encoding='utf-8-sig'))
    result = run(request)
    output = Path(request['output']).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
