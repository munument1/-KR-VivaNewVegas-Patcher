"""Attach exact-version deltas for fully verified optional variants."""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import vnvkr


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--verification',type=Path,required=True)
    a=p.parse_args()
    catalog_path=a.catalog/'catalog.json'
    catalog=vnvkr.read_json(catalog_path)
    report=vnvkr.read_json(a.verification/'optional-verification.json')
    engine=vnvkr.engine(None)
    delta_dir=a.catalog/'native-deltas'; delta_dir.mkdir(exist_ok=True)
    attached=0
    with tempfile.TemporaryDirectory(prefix='.optional-delta-',dir=a.catalog) as temp:
        temp=Path(temp)
        for index,row in enumerate(report['files']):
            if row['status']!='verified': continue
            entry=next(e for e in catalog['files'] if e.get('optional') and
                       e.get('provider')==row['provider'] and e['path']==row['path'])
            source=Path(row['source']); target=Path(row['target'])
            if vnvkr.sha256(source)!=row['source_sha256'] or vnvkr.sha256(target)!=row['target_sha256']:
                raise ValueError(f'Optional verification artifact changed: {row["path"]}')
            patch=delta_dir/f'optional-{index:02d}.vcdiff'
            if patch.exists(): patch.unlink()
            vnvkr.delta(engine,'encode',source,target,patch)
            check=temp/f'{index:02d}.roundtrip'
            vnvkr.delta(engine,'decode',source,patch,check)
            if vnvkr.sha256(check)!=row['target_sha256']:
                raise ValueError(f'Optional xdelta roundtrip mismatch: {row["path"]}')
            entry['verified_delta']={
                'source_sha256':row['source_sha256'],'target_sha256':row['target_sha256'],
                'target_size':target.stat().st_size,'payload':patch.relative_to(a.catalog).as_posix(),
                'payload_sha256':vnvkr.sha256(patch),'translated':row['translated'],
                'unmatched':row['unmatched'],'records_verified':row['records_verified'],
                'verification':row['verification']}
            attached+=1
    catalog['verified_delta_files']=sum(1 for e in catalog['files'] if e.get('verified_delta'))
    vnvkr.write_json(catalog_path,catalog)
    print({'optional_attached':attached,'verified_delta_files':catalog['verified_delta_files']})


if __name__=='__main__':
    main()
