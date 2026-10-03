"""Inventory human translation work without parsing or changing plugin records."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


def digest(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def text_read(path: Path):
    raw = path.read_bytes()
    encodings = ['utf-16'] if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ['utf-8-sig', 'cp949']
    for encoding in encodings:
        try:
            return raw.decode(encoding), encoding
        except UnicodeError:
            pass
    raise ValueError(f'Unknown text encoding: {path}')


def ini_summary(path: Path):
    text, encoding = text_read(path)
    section, entries = '', []
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith((';', '#')):
            continue
        if stripped.startswith('[') and stripped.endswith(']'):
            section = stripped[1:-1]
        elif '=' in line:
            key, value = line.split('=', 1)
            entries.append({'section': section, 'key': key.strip(), 'line': line_number,
                            'empty': not value.strip(), 'hangul': bool(re.search('[가-힣]', value)),
                            'message_prefix': bool(re.match(r'\s*"?#\d+\|', value)),
                            'percent_escape': '%%' in value})
    groups = {}
    for e in entries:
        groups.setdefault((e['section'], e['key']), []).append(e['line'])
    return {'encoding': encoding, 'entry_count': len(entries),
            'nonempty_entries': sum(not e['empty'] for e in entries),
            'hangul_entries': sum(e['hangul'] for e in entries),
            'message_prefix_entries': sum(e['message_prefix'] for e in entries),
            'percent_escape_entries': sum(e['percent_escape'] for e in entries),
            'duplicate_keys': [{'section': k[0], 'key': k[1], 'lines': v}
                               for k, v in groups.items() if len(v) > 1]}


def audit(workspace: Path, sst_dir: Path, output: Path):
    if output.exists():
        raise FileExistsError(f'Use a new output folder: {output}')
    manifest = json.loads((workspace / 'source_manifest.json').read_text(encoding='utf-8-sig'))
    dictionaries = [{'name': p.name, 'path': str(p), 'size': p.stat().st_size, 'sha256': digest(p)}
                    for p in sorted(sst_dir.glob('*.sst'))]
    indexed = {p['name'].casefold(): p for p in dictionaries}
    original_changed, rows = [], []
    for source in manifest['files']:
        category = source['category']
        if category not in {'01_Plugins', '99_Optional_Plugins'}:
            continue
        original = Path(source['source'])
        original_hash = digest(original) if original.is_file() else None
        if original_hash != source['sha256']:
            original_changed.append(source['output'])
        expected = workspace / source['output']
        completed = workspace / '01_Plugins' / '번역 완료' / Path(source['data_path']).name
        if category == '99_Optional_Plugins':
            current, status = expected, 'user_reported_completed_optional'
        elif completed.is_file():
            current, status = completed, 'completed_folder'
        elif expected.is_file():
            current, status = expected, 'remaining_folder'
        else:
            current, status = None, 'not_present_in_plugin_folders'
        current_hash = digest(current) if current and current.is_file() else None
        dictionary_name = Path(source['data_path']).stem.casefold() + '_en_ko.sst'
        dictionary = indexed.get(dictionary_name)
        rows.append({'category': category, 'plugin': source['data_path'], 'status': status,
                     'current_path': str(current) if current else None, 'current_sha256': current_hash,
                     'baseline_sha256': source['sha256'], 'original_source': str(original),
                     'original_sha256': original_hash,
                     'original_matches_baseline': original_hash == source['sha256'],
                     'changed_from_baseline': None if current_hash is None else current_hash != source['sha256'],
                     'enabled_profiles': source['enabled_profiles'],
                     'sst_filename_candidate': dictionary})
    mcm = [{'path': str(p.relative_to(workspace)), 'sha256': digest(p), 'size': p.stat().st_size}
           for p in sorted((workspace / '02_MCM').rglob('*')) if p.is_file()]
    translations = [{'path': str(p.relative_to(workspace)), 'sha256': digest(p), **ini_summary(p)}
                    for p in sorted((workspace / '03_Translations').rglob('*.ini'))]
    counts = dict(Counter(r['status'] for r in rows))
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'workspace': str(workspace),
              'sst_directory': str(sst_dir), 'counts': counts, 'plugins': rows,
              'baseline_source_mismatches': original_changed, 'mcm_remaining_files': mcm,
              'ini_translations': translations, 'sst_root_files': dictionaries,
              'limits': ['No plugin records or SST payloads parsed.',
                         'Completed is user folder/report status, not translation completeness proof.',
                         'SST matching is filename only; source strings and record identity are unverified.',
                         'No translations generated or modified; no game or MO2 changes.']}
    output.mkdir(parents=True)
    (output / 'intake.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 번역 작업 현황', '', '사용자 정리 상태와 파일 해시를 기록한 목록입니다. 번역률·레코드 보존·게임 호환성 검증 결과는 아닙니다.', '',
             f'- 완료 폴더: {counts.get("completed_folder", 0)}개',
             f'- 추가 작업 폴더: {counts.get("remaining_folder", 0)}개',
             f'- 플러그인 폴더에서 찾지 못한 항목: {counts.get("not_present_in_plugin_folders", 0)}개',
             f'- Optional: {counts.get("user_reported_completed_optional", 0)}개 (사용자가 모두 완료했다고 알림)',
             f'- MCM 추가 작업 파일: {len(mcm)}개', f'- INI 번역 사전: {len(translations)}개',
             f'- SST 루트 사전: {len(dictionaries)}개. Auto/Backup/백업 하위 폴더는 제외.',
             f'- 수집 당시와 설치 원본 해시가 다른 항목: {len(original_changed)}개', '',
             '## 플러그인과 SST', '', '| 파일 | 사용자 정리 상태 | 원본과 바이트 차이 | 같은 이름의 SST |',
             '|---|---|---|---|']
    labels = {'completed_folder': '완료 폴더', 'remaining_folder': '추가 작업 폴더',
              'not_present_in_plugin_folders': '폴더에 없음 / 확인 필요',
              'user_reported_completed_optional': 'Optional 완료 보고'}
    for row in rows:
        diff = '미확인' if row['changed_from_baseline'] is None else ('있음' if row['changed_from_baseline'] else '없음')
        lines.append(f'| {row["plugin"]} | {labels[row["status"]]} | {diff} | {row["sst_filename_candidate"]["name"] if row["sst_filename_candidate"] else "없음"} |')
    lines += ['', '바이트 차이가 없는 파일도 문자열이 없거나 번역 불필요한 파일일 수 있습니다. 완료 상태를 자동으로 번역 누락으로 판정하지 않습니다.', '',
              '## MCM 추가 작업', '']
    lines += [f'- `{r["path"]}`' for r in mcm]
    lines += ['', '## Translations INI', '', '| 파일 | 항목 / 빈 값 제외 | 보호 표기 / 중복 키 |', '|---|---|---|']
    for row in translations:
        warnings = []
        if row['message_prefix_entries']:
            warnings.append(f'#숫자\u007c 접두사 {row["message_prefix_entries"]}개')
        if row['percent_escape_entries']:
            warnings.append(f'%% {row["percent_escape_entries"]}개 항목')
        warnings += [f'{d["key"]} 중복 (줄 {", ".join(map(str, d["lines"]))})' for d in row['duplicate_keys']]
        lines.append(f'| {row["path"]} | {row["entry_count"]} / {row["nonempty_entries"]} | {"; ".join(warnings).replace(chr(124), "&#124;") or "없음"} |')
    lines += ['', '이 파일들은 `[Translations]` 또는 `[UII]` 아래의 INI `키=값` 사전입니다. xTranslator 설명서의 MCM/Translate는 SkyUI 계열을 설명하며, 여기의 INI 형식을 인식하는지는 실제 UI 시험 전까지 확인되지 않았습니다.', '',
              '작업 시 섹션 이름·키·순서·중복 키·따옴표·빈 값·줄바꿈을 유지하고 표시 문구만 번역합니다. `#0|`, `#5|`, `%%`, 서식 변수와 파일 경로는 유지합니다. ExtraGoodies.ini에는 같은 키가 여러 번 나오므로 INI 파서로 다시 저장해 항목을 합치지 않습니다.', '',
              '## 본편/DLC 사전 적용 문제', '',
              'FalloutNV.esm, DeadMoney.esm, OldWorldBlues.esm이 추가 작업 폴더에 있고 각각 같은 이름의 SST가 있습니다. HonestHearts.esm, LonesomeRoad.esm, GunRunnersArsenal.esm 및 시작 장비 팩 4개는 완료 폴더에 있습니다.', '',
              '문구가 달라져서 엄격 매칭이 실패한다는 설명은 가능하지만 아직 해당 SST 내용과 현행 레코드를 대조하지 않았습니다. 현재 설치본을 기준으로 원문 불일치·레코드 식별 불일치·사전 원천 부재를 구분해야 합니다. 유사 문자열 일괄 적용이나 새 번역은 수행하지 않았습니다.', '',
              '## 패쳐 반영 상태', '',
              '완료본은 입력 후보로 등록했습니다. 설치 원본과 번역본의 레코드/masters/스크립트 보존을 확인하기 전에는 검수 완료로 표시하거나 릴리스 번들에 넣지 않습니다. Optional 파일은 기본 번들에 자동 포함하지 않으며 실제 활성 원본 제공자에 맞게 별도 관리합니다.', '']
    (output / '번역작업현황.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'counts': counts, 'mcm': len(mcm), 'ini': len(translations),
                      'sst': len(dictionaries), 'original_mismatches': original_changed,
                      'output': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--sst-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.workspace.resolve(), args.sst_dir.resolve(), args.output.resolve())
