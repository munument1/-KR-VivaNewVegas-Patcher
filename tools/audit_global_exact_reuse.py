"""Read-only global exact English reuse; human reviews contextual scope changes."""
import json
from collections import defaultdict,Counter
from audit_remaining_translation import ROOT,DICTS,identity,recover,rows,HANGUL
from bgs_translator.sst import read_sst

OUT=ROOT/'reports/remaining_translation_audit'
def main():
    targets=[json.loads(x) for x in (OUT/'residual_player_candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    texts={x['source'] for x in targets};verified=defaultdict(set)
    inspect=json.loads((ROOT/'reports/source_audit/fallout_nv_kr_inspect.json').read_text(encoding='utf-8'));data=inspect.get('data',inspect)
    for r in rows(ROOT/'reports/source_audit/xtl_state/translator/projects/source-main/memory/memory.sqlite'):
        key=identity(r['formid'],data['header']['masters'],'Fallout NV KR.esm',r['signature'],r['field'],r['index_n'],r['index_max']);dest=recover(r['source'])
        if key and HANGUL.search(dest):verified[key].add(dest)
    pool=defaultdict(list)
    for path in sorted(DICTS.glob('*.sst')):
        dictionary=read_sst(path);own=dictionary.masters[-1] if dictionary.masters else path.stem+'.esp'
        for e in dictionary.entries:
            if e.source not in texts:continue
            key=identity(e.formid,dictionary.masters,own,e.signature,e.field,e.index,e.index_max)
            dest=e.dest;preferred=False
            if path.name=='fallout nv kr_en_ko.sst' and key and len(verified.get(key,set()))==1:
                dest=next(iter(verified[key]));preferred=True
            if HANGUL.search(dest) and '\ufffd' not in dest:
                pool[e.source].append({'source_dictionary':str(path),'signature':e.signature,'field':e.field,'old_canonical_identity':key,'existing_ko':dest,'preferred_kr_actual_text':preferred})
    candidates=[];conflicts=[]
    for t in targets:
        values=pool.get(t['source'],[])
        preferred=[v for v in values if v['preferred_kr_actual_text']]
        samefield=[v for v in values if v['signature']==t['signature'] and v['field']==t['field']]
        levels=[('preferred_kr_exact_english',preferred),('exact_english_same_signature_field',samefield),('global_exact_english',values)]
        chosen=None
        for method,group in levels:
            if not group:continue
            destinations={v['existing_ko'] for v in group}
            if len(destinations)==1:
                chosen=(method,next(iter(destinations)),group);break
            # Preferred translations conflicting cannot be replaced by unrelated less reliable data.
            if method=='preferred_kr_exact_english':break
        base={k:t[k] for k in ['plugin','formid','canonical_identity','signature','field','index_n','index_max','source']}
        if chosen:
            method,dest,evidence=chosen
            candidates.append(dict(base,status='global_exact_source_manual_context_review',method=method,dest=dest,evidence=evidence[:8],other_destinations=sorted({v['existing_ko'] for v in values}-{dest})))
        elif values:conflicts.append(dict(base,status='ambiguous_global_exact_english',destinations=sorted({v['existing_ko'] for v in values}),evidence=values[:8]))
    for name,items in [('global_exact_source_review.jsonl',candidates),('global_exact_source_conflicts.jsonl',conflicts)]:
        with (OUT/name).open('w',encoding='utf-8') as f:
            for item in items:f.write(json.dumps(item,ensure_ascii=False)+'\n')
    summary={'target_units':len(targets),'candidate_units':len(candidates),'candidate_unique_texts':len({x['source'] for x in candidates}),'methods':dict(Counter(x['method'] for x in candidates)),'conflict_units':len(conflicts),'remaining_units_without_unique_global_exact':len(targets)-len(candidates)}
    (OUT/'global_exact_source_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
