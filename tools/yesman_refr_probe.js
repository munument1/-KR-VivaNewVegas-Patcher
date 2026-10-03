'use strict';
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
const out=path.join(root,'reports/yesman_ai_audit');
async function main(){
 x.init();x.setLanguage('English');x.setGamePath(path.join(root,'staging/xedit_audit_mo2/Audit Game')+'\\');x.setGameMode(x.GM_FNV);
 x.loadPlugins('Fallout NV KR.esm\nNVKOR Radio + UI.esp',true,false);await x.waitForLoader(180000);
 const result=[];
 for(const name of ['Fallout NV KR.esm','NVKOR Radio + UI.esp']){
  const f=x.fileByName(name);
  for(const sig of ['QUST','FACT','PERK']){
   const rs=x.getRecords(f,sig,true),entry={file:name,sig,count:rs.length,samples:[]};
   for(const r of rs.slice(0,3))entry.samples.push({id:x.getFormID(r,true).toString(16),json:JSON.parse(x.elementToJson(r))});
   result.push(entry);for(const r of rs)x.release(r);
  }x.release(f);
 }
 fs.writeFileSync(path.join(out,'refr_probe.json'),JSON.stringify(result,null,2),'utf8');console.log(JSON.stringify(result.map(({samples,...e})=>e)));x.close();
}
main().catch(e=>{console.error(e.stack);try{x.close()}catch{}process.exit(1)});
