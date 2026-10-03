"""Attach exact-version xdelta payloads for fully verified native outputs."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile

import vnvkr


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mo2-root', type=Path, required=True)
    p.add_argument('--profile', required=True)
    p.add_argument('--base-catalog', type=Path, required=True)
    p.add_argument('--verified-dir', type=Path, required=True)
    p.add_argument('--verified-originals', type=Path, required=True)
    p.add_argument('--apply-json', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    inst = vnvkr.Installation(a.mo2_root, a.profile)
    applied = {row['plugin']: row for row in vnvkr.read_json(a.apply_json)['files']}
    engine = vnvkr.engine(None)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vnvkr-deltas-', dir=a.output.parent) as tmp:
        stage = Path(tmp) / 'catalog'
        shutil.copytree(a.base_catalog, stage)
        delta_dir = stage / 'native-deltas'
        if delta_dir.exists():
            shutil.rmtree(delta_dir)
        delta_dir.mkdir()
        catalog = vnvkr.read_json(stage / 'catalog.json')
        verified = 0
        for index, entry in enumerate(catalog['files']):
            if entry['kind'] != 'plugin-records' or entry.get('optional'):
                continue
            name = entry['path']
            if name.casefold() not in inst.active_keys:
                continue
            source = inst.source(name)
            original = a.verified_originals / name
            target = a.verified_dir / name
            if not original.is_file() or not target.is_file():
                raise FileNotFoundError(name)
            source_hash = vnvkr.sha256(source)
            if source_hash != vnvkr.sha256(original):
                raise ValueError(f'Source changed since full verification: {name}')
            target_hash = vnvkr.sha256(target)
            patch = delta_dir / f'{index:04d}.vcdiff'
            vnvkr.delta(engine, 'encode', source, target, patch)
            check = Path(tmp) / f'{index:04d}.roundtrip'
            vnvkr.delta(engine, 'decode', source, patch, check)
            if vnvkr.sha256(check) != target_hash:
                raise ValueError(f'xdelta roundtrip mismatch: {name}')
            stats = applied[name]
            entry['verified_delta'] = {
                'source_sha256': source_hash, 'target_sha256': target_hash,
                'target_size': target.stat().st_size,
                'payload': patch.relative_to(stage).as_posix(),
                'payload_sha256': vnvkr.sha256(patch),
                'translated': len(stats['changed']), 'unmatched': len(stats['missing']),
                'records_verified': len(stats['beforeHashes']),
                'verification': 'UTF8_and_CP1252_full_fresh_readback_completed'}
            verified += 1
        catalog['verified_delta_backend'] = 'xdelta3_exact_source_fast_path'
        catalog['verified_delta_files'] = verified
        vnvkr.write_json(stage / 'catalog.json', catalog)
        stage.rename(a.output)
    print({'verified_delta_files': verified, 'output': str(a.output)})


if __name__ == '__main__':
    main()
