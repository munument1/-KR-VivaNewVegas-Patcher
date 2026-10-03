'use strict';
// Official XEditLib read-only inspection. Never calls SaveFile or mutators.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..');
const x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
const out=path.join(root,'reports/yesman_ai_audit');fs.mkdirSync(out,{recursive:true});
const game=path.join(root,'staging/xedit_audit_mo2/Audit Game')+'\\';
const manifest=JSON.parse(fs.readFileSync(path.join(root,'VNV_Translation_Workspace/source_manifest.json'),'utf8'));
const current=manifest.files.filter(f=>f.category==='01_Plugins').map(f=>f.data_path);
const sources=['Fallout NV KR.esm','NVKOR Radio + UI.esp'];
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
const hex=id=>id.toString(16).padStart(8,'0').toUpperCase();
const counts={queried_source_records:0,source_script_blocks:0,source_nonempty_compiled_blocks:0,source_source_text_blocks:0,source_source_text_hangul_blocks:0,source_script_blocks_different_from_current:0,compiled_changed_blocks:0,source_text_changed_blocks:0,reference_or_metadata_changed_blocks:0,script_records_with_changes:0,current_standalone_scripts:0,current_script_display_string_literals:0};
function blocks(o,p='',result=[]){
 if(!o||typeof o!=='object')return result;
 if(!Array.isArray(o)&&Object.keys(o).some(k=>/^SCTX|^SCDA/.test(k))){result.push({path:p,fields:o});return result;}
 for(const [k,v]of Object.entries(o)){if(k==='Child Group')continue;blocks(v,p?p+'\\'+k:k,result);}
 return result;
}
function filename(handle){const f=x.getElementFile(handle);try{return x.name(f)}finally{x.release(f)}}
function owner(handle){const m=x.getMasterRecord(handle);try{return {file:filename(m),formid:hex(x.getFormID(m)),signature:x.signature(m)}}finally{x.release(m)}}
function value(block,prefix){const key=Object.keys(block.fields).find(k=>k.startsWith(prefix));return key?block.fields[key]:null;}
function nativeBlockEqual(a,b,blockPath){let ha=0,hb=0;try{ha=x.getElement(a,blockPath);hb=x.getElement(b,blockPath);return x.elementEquals(ha,hb)}catch{return null}finally{if(ha)x.release(ha);if(hb)x.release(hb)}}
function currentWinner(record){
 let h=x.getMasterRecord(record),best=h,bestIndex=-1;
 let candidates=[h,...x.getOverrides(h)];
 for(const r of candidates){const f=x.getElementFile(r);try{const name=x.name(f),index=x.getFileLoadOrder(f);if(current.includes(name)&&index>bestIndex){best=r;bestIndex=index}}finally{x.release(f)}}
 for(const r of candidates)if(r!==best)x.release(r);
 return best;
}
function compareFields(a,b){
 const sourceA=value(a,'SCTX'),sourceB=b?value(b,'SCTX'):null;
 const compiledA=value(a,'SCDA'),compiledB=b?value(b,'SCDA'):null;
 const metaA={...a.fields},metaB=b?{...b.fields}:null;
 for(const key of Object.keys(metaA))if(/^SCTX|^SCDA/.test(key))delete metaA[key];
 if(metaB)for(const key of Object.keys(metaB))if(/^SCTX|^SCDA/.test(key))delete metaB[key];
 return {source_text_changed:sourceA!==sourceB,compiled_changed:compiledA!==compiledB,metadata_json_changed:JSON.stringify(metaA)!==JSON.stringify(metaB),source_text:sourceA,current_source_text:sourceB,source_compiled_hex:compiledA,current_compiled_hex:compiledB,source_metadata:metaA,current_metadata:metaB};
}
async function main(){
 x.init();x.setLanguage('English');x.setGamePath(game);x.setGameMode(x.GM_FNV);x.loadPlugins([...current,...sources].join('\n'),true,false);await x.waitForLoader(180000);
 let globals=null;try{globals=x.getGlobals()}catch(e){globals={error:e.message}}
 fs.writeFileSync(path.join(out,'globals.json'),JSON.stringify(globals,null,2),'utf8');
 const files=[],changed=[],allSourceScripts=[];
 for(const name of sources){
  const f=x.fileByName(name);const bySig={};const rs=x.getRecords(f,'',true);const sourceEntry={file:name,record_count:rs.length,signature_counts:bySig,script_blocks:0,nonempty_compiled_blocks:0};
  for(const r of rs){
   const sig=x.signature(r);bySig[sig]=(bySig[sig]||0)+1;counts.queried_source_records++;
   const dump=JSON.parse(x.elementToJson(r)),bs=blocks(dump);
   if(bs.length){
    const actual=currentWinner(r),actualName=filename(actual),actualJson=JSON.parse(x.elementToJson(actual)),actualBlocks=blocks(actualJson),map=new Map(actualBlocks.map(b=>[b.path,b]));
    let recordChanged=false;
    for(const b of bs){
     counts.source_script_blocks++;sourceEntry.script_blocks++;
     const compiled=value(b,'SCDA'),source=value(b,'SCTX');
     if(compiled){counts.source_nonempty_compiled_blocks++;sourceEntry.nonempty_compiled_blocks++}
     if(source)counts.source_source_text_blocks++;
     if(source&&/[\uac00-\ud7af]/.test(source))counts.source_source_text_hangul_blocks++;
     const comparison=compareFields(b,map.get(b.path));
     const nativeEqual=nativeBlockEqual(r,actual,b.path);
     const item={source_file:name,owner:owner(r),formid:hex(x.getFormID(r)),signature:sig,current_winner:actualName,script_path:b.path,native_block_equal:nativeEqual,...comparison};
     allSourceScripts.push(item);
     if(nativeEqual!==true&&(comparison.compiled_changed||comparison.source_text_changed||comparison.metadata_json_changed)){
      counts.source_script_blocks_different_from_current++;recordChanged=true;if(comparison.compiled_changed)counts.compiled_changed_blocks++;if(comparison.source_text_changed)counts.source_text_changed_blocks++;if(comparison.metadata_json_changed)counts.reference_or_metadata_changed_blocks++;changed.push(item);
     }
    }
    if(recordChanged)counts.script_records_with_changes++;
    x.release(actual);
   }
   x.release(r);
   if(counts.queried_source_records%5000===0)console.log(JSON.stringify({progress:counts.queried_source_records,script_blocks:counts.source_script_blocks}));
  }
  files.push(sourceEntry);x.release(f);
 }
 const seen=new Set(),standalone=[];
 for(const name of current){const f=x.fileByName(name);const scripts=x.getRecords(f,'SCPT',true);
  for(const r of scripts){const id=hex(x.getFormID(r));if(!seen.has(id)){seen.add(id);const winner=currentWinner(r);const dump=JSON.parse(x.elementToJson(winner));const bs=blocks(dump);counts.current_standalone_scripts++;const src=bs.length?value(bs[0],'SCTX'):null;const literals=[];
   if(src)for(const line of src.split(/\r?\n/))if(/\b(messagebox|showmessage|showmessageex|printc|print|debugnotification|setname)\b/i.test(line)){const strings=[...line.matchAll(/"([^"\r\n]*)"/g)].map(m=>m[1]);if(strings.length)literals.push({line,strings})}
   if(literals.length){counts.current_script_display_string_literals+=literals.length;standalone.push({owner:owner(winner),current_winner:filename(winner),edid:x.getValue(winner,'EDID'),script_source:src,display_literal_lines:literals,compiled_hex:bs.length?value(bs[0],'SCDA'):null})}x.release(winner);
  }x.release(r)}x.release(f);
 }
 for(const [name,items]of [['source_embedded_scripts.jsonl',allSourceScripts],['script_differences.jsonl',changed],['current_standalone_display_literals.jsonl',standalone]])fs.writeFileSync(path.join(out,name),items.map(x=>JSON.stringify(x)).join('\n')+'\n','utf8');
 const runtimeFile=path.join(root,'.tools/yesman-node-utf8/runtime.json');const runtime=fs.existsSync(runtimeFile)?JSON.parse(fs.readFileSync(runtimeFile,'utf8')):null;
 const summary={read_only:true,save_file_called:false,game,node_executable:process.execPath,process_utf8_runtime:runtime,source_files:files,counts,scope:'All records of two supplied Korean sources, script source/compiled blocks vs current 43-plugin winner; standalone current SCPT display-command string candidates only. No new translation/no plugin edits.',encoding_warning:'Use manifest UTF8 node runtime only; confirmed source text Korean recovery in separate probe. Do not assume supplied user-translated other plugins are UTF8 without individual checks. Compiled hex is exposed directly by official API.',source_scripts_safe_to_copy:[]};
 fs.writeFileSync(path.join(out,'script_audit_summary.json'),JSON.stringify(summary,null,2),'utf8');console.log(JSON.stringify(summary,null,2));x.close();
}
main().catch(err=>{console.error(err.stack);try{x.close()}catch{}process.exit(1)});
