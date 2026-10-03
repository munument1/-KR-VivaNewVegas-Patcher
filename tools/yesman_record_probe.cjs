// Targeted official-API diagnostic, no writes to plugin files.
const fs=require('fs'),path=require('path');
const x=require('../.tools/YesMan-AI/node_modules/xeditlib');
async function main(){
 const req=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 x.init();x.setLanguage('English');x.setGamePath(path.resolve(req.game)+path.sep);x.setGameMode(x.GM_FNV);
 x.loadPlugins(req.plugins.join('\n'),true,false);await x.waitForLoader();
 const rows=[];
 for(const name of req.plugins){
  const file=x.fileByName(name),masters=x.getMasterNames(file);
  for(const r of x.getRecords(file,req.signature,true)){
   const id=x.getFormID(r,true),owner=masters[id>>>24] || name;
   if(owner.toLowerCase()===req.owner.toLowerCase() && (id&0xffffff).toString(16).padStart(6,'0')===req.id){
    const json=JSON.parse(x.elementToJson(r));if(json['Record Header'])delete json['Record Header']['Data Size'];
    const g=x.getElementGroup(r);json.$parent=x.path(g,true,true);x.release(g);
    rows.push({plugin:name,json});
   }x.release(r);
  }x.release(file);
 }
 x.close();fs.writeFileSync(req.output,JSON.stringify(rows,null,2));console.log(JSON.stringify({output:req.output,plugins:rows.map(r=>r.plugin)}));
}
main().catch(e=>{try{x.close()}catch{}console.error(e.stack);process.exitCode=1});
