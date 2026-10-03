"""Compare native xEditLib JSON exports, never plugin binary contents."""
import argparse
from collections import Counter
import json
from pathlib import Path


def record_key(row):
    return row['owner'], row['id'], row['signature']


def text_key(row):
    return (*record_key(row), row['path'])


def mask_text(obj, fields):
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key.startswith('Child Group'):
                continue
            field = key.split(' -', 1)[0]
            result[key] = '<display text>' if field in fields and isinstance(value, str) else mask_text(value, fields)
        return result
    if isinstance(obj, list):
        return [mask_text(value, fields) for value in obj]
    return obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--translated', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original = json.loads(args.original.read_text(encoding='utf-8'))
    translated = json.loads(args.translated.read_text(encoding='utf-8'))
    if args.output.exists():
        raise FileExistsError(args.output)
    target_files = {row['plugin'].casefold(): row for row in translated['files']}
    mappings, report = {}, []
    for file in original['files']:
        target = target_files[file['plugin'].casefold()]
        if file['masters'] != target['masters']:
            raise ValueError(f'Masters changed: {file["plugin"]}')
        target_rows = {text_key(row): row for row in target['rows']}
        if set(target_rows) != {text_key(row) for row in file['rows']}:
            raise ValueError(f'Translatable fields added/deleted: {file["plugin"]}')
        source_structures = {record_key(r): r['json'] for r in file.get('structures', [])}
        target_structures = {record_key(r): r['json'] for r in target.get('structures', [])}
        allowed = {}
        for row in file['rows']:
            allowed.setdefault(record_key(row), set()).add(row['field'])
        blocked, recovered, unreadable = set(), [], []
        for key, source in source_structures.items():
            if mask_text(source, allowed[key]) != mask_text(target_structures[key], allowed[key]):
                blocked.add(key)
        for row in file['rows']:
            dest = target_rows[text_key(row)]['source']
            if dest == row['source']:
                continue
            if record_key(row) in blocked:
                continue
            if '\ufffd' in row['source'] or '\ufffd' in dest:
                unreadable.append({**row, 'dest': dest, 'reason': 'needs_legacy_codepage_recovery'})
                continue
            recovered.append({**row, 'dest': dest})
        mappings[file['plugin']] = recovered
        report.append({'plugin': file['plugin'], 'fields': len(file['rows']), 'mappings': len(recovered),
                       'blocked_nontext_records': [list(key) for key in sorted(blocked)],
                       'unreadable_fields': unreadable})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'mappings': mappings, 'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'plugins': len(mappings), 'mappings': sum(map(len, mappings.values())),
                      'blocked_records': sum(len(row['blocked_nontext_records']) for row in report),
                      'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
