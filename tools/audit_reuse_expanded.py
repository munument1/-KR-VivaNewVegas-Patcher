"""Read-only exact English reuse when record IDs differ, and actor-tag review."""
import json,re
from pathlib import Path
from collections import defaultdict,Counter
from difflib import SequenceMatcher
from audit_remaining_translation import ROOT,DICTS,identity,recover,rows,HANGUL
from bgs_translator.sst import read_sst

OUT=ROOT/'reports/remaining_translation_audit'
TAG=re.compile(r'\{[^{}]*\}')
def strip_tags(text):return re.sub(r'\s+',' ',TAG.sub('',text)).strip()
def whitespace(text):return re.sub(r'\s+',' ',text).strip()
def punctuation(text):return re.sub(r'[^\w\s]','',whitespace(text)).casefold()

def main():
    target=[json.loads(x) for x in (OUT/'residual_player_candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    wanted={(x['canonical_identity'][0],x['signature'],x['field'],x['source']) for x in target}
    preferred=defaultdict(set)
    inspected=json.loads((ROOT/'reports/source_audit/fallout_nv_kr_inspect.json').read_text(encoding='utf-8'))
    data=inspected.get('data',inspected);masters=data['header']['masters']
    for r in rows(ROOT/'reports/source_audit/xtl_state/translator/projects/source-main/memory/memory.sqlite'):
        key=identity(r['formid'],masters,'Fallout NV KR.esm',r['signature'],r['field'],r['index_n'],r['index_max'])
        dest=recover(r['source'])
        if key and HANGUL.search(dest):preferred[key].add(dest)
    pool=defaultdict(list);tagpool=defaultdict(list)
    for path in sorted(DICTS.glob('*.sst')):
        dictionary=read_sst(path);own=dictionary.masters[-1] if dictionary.masters else path.stem+'.esp'
        for entry in dictionary.entries:
            key=identity(entry.formid,dictionary.masters,own,entry.signature,entry.field,entry.index,entry.index_max)
            if key is None:continue
            dest=entry.dest;method='existing_sst'
            if path.name=='fallout nv kr_en_ko.sst' and len(preferred.get(key,set()))==1:
                dest=next(iter(preferred[key]));method='preferred_kr_actual_text'
            if not HANGUL.search(dest) or '\ufffd' in dest:continue
            value={'old_canonical_identity':key,'old_english':entry.source,'existing_ko':dest,'dictionary':str(path),'translation_source':method}
            if (key[0],entry.signature,entry.field,entry.source) in wanted:
                pool[(key[0],entry.signature,entry.field,entry.source)].append(value)
            if entry.signature=='INFO' and entry.field=='NAM1':
                tagpool[(key[:5],strip_tags(entry.source))].append(value)
    exact=[];tags=[];ambiguous=[]
    for t in target:
        key=tuple(t['canonical_identity']);values=pool.get((key[0],t['signature'],t['field'],t['source']),[])
        unique={v['existing_ko'] for v in values}
        item={'plugin':t['plugin'],'formid':t['formid'],'canonical_identity':key,'target_english':t['source'],'signature':t['signature'],'field':t['field'],'index_n':t['index_n'],'index_max':t['index_max']}
        if len(unique)==1:
            # Full identity equals should have been covered; retain evidence either way.
            exact.append(dict(item,existing_ko=next(iter(unique)),status='exact_source_same_owner_signature_field_identity_changed_manual_review',evidence=values[:5]))
        elif len(unique)>1:
            ambiguous.append(dict(item,status='exact_source_same_owner_ambiguous_destination',candidate_translations=sorted(unique)))
        if t['signature']=='INFO' and t['field']=='NAM1':
            alternatives=tagpool.get((key[:5],strip_tags(t['source'])),[])
            ko={v['existing_ko'] for v in alternatives}
            if len(ko)==1 and alternatives:
                tags.append(dict(item,existing_ko=next(iter(ko)),current_actor_tags=TAG.findall(t['source']),status='actor_directions_stripped_same_record_occurrence_manual_review',evidence=alternatives[:5]))
    for name,entries in [('exact_source_identity_changed_review.jsonl',exact),('actor_direction_stripped_reuse_review.jsonl',tags),('exact_source_identity_changed_ambiguous.jsonl',ambiguous)]:
        with (OUT/name).open('w',encoding='utf-8') as f:
            for item in entries:f.write(json.dumps(item,ensure_ascii=False)+'\n')
    fuzzy=[json.loads(x) for x in (OUT/'fuzzy_reuse_pairs.jsonl').read_text(encoding='utf-8').splitlines()]
    fcounts=Counter()
    for pair in fuzzy:
        a,b=pair['old_english'],pair['target_english']
        if a==b:kind='identical_english'
        elif whitespace(a)==whitespace(b):kind='whitespace_only'
        elif strip_tags(a)==strip_tags(b):kind='actor_tags_only'
        elif punctuation(a)==punctuation(b):kind='punctuation_case_only'
        else:kind='word_or_actor_tag_changes'
        fcounts[kind]+=1;pair['difference_kind']=kind
        pair['diffs']=[{'operation':op,'old':a[i:j],'target':b[k:l]} for op,i,j,k,l in SequenceMatcher(None,a,b,autojunk=False).get_opcodes() if op!='equal']
    fuzzy.sort(key=lambda x:(x['difference_kind']=='word_or_actor_tag_changes',-x['similarity']))
    (OUT/'fuzzy_top20.json').write_text(json.dumps(fuzzy[:20],ensure_ascii=False,indent=2),encoding='utf-8')
    keys_exact={(x['plugin'],x['formid'],x['signature'],x['field'],x['index_n']) for x in exact}
    keys_tag={(x['plugin'],x['formid'],x['signature'],x['field'],x['index_n']) for x in tags}
    summary={'player_residual_units':len(target),'same_owner_exact_source_unique_ko':len(exact),'same_owner_exact_source_ambiguous':len(ambiguous),'same_record_actor_tag_stripped_unique_ko':len(tags),'combined_candidate_units':len(keys_exact|keys_tag),'fuzzy_difference_kinds':dict(fcounts),'remaining_after_review_candidates':len(target)-len(keys_exact|keys_tag)}
    (OUT/'expanded_reuse_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    for item in fuzzy[:20]:
        print(json.dumps({k:item[k] for k in ['plugin','target_english','old_english','existing_ko','difference_kind','diffs']},ensure_ascii=False))

if __name__=='__main__':main()
