"""Remove JSON-export child-group duplication; analyzes official API JSON only."""
import json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]/'reports/yesman_ai_audit'
def main():
    items=[json.loads(x) for x in (ROOT/'source_embedded_scripts.jsonl').read_text(encoding='utf-8').splitlines() if x]
    child=[x for x in items if x['script_path'].startswith('Child Group\\')]
    direct=[x for x in items if not x['script_path'].startswith('Child Group\\')]
    changes=[x for x in direct if x['native_block_equal'] is not True and (x['compiled_changed'] or x['source_text_changed'] or x['metadata_json_changed'])]
    for name,data in [('source_embedded_scripts.jsonl',direct),('script_differences.jsonl',changes),('excluded_child_group_duplicate_scripts.jsonl',child)]:
        (ROOT/name).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data),encoding='utf-8')
    summary=json.loads((ROOT/'script_audit_summary.json').read_text(encoding='utf-8'));counts=summary['counts']
    summary['child_group_duplicate_blocks_excluded']=len(child)
    counts.update(source_script_blocks=len(direct),source_nonempty_compiled_blocks=sum(bool(x['source_compiled_hex']) for x in direct),source_source_text_blocks=sum(bool(x['source_text']) for x in direct),source_source_text_hangul_blocks=sum(any('\uac00'<=c<='\ud7af' for c in x['source_text'] or '') for x in direct),source_script_blocks_different_from_current=len(changes),compiled_changed_blocks=sum(x['compiled_changed'] for x in changes),source_text_changed_blocks=sum(x['source_text_changed'] for x in changes),reference_or_metadata_changed_blocks=sum(x['metadata_json_changed'] for x in changes),script_records_with_changes=len({(x['source_file'],x['formid']) for x in changes}))
    for file in summary['source_files']:
        own=[x for x in direct if x['source_file']==file['file']];file['script_blocks']=len(own);file['nonempty_compiled_blocks']=sum(bool(x['source_compiled_hex']) for x in own)
    summary['metadata_comparison_limit']='Serialized references contain current containing filename; metadata_json_changed is not proof of functional changes. Native equality is recorded, array-path lookups may be unavailable. Child Group duplicate descendants are excluded.'
    (ROOT/'script_audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(counts,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
