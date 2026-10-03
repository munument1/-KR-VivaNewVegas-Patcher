"""Read-only xtl CLI extraction and installed SST reader; no plugin binary parser."""
import os, json, re, sqlite3, subprocess, hashlib
from pathlib import Path
from collections import defaultdict, Counter
from bgs_translator.sst import read_sst

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports'/'remaining_translation_audit'
STATE=OUT/'xtl_state'
PLUGINS=ROOT/'VNV_Translation_Workspace'/'01_Plugins'
DICTS=Path(r'F:\번역\프로그램\xTranslator\UserDictionaries\FalloutNV')
HANGUL=re.compile(r'[\uac00-\ud7af\u3130-\u318f]')

def run_cli(args):
    env=os.environ.copy(); env['BGS_MODDING_SUPERPOWERS_HOME']=str(STATE);env['PYTHONIOENCODING']='utf-8'
    p=subprocess.run([str(ROOT/'.venv/Scripts/xtl.exe'),*args],capture_output=True,text=True,encoding='utf-8',env=env,check=True)
    result=json.loads(p.stdout)
    if not result['ok']:raise ValueError(result)
    return result['data']

def rows(db):
    con=sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True);con.row_factory=sqlite3.Row
    result=[dict(r) for r in con.execute('select * from units order by rowid')];con.close();return result

def recover(text):
    try: return text.encode('cp1252').decode('utf-8')
    except UnicodeError:return text

