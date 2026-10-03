'use strict';
// Read-only official XEditLib API; no plugin bytes parsed and no mutators called.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
const out=path.join(root,'reports/yesman_ai_audit'),game=path.join(root,'staging/xedit_audit_mo2/Audit Game')+'\\';
const manifest=JSON.parse(fs.readFileSync(path.join(root,'VNV_Translation_Workspace/source_manifest.json'),'utf8'));
const original=manifest.files.filter(f=>f.category==='01_Plugins'),current=original.map(f=>f.data_path),currentSet=new Set(current.map(n=>n.toLowerCase()));
const sourceNames=['Fallout NV KR.esm','NVKOR Radio + UI.esp'];
const schema=JSON.parse(fs.readFileSync(path.join(out,'xtl_fnv_fields.json'),'utf8'));
const omitted=['BPTD','REFR','ACHR','ACRE','NAVM','PGRE','MICN'];
const scanSignatures=process.argv.includes('--targeted-excluded-fields') ? ['BPTD','REFR','ACRE','ACTI','QUST','DIAL','PERK','FACT','GMST'] : process.argv.includes('--all-excluded-fields') ? Object.keys(JSON.parse(fs.readFileSync(path.join(out,'script_audit_summary.json'),'utf8')).source_files[0].signature_counts).concat('MICN') : omitted;
const hangul=/[\uac00-\ud7af\u3130-\u318f]/,hex=id=>id.toString(16).padStart(8,'0').toUpperCase();
const unsupportedValueTypes=[];
function filename(h){const f=x.getElementFile(h);try{return x.name(f)}finally{x.release(f)}}
function winner(r){
 const master=x.getMasterRecord(r),rs=[master,...x.getOverrides(master)];let best=0,order=-1;
 for(const h of rs){const f=x.getElementFile(h);try{if(currentSet.has(x.name(f).toLowerCase())&&x.getFileLoadOrder(f)>order){best=h;order=x.getFileLoadOrder(f)}}finally{x.release(f)}}
 for(const h of rs)if(h!==best)x.release(h);return best;
}
function text(h,covered){
 const result=[];
 function walk(e,inherited=null){
  let children;try{children=x.getElements(e)}catch{return}
  for(const child of children){
   try{
    const type=x.elementType(child);if([0,1,2,10].includes(type))continue;
    const m=/^([A-Z0-9_]{4})(?: -|$)/.exec(x.name(child)),field=m?m[1]:inherited;
    let vt;try{vt=x.valueType(child)}catch{unsupportedValueTypes.push({name:x.name(child),type,path:x.path(child,true,true)});continue;}
    if([3,4].includes(vt)){if(covered.includes(field))continue;const value=x.getValue(child);if(hangul.test(value))result.push({field,path:x.path(child,true,true),fullpath:x.path(child,false,true),dest:value,name:x.name(child)});}
    else if(type!==9)walk(child,field);
   }finally{x.release(child)}
  }
 }
 walk(h);return result;
}
function get(h,p){try{return x.hasElement(h,p)?x.getValue(h,p):null}catch{return null}}
function ident(f,r){const local=x.getFormID(r,true),masters=x.getMasterNames(f);return {owner:masters[local>>>24]||x.name(f),low24:(local&0xffffff).toString(16).padStart(6,'0').toUpperCase(),signature:x.signature(r)}}
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function main(){
 x.init();x.setLanguage('English');x.setGamePath(game);x.setGameMode(x.GM_FNV);
 const koffi=require(path.join(root,'.tools/YesMan-AI/node_modules/koffi')),acp=koffi.load('kernel32.dll').func('uint GetACP()')();
 if(acp!==65001)throw Error('Requires isolated UTF8 manifested runtime');
 x.loadPlugins([...current,...sourceNames].join('\n'),true,false);await x.waitForLoader(180000);
 const counts={},rows=[],candidates=[],exclusions=[],sources=[];let visited=0;
 for(const name of sourceNames){
  const f=x.fileByName(name),hash=sha(path.join(game,'Data',name));sources.push({name,sha256:hash,masters:x.getMasterNames(f)});
  for(const sig of scanSignatures){
   const rs=x.getRecords(f,sig,true),stats={queried:rs.length,hangul_records:0,hangul_fields:0,full_fields:0,supplement_pairs:0};counts[name+'|'+sig]=stats;
   for(const r of rs){
    const fields=text(r,schema[sig]||[]);if(fields.length){
     stats.hangul_records++;stats.hangul_fields+=fields.length;
     const w=winner(r),winnerName=w?filename(w):null,identity=ident(f,r);
     for(const item of fields){
      let english=w?get(w,item.path):null,actualPath=item.path;
      if(english===null&&w){english=get(w,item.fullpath);if(english!==null)actualPath=item.fullpath;}
      // Native short/local Path omits the unnamed BPTD Body Parts array parent.
      // Its name is independently exposed by the official record JSON.
      const arrayNames={BPTD:'Body Parts',QUST:'Objectives',FACT:'Ranks',PERK:'Effects'};
      if(english===null&&w&&arrayNames[sig]&&/^\\\[\d+\]/.test(item.path)){
       const p=arrayNames[sig]+item.path;english=get(w,p);if(english!==null)actualPath=p;
      }
      const row={...identity,formid:hex(x.getFormID(r)),edid:get(r,'EDID'),field:item.field,path:actualPath,native_path:item.path,fullpath:item.fullpath,currentEnglish:english,sourceEnglish:english,dest:item.dest,currentwinner:winnerName,winningfile:winnerName,sourceprovenance:{plugin:name,sha256:hash,localFormID:hex(x.getFormID(r,true))},native_field_name:item.name};
      if(sig==='BPTD'&&item.field==='BPTN'){
       const parent=actualPath.slice(0,actualPath.lastIndexOf('\\'));
       const sourceContext={},currentContext={};for(const p of ['BPNN','BPNT','BPNI','BPND\\Part Type']){sourceContext[p]=get(r,parent+'\\'+p);currentContext[p]=w?get(w,parent+'\\'+p):null;}
       row.part_context={source:sourceContext,current:currentContext,equal:JSON.stringify(sourceContext)===JSON.stringify(currentContext)};
      }
      if(sig==='QUST'&&item.field==='NNAM'){
       const sourcePath='Objectives'+item.path,sourceParent=sourcePath.slice(0,sourcePath.lastIndexOf('\\'));
       const sourceIndex=get(r,sourceParent+'\\QOBJ');let currentIndex=w?get(w,actualPath.slice(0,actualPath.lastIndexOf('\\'))+'\\QOBJ'):null;
       if(w&&sourceIndex!==null&&sourceIndex!==currentIndex){
        let elements=[];try{elements=x.getElements(w,'Objectives')}catch{}
        for(let i=0;i<elements.length;i++){const e=elements[i];if(get(e,'QOBJ')===sourceIndex){const p='Objectives\\['+i+']\\NNAM';const translatedEnglish=get(w,p);if(translatedEnglish!==null){row.path=p;row.currentEnglish=translatedEnglish;row.sourceEnglish=translatedEnglish;english=translatedEnglish;currentIndex=sourceIndex}}x.release(e)}
       }
       row.objective_context={source_objective_id:sourceIndex,current_objective_id:currentIndex,equal:sourceIndex!==null&&sourceIndex===currentIndex};
      }
      if(sig==='FACT'&&item.field==='FNAM'){
       const parent=actualPath.slice(0,actualPath.lastIndexOf('\\'));const a=get(r,parent+'\\RNAM'),b=w?get(w,parent+'\\RNAM'):null;
       row.rank_context={source_rank:a,current_rank:b,equal:a!==null&&a===b};
      }
      rows.push(row);if(item.field==='FULL')stats.full_fields++;
      let reason=null;
      const directDisplay=['FULL','XATO','BPTN','RNAM','NNAM','TDUM','EPF2','FNAM'].includes(item.field)||(sig==='GMST'&&item.field==='DATA'&&/^s/.test(row.edid||''));
      if(!w)reason='no_current_record';else if(item.dest.includes('\uFFFD')||(english&&english.includes('\uFFFD')))reason='encoding_unreadable';else if(!directDisplay)reason='not_classified_player_facing';else if(row.part_context&&!row.part_context.equal)reason='body_part_context_changed';else if(row.objective_context&&!row.objective_context.equal)reason='objective_id_not_matched';else if(row.rank_context&&!row.rank_context.equal)reason='rank_index_not_matched';else if(english&&hangul.test(english))reason='current_text_already_korean';else if(english===null)reason='current_field_absent';else if(!english.trim())reason='current_field_empty';else if(english===item.dest)reason='text_unchanged';
      if(reason)exclusions.push({...row,reason});else{candidates.push(row);stats.supplement_pairs++;}
     }if(w)x.release(w);
    }
    x.release(r);visited++;if(visited%5000===0)console.log(JSON.stringify({visited,candidates:candidates.length}));
   }
  }x.release(f);
 }
 for(const [name,data]of [['missing_schema_hangul_fields.jsonl',rows],['supplement_full_pairs.jsonl',candidates.filter(r=>r.field==='FULL')],['supplement_display_pairs.jsonl',candidates],['missing_schema_exclusions.jsonl',exclusions],['unsupported_value_types.jsonl',unsupportedValueTypes]])fs.writeFileSync(path.join(out,name),data.map(r=>JSON.stringify(r)).join('\n')+(data.length?'\n':''),'utf8');
 const byField={};for(const c of candidates)byField[c.signature+'|'+c.field]=(byField[c.signature+'|'+c.field]||0)+1;
 const summary={read_only:true,save_file_called:false,engine:'YesManAI/xEditLib',acp,node:process.execPath,game,current_plugin_count:current.length,current_plugins:current,source_files:sources,schema_omitted_signatures:omitted,scanned_signatures:scanSignatures,counts,hangul_fields:rows.length,supplement_full_pairs:candidates.filter(r=>r.field==='FULL').length,supplement_display_pairs:candidates.length,supplement_display_by_field:byField,exclusions:exclusions.length,unsupported_value_type_count:unsupportedValueTypes.length,scope:'Requested source signatures; string values outside installed xtl fnv schema inspected using official API. Only existing Korean text reuse candidates, no automatic plugin changes. QUST objective ID and FACT rank ID are validated; BPTN checks node, VATS node, IK node and part type. PERK labels remain occurrence-based semantic review candidates. Current winner restricted to original 43-plugin installation. No script copies, no save, no functional-equivalence assertion.',proposal:'For each reviewed pair, replace only this text field in an output copy of the existing current-winning ESM/ESP. Preserve current functional fields, owner ID and referenced records; distribute delta translation data for those installed files.'};
 fs.writeFileSync(path.join(out,'missing_text_audit_summary.json'),JSON.stringify(summary,null,2),'utf8');console.log(JSON.stringify(summary,null,2));x.close();
}
main().catch(e=>{console.error(e.stack);try{x.close()}catch{}process.exit(1)});
