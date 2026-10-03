const x=require('../.tools/YesMan-AI/node_modules/xeditlib');
const path=require('path');
async function main(){
 x.init();x.setLanguage('English');x.setGamePath(path.resolve('staging/xedit_audit_mo2/Audit Game')+path.sep);x.setGameMode(x.GM_FNV);
 x.loadPlugins('HonestHearts.esm',true,false);await x.waitForLoader();
 const f=x.fileByName('HonestHearts.esm');
 for(const sig of ['ARMO','CELL','DIAL','INFO','QUST','REFR']){
  const records=x.getRecords(f,sig,true);console.log(JSON.stringify({sig,count:records.length}));
  if(records.length){const r=records[0];console.log(JSON.stringify(x.getElements(r).map(e=>{const row={name:x.name(e),type:x.elementType(e),valueType:x.valueType(e)};x.release(e);return row;})));}
  for(const r of records)x.release(r);
 }
 x.release(f);x.close();
}
main().catch(error=>{try{x.close();}catch{}console.error(error.stack);process.exitCode=1;});
