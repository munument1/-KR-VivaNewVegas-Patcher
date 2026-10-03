const x = require('../.tools/YesMan-AI/node_modules/xeditlib');
const path = require('path');
const fs = require('fs');
const root = path.resolve(__dirname, '..');
const game = path.join(root, 'staging/xedit_audit_mo2/Audit Game');
async function main() {
  x.init(); x.setLanguage('English'); x.setGamePath(game + path.sep); x.setGameMode(x.GM_FNV);
  x.loadPlugins('MercenaryPack.esm', true, false); await x.waitForLoader();
  const file = x.fileByName('MercenaryPack.esm');
  const rows = [];
  for (const record of x.getRecords(file, '', true)) {
    const row = {signature:x.signature(record), global:x.getFormID(record), local:x.getFormID(record,true),
      recordPath:x.path(record, true, true), json:JSON.parse(x.elementToJson(record)), children:[]};
    function walk(handle, depth=0) {
      if (depth > 5) return;
      let children;
      try {children=x.getElements(handle);} catch {return;}
      for (const child of children) {
        row.children.push({depth, name:x.name(child), pathName:x.pathName(child,true), path:x.path(child,true,true),
          elementType:x.elementType(child), valueType:x.valueType(child),
          ...(depth===0 ? {json:JSON.parse(x.elementToJson(child))} : {})});
        walk(child,depth+1); x.release(child);
      }
    }
    walk(record); rows.push(row); x.release(record);
  }
  x.release(file); x.close();
  fs.writeFileSync(path.join(root,'staging/yesman_probe/paths.json'),JSON.stringify(rows,null,2));
  console.log(JSON.stringify(rows.map(r=>({sig:r.signature,global:r.global,local:r.local,path:r.recordPath,children:r.children.slice(0,8)}))));
}
main().catch(error=>{try{x.close();}catch{} console.error(error.stack);process.exitCode=1;});