def identity(formid,masters,plugin,sig,field,index,indexmax):
    slot=formid>>24
    if slot<len(masters): owner=masters[slot]
    elif slot==len(masters):owner=plugin
    else:return None
    return (owner.casefold(),formid&0xffffff,sig,field,index,indexmax)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    old_inspect=json.loads((ROOT/'reports/source_audit/fallout_nv_kr_inspect.json').read_text(encoding='utf-8'))
    old_data=old_inspect.get('data',old_inspect)
    print('old inspect keys',list(old_data),flush=True)
    oldmasters=old_data.get('masters',old_data.get('header',{}).get('masters'))
    if oldmasters is None:raise ValueError('No masters in old inspect')
    old=defaultdict(list)
    for row in rows(ROOT/'reports/source_audit/xtl_state/translator/projects/source-main/memory/memory.sqlite'):
        dest=recover(row['source'])
        if HANGUL.search(dest):
            key=identity(row['formid'],oldmasters,'Fallout NV KR.esm',row['signature'],row['field'],row['index_n'],row['index_max'])
            if key:old[key].append({'dest':dest,'formid':row['formid'],'edid':row['edid']})
    preferred_english=defaultdict(set)
    preferred_sst=read_sst(DICTS/'fallout nv kr_en_ko.sst')
    for entry in preferred_sst.entries:
        key=identity(entry.formid,preferred_sst.masters,'Fallout NV KR.esm',entry.signature,entry.field,entry.index,entry.index_max)
        if key:preferred_english[key].add(entry.source)
    global_exact=defaultdict(set)
    occurrence_changed=defaultdict(set)
    sst_inventory=[]
    for sst_path in sorted(DICTS.glob('*.sst')):
        dictionary=read_sst(sst_path)
        name=sst_path.name.removesuffix('_en_ko.sst')
        own=dictionary.masters[-1] if dictionary.masters else name+'.esp'
        sst_inventory.append({'path':str(sst_path),'version':dictionary.label,'masters':dictionary.masters,'entries':len(dictionary.entries),'sha256':hashlib.sha256(sst_path.read_bytes()).hexdigest()})
        for entry in dictionary.entries:
            if not HANGUL.search(entry.dest) or '\ufffd' in entry.dest:continue
            key=identity(entry.formid,dictionary.masters,own,entry.signature,entry.field,entry.index,entry.index_max)
            if key:
                global_exact[(key,entry.source)].add(entry.dest)
                occurrence_changed[(key[:4],entry.source)].add(entry.dest)
    (OUT/'sst_inventory.json').write_text(json.dumps(sst_inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    output=[];findings=[];residual=[]
    for n,path in enumerate(sorted(PLUGINS.glob('*'))):
        if path.suffix.lower() not in {'.esp','.esm'}:continue
        slug='remaining-'+re.sub('[^a-z0-9]+','-',path.stem.casefold()).strip('-')
        inspectpath=OUT/(slug+'.inspect.json')
        if inspectpath.exists(): info=json.loads(inspectpath.read_text(encoding='utf-8'))
        else:
            info=run_cli(['inspect','plugin',str(path),'--game','FalloutNV']);inspectpath.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
        db=STATE/'translator/projects'/slug/'memory/memory.sqlite'
        if not db.exists():
            extraction=run_cli(['project','init',slug,'--plugin',str(path),'--game','FalloutNV','--source-lang','en','--target-lang','ko'])
            (OUT/(slug+'.extract.json')).write_text(json.dumps(extraction,ensure_ascii=False,indent=2),encoding='utf-8')
        masters=info.get('masters',info.get('header',{}).get('masters'))
        units=rows(db);sstpath=DICTS/(path.stem.lower()+'_en_ko.sst')
        sst=read_sst(sstpath) if sstpath.exists() else None
        exact=defaultdict(list);sst_by_identity=defaultdict(list)
        if sst:
            for entry in sst.entries:
                if not HANGUL.search(entry.dest):continue
                key=identity(entry.formid,sst.masters,path.name,entry.signature,entry.field,entry.index,entry.index_max)
                if key:
                    exact[(key,entry.source)].append(entry.dest)
                    sst_by_identity[key].append((entry.source,entry.dest))
        counts=Counter()
        for row in units:
            key=identity(row['formid'],masters,path.name,row['signature'],row['field'],row['index_n'],row['index_max'])
            src=row['source'];recovered=recover(src)
            result={k:row[k] for k in ['row_id','formid','signature','field','index_n','index_max','list_index','strid','edid','source'] if k in row}
            result.update(plugin=path.name,canonical_identity=key,project=slug,normalized_source=recovered)
            strict=set(exact.get((key,src),[]))
            olddest={r['dest'] for r in old.get(key,[])}
            cross=global_exact.get((key,src),set())
            if HANGUL.search(recovered): status='already_korean';dest=recovered
            elif len(olddest)==1 and src in preferred_english.get(key,set()):
                status='preferred_kr_sst_exact_source_identity';dest=next(iter(olddest))
            elif len(strict)==1:
                dest=next(iter(strict));status='sst_exact_identity_source'
                if dest in olddest:status='sst_exact_and_preferred_kr_agree'
                elif olddest:result['preferred_kr_alternatives']=sorted(olddest)
            elif len(strict)>1:status='ambiguous_sst';dest=None
            elif len(cross)==1:
                dest=next(iter(cross));status='supplemental_sst_exact_identity_source'
            elif len(olddest)==1:
                dest=next(iter(olddest));status='preferred_kr_identity_only_needs_review'
            elif len(olddest)>1:status='ambiguous_kr_identity';dest=None
            else:status='needs_new_translation';dest=None
            result.update(status=status,dest=dest)
            if status in ('needs_new_translation','preferred_kr_identity_only_needs_review') and key:
                alternate=occurrence_changed.get((key[:4],src),set())
                if len(alternate)==1:
                    result['occurrence_metadata_changed_exact_source_candidate']=next(iter(alternate))
            if key in sst_by_identity and status not in ('sst_exact_identity_source','sst_exact_and_preferred_kr_agree','already_korean'):
                result['same_identity_sst_evidence']=[{'source':a,'dest':b} for a,b in sst_by_identity[key]]
            counts[status]+=1;output.append(result)
            if status in ('needs_new_translation','preferred_kr_identity_only_needs_review','ambiguous_kr_identity','ambiguous_sst'):residual.append(result)
        findings.append({'plugin':path.name,'database':str(db),'units':len(units),'masters':masters,'counts':dict(counts),'sst_path':str(sstpath),'sst_masters':sst.masters if sst else None,'sst_entries':len(sst.entries) if sst else 0,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        print(path.name,len(units),dict(counts),flush=True)
    for name,entries in [('candidates.jsonl',output),('residual.jsonl',residual)]:
        with (OUT/name).open('w',encoding='utf-8') as f:
            for entry in entries:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
    (OUT/'summary.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding='utf-8')
    unique=defaultdict(list)
    for entry in residual:unique[(entry['signature'],entry['field'],entry['source'])].append(entry)
    with (OUT/'residual_unique.jsonl').open('w',encoding='utf-8') as f:
        for (sig,field,source),entries in unique.items():
            f.write(json.dumps({'signature':sig,'field':field,'source':source,'count':len(entries),'examples':entries[:3]},ensure_ascii=False)+'\n')
    print('DONE',len(output),'residual',len(residual),flush=True)

if __name__=='__main__':main()
