"""Recover release resources and change only the key-prompt UI plugin."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
from tools.prepare_key_prompt_test import prepare as patch_plugin


def resources(exe):
    reader = CArchiveReader(str(exe))
    return {n.replace('\\', '/'): reader.extract(n) for n in reader.toc
            if n.replace('\\', '/').startswith(('TranslationData/', 'Backend/'))
            or n.replace('\\', '/') in ('NSKRXEditWorker.exe', 'VNVKRXEditWorker.exe')}


def prepare(exe, target):
    if target.exists():
        raise FileExistsError(target)
    data = resources(exe)
    target.mkdir(parents=True)
    for name, raw in data.items():
        path = (target / name).resolve()
        if not path.is_relative_to(target.resolve()):
            raise ValueError('Unsafe resource path')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    catalog_path = target / 'TranslationData/catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    candidates = [item for mod in catalog['runtime_mods'] for item in mod['files']
                  if item['path'].endswith('UI Strings.esp')]
    if len(candidates) != 1:
        raise ValueError('Expected one Korean UI Strings plugin')
    item = candidates[0]
    plugin = target / 'TranslationData' / item['payload']
    if hashlib.sha256(plugin.read_bytes()).hexdigest() != item['payload_sha256']:
        raise ValueError('UI plugin checksum mismatch')
    revised = plugin.with_suffix('.revised')
    patch_plugin(plugin, None, revised)
    plugin.write_bytes(revised.read_bytes())
    revised.unlink()
    item['payload_sha256'] = hashlib.sha256(plugin.read_bytes()).hexdigest()
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify(base, revised):
    old, new = resources(base), resources(revised)
    if old.keys() != new.keys():
        raise ValueError('Resource set changed')
    before, after = [json.loads(r['TranslationData/catalog.json'].decode('utf-8-sig')) for r in (old, new)]
    expected = copy.deepcopy(before)
    item = next(i for m in expected['runtime_mods'] for i in m['files'] if i['path'].endswith('UI Strings.esp'))
    name = 'TranslationData/' + item['payload']
    item['payload_sha256'] = hashlib.sha256(new[name]).hexdigest()
    if after != expected or {n for n in old if old[n] != new[n]} != {'TranslationData/catalog.json', name}:
        raise ValueError('Unrelated resource changes')
    # Regenerate the expected bytes using the validated record-preserving transform.
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        p = Path(temp)
        (p/'base.esp').write_bytes(old[name])
        patch_plugin(p/'base.esp', None, p/'expected.esp')
        if new[name] != (p/'expected.esp').read_bytes():
            raise ValueError('UI plugin is not the expected key-prompt patch')
    print('PASS: only two key-prompt GMSTs and catalog checksum changed; fonts/DLL/translations/worker preserved.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['prepare', 'verify'])
    p.add_argument('base', type=Path)
    p.add_argument('target', type=Path)
    args = p.parse_args()
    (prepare if args.mode == 'prepare' else verify)(args.base, args.target)
