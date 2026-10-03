"""Publish a previously full-verified native translation run without rerunning it."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile

import vnvkr
import vnvkr_fonts
import vnvkr_output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mo2-root', type=Path, required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--verified-dir', type=Path, required=True)
    parser.add_argument('--verified-originals', type=Path, required=True)
    parser.add_argument('--apply-json', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_name(args.output.name + '.report.json').exists():
        raise FileExistsError(args.output)
    installation = vnvkr.Installation(args.mo2_root, args.profile)
    catalog = vnvkr.read_json(args.catalog / 'catalog.json')
    applied = {row['plugin']: row for row in vnvkr.read_json(args.apply_json)['files']}
    active_entries = [e for e in catalog['files'] if e['kind'] == 'plugin-records'
                      and not e.get('optional') and e['path'].casefold() in installation.active_keys]
    expected = {e['path'] for e in active_entries}
    actual = {p.name for p in args.verified_dir.iterdir() if p.suffix.casefold() in {'.esp', '.esm'}}
    if expected != actual:
        raise ValueError(f'Verified plugin set mismatch: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}')
    for entry in active_entries:
        name = entry['path']
        current = installation.source(name)
        original = args.verified_originals / name
        translated = args.verified_dir / name
        if not original.is_file() or not translated.is_file():
            raise FileNotFoundError(name)
        if vnvkr.sha256(current) != vnvkr.sha256(original):
            raise ValueError(f'Installed source changed since verification: {name}')
        if name not in applied:
            raise ValueError(f'Missing verified apply statistics: {name}')
    report = {'mo2_root': str(installation.root), 'profile': installation.profile,
              'output': str(args.output.resolve()), 'created_utc': datetime.now(timezone.utc).isoformat(),
              'files': [], 'skipped': [], 'warnings': installation.warnings,
              'install_state': 'manual_copy_required', 'game_validation': 'not_run',
              'updated_plugin_backend': 'YesManAI/xEditLib',
              'native_verification': 'UTF8_and_CP1252_full_fresh_readback_completed'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vnvkr-publish-', dir=args.output.parent) as tmp:
        stage = Path(tmp) / 'Output'
        stage.mkdir()
        seen = set()
        for entry in catalog['files']:
            if entry.get('optional'):
                report['skipped'].append({'path': entry['path'], 'provider': entry.get('provider'),
                                          'reason': 'optional_variant_requires_separate_native_verification'})
                continue
            key = entry['path'].casefold()
            chain = installation.providers.get(key)
            if not chain or (entry['kind'] in {'plugin-records', 'plugin-copy'} and key not in installation.active_keys):
                report['skipped'].append({'path': entry['path'], 'reason': 'not_enabled_or_not_installed'})
                continue
            source = installation.source(entry['path'])
            relative = vnvkr_output.destination(installation, source, entry['path'])
            if relative.casefold() in seen:
                raise ValueError(f'Duplicate physical output: {relative}')
            seen.add(relative.casefold())
            target = vnvkr.contained(stage, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            result = {'path': entry['path'], 'output_path': relative,
                      'provider': chain[-1]['provider'], 'source_sha256': vnvkr.sha256(source),
                      'source_updated': vnvkr.sha256(source) != entry['baseline_sha256']}
            if entry['kind'] == 'plugin-records':
                row = applied[entry['path']]
                shutil.copyfile(args.verified_dir / entry['path'], target)
                result.update(translated=len(row['changed']), unmatched=len(row['missing']),
                              records_verified=len(row['beforeHashes']),
                              status='matched_text_only; full_native_readback_verified')
            elif entry['kind'] in {'ini', 'json'}:
                raw, stats = vnvkr_output.merge_loose(source, entry)
                target.write_bytes(raw)
                result.update(stats, status='merged_into_current_source')
            else:
                raise ValueError(f'Unsupported entry in verified publish: {entry["kind"]}')
            result['output_sha256'] = vnvkr.sha256(target)
            report['files'].append(result)
        if catalog.get('font_bundle'):
            font_files, font_status = vnvkr_fonts.build_fonts(
                installation, args.catalog, catalog['font_bundle'], stage, seen)
            report['files'].extend(font_files)
            report['fonts'] = font_status
        if catalog.get('asset_bundle'):
            asset_files, asset_status = vnvkr_output.build_assets(
                installation, args.catalog, catalog['asset_bundle'], stage, seen,
                report.get('fonts', {}).get('mod'))
            report['files'].extend(asset_files)
            report['assets'] = asset_status
        for row in report['files']:
            artifact = vnvkr.contained(stage, row['output_path'])
            if not artifact.is_file() or vnvkr.sha256(artifact) != row['output_sha256']:
                raise ValueError(f'Output readback failed: {row["output_path"]}')
        note = stage / '읽어주세요.txt'
        note.write_text('VNV 한국어 패치 테스트 출력물\n\nOutput\\mods의 내용을 VNV MO2 폴더에 복사하세요.\n'
                        '원본 VNV 설치 파일은 생성 과정에서 수정하지 않았습니다.\n'
                        'tNVSE 71 이상이 필요하며 tNVSE DLL은 이 출력물에 포함되지 않습니다.\n'
                        '비활성 선택 플러그인 3개는 별도 호환 검증 후 추가됩니다.\n', encoding='utf-8-sig')
        stage.rename(args.output)
    report_path = args.output.with_name(args.output.name + '.report.json')
    vnvkr.write_json(report_path, report)
    print(json.dumps({'files': len(report['files']), 'skipped': len(report['skipped']),
                      'output': str(args.output), 'report': str(report_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
