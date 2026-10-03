'use strict';
const fs=require('fs'),path=require('path'),root=path.resolve(__dirname,'..');
const x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
const out=path.join(root,'reports/yesman_ai_audit'),game=path.join(root,'staging/xedit_audit_mo2/Audit Game')+'\\';
const current=JSON.parse(fs.readFileSync(path.join(root,'VNV_Translation_Workspace/source_manifest.json'),'utf8')).files.filter(f=>f.category==='01_Plugins').map(f=>f.data_path),set=new Set(current.map(s=>s.toLowerCase()));
const sources=['Fallout NV KR.esm','NVKOR Radio + UI.esp'],hex=n=>n.toString(16).padStart(8,'0').toUpperCase();
function get(r,p){try{return x.hasElement(r,p)?x.getValue(r,p):null}catch{return null}}
function win(r){const m=x.getMasterRecord(r),all=[m,...x.getOverrides(m)];let name=null,highest=-1;for(const h of all){const f=x.getElementFile(h);try{const n=x.name(f),order=x.getFileLoadOrder(f);if(set.has(n.toLowerCase())&&order>highest){name=n;highest=order}}finally{x.release(f)}}for(const h of all)x.release(h);return name;}
function add(map,k){map[k]=(map[k]||0)+1}
async function main(){
 x.init();x.setLanguage('English');x.setGamePath(game);x.setGameMode(x.GM_FNV);x.loadPlugins([...current,...sources].join('\n'),true,false);await x.waitForLoader(180000);
 const summaries=[],rows=[];
 const currentSettings=new Map();
 for(const n of current){const f=x.fileByName(n),rs=x.getRecords(f,'GMST',true);for(const r of rs){const edid=get(r,'EDID');if(edid){const id=hex(x.getFormID(r));if(!currentSettings.has(edid))currentSettings.set(edid,new Map());currentSettings.get(edid).set(id,{global_formid:id,file:n,value:get(r,'DATA')});}x.release(r)}x.release(f)}
 for(const n of sources){const f=x.fileByName(n),masters=x.getMasterNames(f),all=x.getRecords(f,'',true),nativeNew=x.getRecords(f,'',false),sum={plugin:n,masters,all_records:all.length,native_getRecords_without_overrides:nativeNew.length,native_new_signatures:{},local_owned_records:0,local_owned_signatures:{},current_corresponding:0,current_missing:0,current_missing_signatures:{},new_gmst_with_existing_edid:0};for(const r of nativeNew){add(sum.native_new_signatures,x.signature(r));x.release(r)}
  for(const r of all){const id=x.getFormID(r,true),sig=x.signature(r),slot=id>>>24,owner=masters[slot]||n,owned=slot===masters.length,edid=get(r,'EDID'),full=get(r,'FULL'),data=sig==='GMST'?get(r,'DATA'):null,global=hex(x.getFormID(r)),winner=win(r);
   if(owned){sum.local_owned_records++;add(sum.local_owned_signatures,sig)}if(winner)sum.current_corresponding++;else{sum.current_missing++;add(sum.current_missing_signatures,sig)}
   if(owned||!winner){const matches=sig==='GMST'&&edid&&currentSettings.has(edid)?[...currentSettings.get(edid).values()]:[];if(matches.length)sum.new_gmst_with_existing_edid++;
    rows.push({sourceplugin:n,owner,low24:(id&0xffffff).toString(16).padStart(6,'0').toUpperCase(),localFormID:hex(id),globalFormID:global,signature:sig,edid,new_owned_form:owned,current_winner:winner,source_full:full,source_data:data,gmst_same_edid_current_records:matches});
   }x.release(r);
  }x.release(f);summaries.push(sum);console.log(JSON.stringify(sum));
 }
 const report={read_only:true,save_file_called:false,game,current_plugin_count:current.length,source_files:summaries,scope:'Canonical owner+low24 native record inheritance correspondence; new source records classified by local master index. GMST same-EDID references are evidence for review only and not assumed equivalent by FormID. No claim that lack of SCPT or Korean SCTX means lack of extra functionality.'};
 fs.writeFileSync(path.join(out,'radio_ownership_summary.json'),JSON.stringify(report,null,2),'utf8');fs.writeFileSync(path.join(out,'source_owned_or_missing_records.jsonl'),rows.map(r=>JSON.stringify(r)).join('\n')+'\n','utf8');x.close();
}
main().catch(e=>{console.error(e.message.split('\n')[0]);try{x.close()}catch{}process.exit(1)});
