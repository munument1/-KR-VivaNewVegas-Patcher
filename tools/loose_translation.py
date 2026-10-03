"""Prepare and rebuild human-reviewed NV MCM/INI text with protected structure."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

DISPLAY_KEYS = {'displayName', 'description', 'listTitle', 'pageTitle', 'title', 'mouse', 'strings', 'suffix'}
TOKEN = re.compile(r'%%|%[a-zA-Z](?:[a-zA-Z])?|\{[^{}]+\}|<[^<>]+>|&[a-zA-Z0-9]+;|#\d+\|')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def decode(path):
    raw = path.read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        encoding = 'utf-16'
    elif raw.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf-8-sig'
    else:
        encoding = 'utf-8'
    return raw.decode(encoding), encoding


def json_values(value, pointer=(), key=''):
    if isinstance(value, dict):
        for name, child in value.items():
            yield from json_values(child, pointer + (name,), name)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from json_values(child, pointer + (i,), key)
    elif isinstance(value, str) and key in DISPLAY_KEYS:
        if value.strip() and not value.startswith('$') and value.strip() not in {'s', '%', 'ms', 'x'}:
            yield pointer, value


def prepare(workspace, output):
    if output.exists():
        raise FileExistsError(output)
    entries, sources, files = [], {}, []
    for category in ('02_MCM', '03_Translations'):
        for path in sorted((workspace / category).rglob('*')):
            if not path.is_file() or path.suffix.lower() not in {'.json', '.ini'}:
                continue
            text, encoding = decode(path)
            relative = path.relative_to(workspace).as_posix()
            files.append({'path': relative, 'sha256': sha(path), 'encoding': encoding})
            if path.suffix.lower() == '.json':
                items = [{'pointer': list(pointer), 'source': value} for pointer, value in json_values(json.loads(text))]
            else:
                items = []
                section = ''
                for line_number, line in enumerate(text.splitlines(keepends=True)):
                    line = line.rstrip('\r\n')
                    stripped = line.strip()
                    if stripped.startswith('[') and stripped.endswith(']'):
                        section = stripped
                    if not stripped or stripped.startswith((';', '#', '[')) or '=' not in line:
                        continue
                    key, raw_value = line.split('=', 1)
                    value = raw_value.strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    if not value:
                        continue
                    items.append({'line': line_number, 'section': section, 'key': key.strip(), 'source': value})
            for item in items:
                source = item['source']
                if source not in sources:
                    sources[source] = str(len(sources) + 1)
                entries.append({'path': relative, 'id': sources[source], **item})
    output.mkdir(parents=True)
    (output / 'work.json').write_text(json.dumps({'files': files, 'entries': entries}, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'sources.json').write_text(json.dumps([{'id': identity, 'source': source} for source, identity in sources.items()], ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(files), 'entries': len(entries), 'unique': len(sources)}, ensure_ascii=False))


def apply(workspace, work_dir, translations, output):
    if output.exists():
        raise FileExistsError(output)
    work = json.loads((work_dir / 'work.json').read_text(encoding='utf-8'))
    accepted = json.loads(translations.read_text(encoding='utf-8'))
    if not isinstance(accepted, dict):
        raise ValueError('Translations must be an ID-to-text object')
    expected_ids = {entry['id'] for entry in work['entries']}
    if set(accepted) != expected_ids:
        raise ValueError(f'Missing/extra translations: {sorted(expected_ids - set(accepted))} / {sorted(set(accepted) - expected_ids)}')
    for entry in work['entries']:
        dest = accepted[entry['id']]
        if not isinstance(dest, str) or not dest or '\n' in dest or '\r' in dest:
            raise ValueError(f'Invalid translation {entry["id"]}')
        if Counter(TOKEN.findall(entry['source'])) != Counter(TOKEN.findall(dest)):
            raise ValueError(f'Protected token mismatch {entry["id"]}')
        prefix = re.match(r'#\d+\|', entry['source'])
        if prefix and not dest.startswith(prefix.group()):
            raise ValueError(f'Message prefix moved {entry["id"]}')
    rendered, report = [], []
    for info in work['files']:
        source = workspace / info['path']
        if sha(source) != info['sha256']:
            raise ValueError(f'Source changed: {source}')
        text, encoding = decode(source)
        items = [entry for entry in work['entries'] if entry['path'] == info['path']]
        if source.suffix.lower() == '.json':
            obj = json.loads(text)
            for entry in items:
                container = obj
                for part in entry['pointer'][:-1]:
                    container = container[part]
                key = entry['pointer'][-1]
                assert container[key] == entry['source']
                container[key] = accepted[entry['id']]
            result = json.dumps(obj, ensure_ascii=False, indent='\t') + '\n'
            # Independent readback: reverting display fields reproduces original JSON tree.
            readback = json.loads(result)
            for entry in items:
                container = readback
                for part in entry['pointer'][:-1]:
                    container = container[part]
                container[entry['pointer'][-1]] = entry['source']
            assert readback == json.loads(text)
        else:
            lines = text.splitlines(keepends=True)
            for entry in items:
                line = lines[entry['line']]
                # Keep assignment, whitespace, quotes, duplicate rows and line endings.
                newline = '\r\n' if line.endswith('\r\n') else ('\n' if line.endswith('\n') else '')
                body = line[:-len(newline)] if newline else line
                lhs, rhs = body.split('=', 1)
                lead = rhs[:len(rhs) - len(rhs.lstrip())]
                trail = rhs[len(rhs.rstrip()):]
                value = rhs.strip()
                quoted = value.startswith('"') and value.endswith('"')
                original = value[1:-1] if quoted else value
                assert original == entry['source']
                dest = accepted[entry['id']]
                if quoted:
                    dest = '"' + dest + '"'
                lines[entry['line']] = lhs + '=' + lead + dest + trail + newline
            result = ''.join(lines)
            reverted = result.splitlines(keepends=True)
            originals = text.splitlines(keepends=True)
            for entry in items:
                reverted[entry['line']] = originals[entry['line']]
            assert ''.join(reverted) == text
        rendered.append((info['path'], result.encode(encoding)))
        report.append({'path': info['path'], 'source_sha256': info['sha256'], 'entries': len(items), 'encoding': encoding})
    output.mkdir(parents=True)
    for relative, raw in rendered:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for item in report:
        item['translated_sha256'] = sha(output / item['path'])
    (output / 'validation.json').write_text(json.dumps({'files': report, 'entries': len(work['entries']), 'protected_tokens': 'passed', 'non_display_structure': 'passed', 'source_hashes': 'passed', 'game_test': 'not_run'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(rendered), 'entries': len(work['entries']), 'output': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'apply'])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--translations', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.workspace, args.work_dir)
    else:
        apply(args.workspace, args.work_dir, args.translations, args.output)
