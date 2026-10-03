"""Fully verify installed inactive optional plugin variants for release deltas."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import vnvkr
import vnvkr_yesman


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mo2-root',type=Path,required=True)
    p.add_argument('--profile',required=True)
    p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--job-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    inst=vnvkr.Installation(a.mo2_root,a.profile)
    catalog=vnvkr.read_json(a.catalog/'catalog.json')
    entries=[e for e in catalog['files'] if e['kind']=='plugin-records' and e.get('optional')]
    if a.job_root.exists() or a.output.exists():
        raise FileExistsError('Use fresh optional verification paths')
    a.job_root.mkdir(parents=True); a.output.mkdir(parents=True)
    report=[]
    for index,entry in enumerate(entries):
        source=vnvkr.contained(inst.mods,f"{entry['provider']}/{entry['path']}")
        if not source.is_file():
            report.append({'path':entry['path'],'provider':entry['provider'],'status':'not_installed'})
            continue
        before=vnvkr.sha256(source)
        files,stats=vnvkr_yesman.merge_plugins(
            inst,[entry],catalog,a.job_root/f'{index:02d}-{entry["path"]}',
            source_overrides={entry['path']:source})
        translated=files/entry['path']
        provider_dir=a.output/entry['provider']
        provider_dir.mkdir(parents=True,exist_ok=True)
        target=provider_dir/entry['path']
        shutil.copyfile(translated,target)
        if vnvkr.sha256(source)!=before:
            raise ValueError(f'Source changed: {source}')
        report.append({'path':entry['path'],'provider':entry['provider'],'status':'verified',
                       'source':str(source),'source_sha256':before,
                       'target':str(target),'target_sha256':vnvkr.sha256(target),
                       **stats[entry['path']]})
        print(json.dumps({'verified':entry['path'],'provider':entry['provider'],
                          'translated':stats[entry['path']]['translated']},ensure_ascii=False))
    vnvkr.write_json(a.output/'optional-verification.json',{'files':report})
    print(json.dumps({'optional_files':len(report),'output':str(a.output)},ensure_ascii=False))


if __name__=='__main__':
    main()
