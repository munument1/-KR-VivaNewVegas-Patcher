'use strict';
const fs=require('fs'),path=require('path'),root=path.resolve(__dirname,'..');
const x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
async function main(){
 x.init();x.setLanguage('English');x.setGamePath(path.join(root,'staging/xedit_audit_mo2/Audit Game')+'\\');x.setGameMode(x.GM_FNV);
 x.loadPlugins('Fallout NV KR.esm\nNVKOR Radio + UI.esp',true,false);await x.waitForLoader(180000);
 const result=[];
 function snapshot(h){let vt=null,sig=null;try{vt=x.valueType(h)}catch{}try{sig=x.signature(h)}catch{}return {name:x.name(h),type:x.elementType(h),valueType:vt,path:x.path(h,true,true),signature:sig}}
 for(const name of ['FalloutNV.esm','Fallout NV KR.esm']){
  const f=x.fileByName(name);
  for(const sig of ['DIAL','CELL','BPTD']){
   const rs=x.getRecords(f,sig,true);
   for(const r of rs.slice(0,3)){
    const children=x.getElements(r),entry={file:name,id:x.getFormID(r).toString(16),sig,record:snapshot(r),children:[]};
    for(const c of children){const item=snapshot(c);try{const sub=x.getElements(c);item.children=sub.slice(0,3).map(snapshot);for(const e of sub)x.release(e);}catch{}entry.children.push(item);x.release(c)}result.push(entry);
   }for(const r of rs)x.release(r);
  }x.release(f);
 }
 const p=path.join(root,'reports/yesman_ai_audit/element_path_probe.json');fs.writeFileSync(p,JSON.stringify(result,null,2),'utf8');console.log(p);x.close();
}
main().catch(e=>{console.error(e.stack);try{x.close()}catch{}process.exit(1)});
