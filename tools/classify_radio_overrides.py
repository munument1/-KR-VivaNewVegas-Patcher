"""Compare official API JSONL snapshots only; no plugin binary reads or writes."""
import json,re,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'reports/yesman_ai_audit'
def read(name):return [json.loads(x)for x in (OUT/name).read_text(encoding='utf-8').splitlines()]
vnv=read('radio_override_vnv_snapshots.jsonl');steam={r['key']:r for r in read('radio_override_steam_snapshots.jsonl')};owned=read('radio_override_vnv_owned.jsonl')
HANGUL=re.compile('[\uac00-\ud7af]')
def diffs(a,b):return [{'path':p,'a':a.get(p),'b':b.get(p)}for p in sorted(a.keys()|b.keys())if a.get(p)!=b.get(p) and p!='Record Header\\Record Flags']
def display(d,sig):
    f=(d['a']or d['b']or{}).get('field'); vt=(d['a']or d['b']or{}).get('vt')
    return vt in [3,4] and (f in ['FULL','DESC','NAM1','TDUM','ITXT'] or sig=='GMST'and f=='DATA')
def script(path):return path.startswith('Script (Begin)')or path.startswith('Script (End)')
def scriptsnap(fields,prefix):return {p:v for p,v in fields.items()if p.startswith(prefix+'\\')}
rows=[];stats=collections.Counter();by_sig=collections.Counter();script_plans=[];text_pairs=[];roots=collections.Counter();unresolved=collections.Counter()
for r in vnv:
    source=r['source']['fields'];current=r['current']['fields'];base=steam[r['key']]['current']['fields'];sig=r['identity']['signature']; ds=diffs(source,current);radio_delta=diffs(source,base);vnv_delta=diffs(current,base)
    text=[d for d in ds if display(d,sig)];notes=[d for d in ds if (d['a']or d['b']or{}).get('field')in['NAM2','NAM3']]; nontext=[d for d in ds if d not in text and d not in notes]
    sd=[d for d in nontext if script(d['path'])];other=[d for d in nontext if not script(d['path'])];links=[d for d in other if (d['a']or d['b']or{}).get('vt')==5]
    if not ds:category='identical_core_fields'
    elif not nontext:category='text_or_notes_only'
    elif sd or links:category='script_or_link_changes'
    else:category='other_nontext_changes'
    stats[category]+=1;by_sig[(sig,category)]+=1
    owned_refs=[ref for ref in r['source']['refs']if ref['target']['owner']=='NVKOR Radio + UI.esp']; stats['override_owned_reference_edges']+=len(owned_refs)
    if owned_refs:stats['override_records_referencing_owned_forms']+=1
    for d in nontext:roots[d['path'].split('\\')[0]]+=1
    for side in ['source','current']:
        unresolved[side]+=sum(bool(v.get('unresolved'))for v in r[side]['fields'].values())
    plans=[]
    for prefix in ['Script (Begin)','Script (End)']:
        s=scriptsnap(source,prefix);c=scriptsnap(current,prefix);b=scriptsnap(base,prefix)
        if s==c:continue
        if s==b:policy='keep_vnv_script_radio_does_not_change_steam_block'
        elif c==b:policy='radio_changes_block_vnv_matches_steam_read_only_copy_candidate'
        else:policy='both_changed_manual_script_merge_and_valid_compilation_required'
        plan={'record':r['key'],'identity':r['identity'],'edid':r['edid'],'winner':r['winner'],'script_block':prefix,'policy':policy,'source_sctx':[v['value']for v in s.values()if v.get('field')=='SCTX'],'current_sctx':[v['value']for v in c.values()if v.get('field')=='SCTX'],'steam_sctx':[v['value']for v in b.values()if v.get('field')=='SCTX'],'source_compiled':[v['value']for v in s.values()if v.get('field')=='SCDA'],'current_compiled':[v['value']for v in c.values()if v.get('field')=='SCDA'],'steam_compiled':[v['value']for v in b.values()if v.get('field')=='SCDA'],'source_references':[v['value']for v in s.values()if v.get('vt')==5],'current_references':[v['value']for v in c.values()if v.get('vt')==5]}
        plans.append(plan);script_plans.append(plan)
    for d in text:
        if d['a']and d['b']and HANGUL.search(str(d['a']['value'])):
            text_pairs.append({'identity':r['identity'],'edid':r['edid'],'winner':r['winner'],'path':d['path'],'field':d['a']['field'],'sourceEnglish':d['b']['value'],'dest':d['a']['value']})
    rows.append({'identity':r['identity'],'key':r['key'],'edid':r['edid'],'winner':r['winner'],'category':category,'source_vs_current':ds,'source_vs_steam':radio_delta,'current_vs_steam':vnv_delta,'display_changes':len(text),'script_changes':len(sd),'link_changes':len(links),'other_nontext_changes':len(other)-len(links),'source_owned_reference_edges':owned_refs,'script_block_policies':[{'block':p['script_block'],'policy':p['policy']}for p in plans]})
same=[r for r in owned if 'same_edid_current'in r];same_rows=[]
for r in same:
    data=r['source']['fields'].get('DATA');c=r['same_edid_current'];same_rows.append({'source_identity':r['identity'],'edid':r['edid'],'source_data':data['value']if data else None,'source_value_type':data['vt']if data else None,'current':c,'has_korean':bool(data and HANGUL.search(str(data['value']))),'policy':'Review Korean string semantics; map DATA into current GMST winner by unique EDID and type=string. Retain current FormID and metadata. Do not create a duplicate setting automatically.'})
for name,data in [('radio_override_classification.jsonl',rows),('radio_override_script_block_plans.jsonl',script_plans),('radio_override_translation_pairs.jsonl',text_pairs),('radio_override_same_edid_gmst_review.jsonl',same_rows)]:
    (OUT/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n'for r in data),encoding='utf-8')
summary={'read_only':True,'save_file_called':False,'override_records':len(rows),'classifications':dict(stats),'classifications_by_signature':{'|'.join(k):v for k,v in by_sig.items()},'changed_nontext_roots':dict(roots),'script_block_policies':dict(collections.Counter(p['policy']for p in script_plans)),'compiled_changed_blocks':sum(p['source_compiled']!=p['current_compiled']for p in script_plans),'script_ref_table_changed_blocks':sum(p['source_references']!=p['current_references']for p in script_plans),'existing_override_korean_text_pairs':len(text_pairs),'same_edid_gmst':len(same_rows),'same_edid_gmst_types':dict(collections.Counter(str(r['source_value_type'])for r in same_rows)),'same_edid_gmst_korean':sum(r['has_korean']for r in same_rows),'source_owned_gmst_without_current_edid':sum(r['identity']['signature']=='GMST'and'same_edid_current'not in r for r in owned),'source_owned_functional_non_gmst':sum(r['identity']['signature']!='GMST'for r in owned),'unresolved_reference_leaves':dict(unresolved),'source_quest_overrides':0,'caveats':['Steam comparison uses copies of currently installed Steam-directory masters, not authenticated pristine game files.','Flattened array occurrence diffs are diagnostic; remap references and ordered arrays by canonical identity before building a patch.','INFO Topic pseudo-field is not in native getElements snapshot; own INFO parent/topic relationships must also be retained.','Script blocks include compiled bytes and ordered SCRO references exposed by official API; no opcode parsing or compilation performed.','Record Header flags excluded from categories because compression/container metadata can differ. Preserve current winning flags when merging.','Raw zero FormID leaf resolution failures are counted and retained; no unresolved leaf is auto-remapped.','No in-game radio playback/subtitle verification.']}
(OUT/'radio_override_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
