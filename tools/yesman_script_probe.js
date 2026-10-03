'use strict';
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
const out=path.join(root,'reports/yesman_ai_audit');fs.mkdirSync(out,{recursive:true});
const game=path.join(root,'staging/xedit_audit_mo2/Audit Game')+'\\';
x.init();x.setLanguage('English');x.setGamePath(game);x.setGameMode(x.GM_FNV);
x.loadPlugins('Fallout NV KR.esm\nNVKOR Radio + UI.esp',true,false);
x.waitForLoader(180000).then(()=>{
 const result={game,files:[]};
 for(const name of ['Fallout NV KR.esm','NVKOR Radio + UI.esp']){
  const f=x.fileByName(name);const entry={name,record_count:x.getRecordCount(f),scripts:[]};
  for(const sig of ['SCPT','INFO','QUST','TERM','PACK','PERK']){
   const handles=x.getRecords(f,sig,true);let samples=[];
   for(const r of handles.slice(0,2)){samples.push({formid:x.getFormID(r).toString(16),json:JSON.parse(x.elementToJson(r))});}
   entry.scripts.push({signature:sig,count:handles.length,samples});for(const h of handles)x.release(h);
  }
  result.files.push(entry);x.release(f);
 }
 fs.writeFileSync(path.join(out,'probe.json'),JSON.stringify(result,null,2),'utf8');console.log(JSON.stringify(result.files.map(f=>({name:f.name,record_count:f.record_count,sigs:f.scripts.map(s=>({sig:s.signature,count:s.count}))})),null,2));
 x.close();
}).catch(err=>{console.error(err.stack);try{x.close()}catch{}process.exit(1)});
