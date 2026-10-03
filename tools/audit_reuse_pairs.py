"""Produce manual-only reuse pairs from extracted SQLite-derived JSON and SSTs."""
import json,re
from pathlib import Path
from collections import defaultdict,Counter
from difflib import SequenceMatcher
from bgs_translator.sst import read_sst
from audit_remaining_translation import identity,recover,HANGUL,DICTS,ROOT

OUT=ROOT/'reports/remaining_translation_audit'

def norm(text):return re.sub(r'\s+',' ',text).strip().casefold()

def lock_reason(entry):
    sig,field,source=entry['signature'],entry['field'],entry['source'].strip()
    if sig=='TES4':return 'plugin_author_description_metadata'
    if (sig,field)==('INFO','NAM2'):return 'actor_direction_notes'
    if sig in ('MSET','ALOC','AMEF','EXPL','PROJ','ARMA','WATR'):return 'technical_record_display_review'
    if not re.search(r'[A-Za-z\uac00-\ud7af]',source):return 'only_punctuation_numeric_or_empty'
    if source==entry.get('edid'):return 'identical_editorid'
    if re.fullmatch(r'\{[^{}]*\}',source):return 'only_actor_direction_braces'
    if not re.search(r'\s',source) and re.search(r'[a-z][A-Z][a-z]+[A-Z]',source):return 'camelcase_internal_identifier_review'
    if source.startswith(('AudioTemplate','VCG','VDialogue','musSet','DEFAULT')):return 'internal_identifier_review'
    return None

def main():
    residual=[json.loads(x) for x in (OUT/'residual.jsonl').read_text(encoding='utf-8').splitlines()]
    keys={tuple(x['canonical_identity']) for x in residual if x['canonical_identity']}
    corekeys={k[:5] for k in keys}
    oldrows=defaultdict(set)
    # Actual preferred recovered text, not possibly corrupt SST destination.
    from audit_remaining_translation import rows
    inspect=json.loads((ROOT/'reports/source_audit/fallout_nv_kr_inspect.json').read_text(encoding='utf-8'))
    data=inspect.get('data',inspect);masters=data['header']['masters']
    for row in rows(ROOT/'reports/source_audit/xtl_state/translator/projects/source-main/memory/memory.sqlite'):
        key=identity(row['formid'],masters,'Fallout NV KR.esm',row['signature'],row['field'],row['index_n'],row['index_max'])
        dest=recover(row['source'])
        if key and HANGUL.search(dest):oldrows[key].add(dest)
    older=defaultdict(list)
    for path in DICTS.glob('*.sst'):
        dictionary=read_sst(path);own=dictionary.masters[-1] if dictionary.masters else path.stem+'.esp'
        for entry in dictionary.entries:
            key=identity(entry.formid,dictionary.masters,own,entry.signature,entry.field,entry.index,entry.index_max)
            if not key or key[:5] not in corekeys:continue
            dest=entry.dest;method='supplied_sst_existing_translation'
            if path.name=='fallout nv kr_en_ko.sst' and len(oldrows.get(key,[]))==1:
                dest=next(iter(oldrows[key]));method='preferred_kr_actual_text_with_old_sst_english'
            if HANGUL.search(dest) and '\ufffd' not in dest:
                older[key].append((entry.source,dest,str(path),method))
    fuzzy=[];player=[];locked=[];unique=defaultdict(list)
    for entry in residual:
        reason=lock_reason(entry)
        if reason:
            locked.append(dict(entry,review_lock_reason=reason));continue
        player.append(entry);unique[(entry['signature'],entry['field'],entry['source'])].append(entry)
        key=tuple(entry['canonical_identity']);matches=older.get(key,[]);identity_method='full_canonical_identity'
        if not matches:
            alternate=[pair for other,values in older.items() if other[:5]==key[:5] for pair in values]
            # Only one older-English/Korean pair allows ignoring maximum; never omit occurrence index.
            if len(set((a,b) for a,b,*_ in alternate))==1:
                matches=alternate;identity_method='same_occurrence_unique_pair_indexmax_changed'
        seen=set()
        for source,dest,path,method in matches:
            if (source,dest) in seen:continue
            seen.add((source,dest))
            ratio=SequenceMatcher(None,norm(source),norm(entry['source']),autojunk=False).ratio()
            if ratio>=0.85:
                fuzzy.append({'plugin':entry['plugin'],'formid':entry['formid'],'canonical_identity':key,'signature':entry['signature'],'field':entry['field'],'index_n':entry['index_n'],'index_max':entry['index_max'],'old_english':source,'target_english':entry['source'],'existing_ko':dest,'similarity':ratio,'source_dictionary':path,'method':method,'identity_method':identity_method,'status':'manual_semantic_review_only'})
    for name,entries in [('fuzzy_reuse_pairs.jsonl',fuzzy),('residual_player_candidates.jsonl',player),('residual_lock_review.jsonl',locked)]:
        with (OUT/name).open('w',encoding='utf-8') as f:
            for entry in entries:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
    with (OUT/'residual_player_unique.jsonl').open('w',encoding='utf-8') as f:
        for (sig,field,source),entries in unique.items():
            f.write(json.dumps({'signature':sig,'field':field,'source':source,'count':len(entries),'examples':entries[:3]},ensure_ascii=False)+'\n')
    summary={'residual_units':len(residual),'player_candidate_units':len(player),'player_unique_field_texts':len(unique),'lock_review_units':len(locked),'lock_review_reasons':dict(Counter(x['review_lock_reason'] for x in locked)),'fuzzy_pairs_manual_only':len(fuzzy),'fuzzy_distinct_target_units':len(set((x['plugin'],x['formid'],x['signature'],x['field'],x['index_n']) for x in fuzzy))}
    (OUT/'reuse_review_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
