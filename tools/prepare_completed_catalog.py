"""Assemble user-completed text mappings; plugin binaries are never packaged."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vnvkr
import vnvkr_yesman


def identity(row):
    return row['owner'], row['id'], row['signature'], row['path']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--recovery', type=Path, required=True)
    parser.add_argument('--optional', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    maps = vnvkr.read_json(args.intake / 'engine_accepted_mappings.json')
    recovered = vnvkr.read_json(args.recovery / 'source_override_candidates.json')['mappings']
    corrections = vnvkr.read_json(args.recovery / 'protected_token_translation_proposals.json')
    report = {'validation_scope': 'text_only_candidate', 'nontext_verified': False,
              'output_verification': 'fresh_UTF8_and_CP1252_structure_readback_required',
              'source_encoding_recovered': 0, 'protected_text_corrections': [], 'optional_mappings': {}}
    additions = {}
    for row in [*recovered, *corrections]:
        vnvkr_yesman.validate_mapping(row)
        additions.setdefault(row['plugin'], []).append(row)
        maps['mappings'][row['plugin']].append(row)
        if row in corrections:
            report['protected_text_corrections'].append(row)
        else:
            report['source_encoding_recovered'] += 1
    optional = vnvkr.read_json(args.optional / 'mappings_candidate.json')
    optional_report = {(r['provider'], r['plugin']): r for r in optional['report']}
    for entry in optional['entries']:
        rows = list(entry['mappings'])
        # Matching current English is still mandatory at runtime. Reuse only
        # corrections/recoveries with the same canonical record and field path.
        rejected = {identity(row): row for row in optional_report[(entry['provider'], entry['plugin'])]['rejected']}
        for row in additions.get(entry['plugin'], []):
            if identity(row) in rejected:
                candidate = dict(row)
                if row not in corrections:
                    candidate['dest'] = rejected[identity(row)]['dest']
                rows.append(candidate)
        for row in rows:
            vnvkr_yesman.validate_mapping(row)
        optional_key = entry['provider'] + '/' + entry['plugin']
        report['optional_mappings'][optional_key] = rows
    result = {**maps, **report}
    result['report'] = [{'plugin': name, 'mappings': len(rows), 'validation_scope': 'text_only_candidate'}
                        for name, rows in result['mappings'].items()]
    result['input_files'] = {str(p): vnvkr.sha256(p) for p in (
        args.intake / 'engine_accepted_mappings.json', args.recovery / 'source_override_candidates.json',
        args.recovery / 'protected_token_translation_proposals.json', args.optional / 'mappings_candidate.json')}
    vnvkr.write_json(args.output, result)
    print({'plugins': len(result['mappings']), 'active_mappings': sum(map(len, result['mappings'].values())),
           'optional_variants': len(result['optional_mappings']),
           'optional_mappings': sum(map(len, result['optional_mappings'].values()))})


if __name__ == '__main__':
    main()
