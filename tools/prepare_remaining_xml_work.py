"""Prepare reviewed textual reuse from official xtl extraction and SST reader."""
import json, re
from collections import defaultdict, Counter
from audit_remaining_translation import ROOT, OUT, DICTS, HANGUL, recover, identity, rows
from audit_reuse_pairs import lock_reason
from bgs_translator.sst import read_sst

WORK=ROOT/'reports/remaining_xml_work_20261003'
def norm(t):
    return re.sub(r'\s+', ' ', re.sub(r'\{[^{}]*\}', '',t)).strip().casefold()
def load(name):return [json.loads(s) for s in (OUT/name).read_text(encoding='utf-8').splitlines()]
def key(r):return (r['plugin'],r['formid'],r['signature'],r['field'],r['index_n'])
def main():
    WORK.mkdir(exist_ok=True)
    pool=defaultdict(list)
    info=json.loads((ROOT/'reports/source_audit/fallout_nv_kr_inspect.json').read_text(encoding='utf-8'))
    masters=info.get('data',info)['header']['masters'];preferred=defaultdict(set)
    for r in rows(ROOT/'reports/source_audit/xtl_state/translator/projects/source-main/memory/memory.sqlite'):
        k=identity(r['formid'],masters,'Fallout NV KR.esm',r['signature'],r['field'],r['index_n'],r['index_max'])
        d=recover(r['source'])
        if k and HANGUL.search(d):preferred[k].add(d)
    for p in sorted(DICTS.glob('*.sst')):
        s=read_sst(p)
        for e in s.entries:
            d=e.dest;priority=1
            if p.name=='fallout nv kr_en_ko.sst':
                k=identity(e.formid,s.masters,'Fallout NV KR.esm',e.signature,e.field,e.index,e.index_max)
                if len(preferred.get(k,set()))==1:d=next(iter(preferred[k]));priority=0
            if HANGUL.search(d) and '\ufffd' not in d:
                pool[(e.signature,e.field,norm(e.source))].append((priority,d,p.name,e.source))
    candidates=load('candidates.jsonl')
    native=json.loads((WORK/'native_remaining.json').read_text(encoding='utf-8'))
    notes=json.loads((WORK/'note_body.json').read_text(encoding='utf-8'))
    for f,n in zip(native['files'],notes['files']):
        assert f['plugin']==n['plugin']
        f['rows'].extend(n['rows'])
    # SSTs supply xTranslator occurrence metadata even for fields omitted by xtl.
    for f in native['files']:
        p=DICTS/(f['plugin'].rsplit('.',1)[0].lower()+'_en_ko.sst')
        s=read_sst(p);indexmap=defaultdict(list)
        for e in s.entries:
            k=identity(e.formid,s.masters,f['plugin'],e.signature,e.field,e.index,e.index_max)
            if k:indexmap[(k[:4],e.source)].append(e)
        byrecord=defaultdict(list)
        for r in f['rows']:byrecord[(r['owner'],r['id'],r['signature'],r['field'])].append(r)
        for rs in byrecord.values():
            for i,r in enumerate(rs):
                k=(r['owner'],int(r['id'],16),r['signature'],r['field'])
                es=indexmap.get((k,r['source']),[])
                e=es[0] if len(es)==1 else None
                slot=f['masters'].index(next(m for m in f['masters'] if m.casefold()==r['owner'])) if r['owner']!=f['plugin'].casefold() else len(f['masters'])
                candidates.append(dict(plugin=f['plugin'],formid=(slot<<24)|k[1],signature=r['signature'],field=r['field'],index_n=e.index if e else i,index_max=e.index_max if e else len(rs)-1,list_index=e.list_index if e else 0,strid=0,edid=r['edid'],source=r['source'],normalized_source=r['source'],canonical_identity=[*k,e.index if e else i,e.index_max if e else len(rs)-1],status='native_schema_supplement',dest=None,native_path=r['path'],occurrence_provenance='supplied_sst' if e else 'native_subrecord_order'))
    fuzzy=defaultdict(list)
    for r in load('fuzzy_reuse_pairs.jsonl'):fuzzy[key(r)].append(r)
    # All inspected fuzzy pairs are wording-equivalent except added player Attack prefix.
    # The hologram-rifle optical rename has conflicting translations, handled manually.
    accepted=[];pending=[];locked=[]
    for r in candidates:
        why=lock_reason(r)
        if why:locked.append(dict(r,reason=why));continue
        if r['status']=='already_korean' or HANGUL.search(r['normalized_source']):accepted.append(dict(r,dest=r['normalized_source'],method='user_existing_korean'));continue
        if r['dest'] and 'identity_only' not in r['status']:
            accepted.append(dict(r,method=r['status']));continue
        values=pool.get((r['signature'],r['field'],norm(r['source'])),[])
        if values:
            priority=min(v[0] for v in values);vs=[v for v in values if v[0]==priority]
            ds={v[1] for v in vs}
            if len(ds)==1:
                accepted.append(dict(r,dest=next(iter(ds)),method='reviewed_normalized_source_reuse',evidence=vs[:3]));continue
        matches=fuzzy.get(key(r),[])
        if matches and not r['source'].startswith('[Attack]'):
            ds={v['existing_ko'] for v in matches}
            if len(ds)==1:
                accepted.append(dict(r,dest=next(iter(ds)),method='reviewed_equivalent_wording_reuse',evidence=matches[:2]));continue
        # Dummy enchantments, triggers, quest result notes and debug topic labels are internal.
        if ('Dummy' in r['source'] and r['signature']=='ENCH') or (r['signature']=='QUST' and r['field']=='CNAM') or r['source'] in ('EDEChatter','RadioBMSegment05','Lucky 38 Entrance Dialogue','Hidden Valley Self-Destruct Sequence','DLC Enhancements Cell') or (r['signature']=='ACTI' and 'Trigger' in r['source']) or (r['signature']=='DIAL' and r['source'].startswith('< Joshua Graham')):
            locked.append(dict(r,reason='reviewed_internal_debug_or_script_label'));continue
        pending.append(r)
    unique={}
    for r in pending:
        k=(r['signature'],r['field'],r['source'])
        if k not in unique:unique[k]=dict(id=len(unique),signature=k[0],field=k[1],source=k[2],plugin=r['plugin'],edid=r.get('edid'))
    for n,rs in [('accepted',accepted),('pending',pending),('locked',locked),('unique',list(unique.values()))]:
        (WORK/(n+'.json')).write_text(json.dumps(rs,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'accepted':len(accepted),'pending_units':len(pending),'unique':len(unique),'internal':len(locked),'by_plugin':dict(Counter(r['plugin'] for r in pending))},ensure_ascii=False))
    for r in unique.values():print(r['id'],r['signature']+':'+r['field'],json.dumps(r['source'],ensure_ascii=False))
if __name__=='__main__':main()
