'use strict';
// Narrow disposable fixture only. Uses official XEditLib APIs; no binary parser/writer.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),root=path.resolve(__dirname,'..');
const x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
const out=path.join(root,'reports/native_save_fix_20261003'),fixture=path.join(root,'staging/native_save_fix_20261003');
const names=['FalloutNV.esm','DeadMoney.esm','HonestHearts.esm','OldWorldBlues.esm','LonesomeRoad.esm','GunRunnersArsenal.esm','YUP - Base Game + All DLC.esm'];
const mode=process.argv[2]||'baseline',isRead=mode.startsWith('read-'),trial=mode.replace(/^read-/,'');
const game=isRead?path.join(fixture,trial):fixture,flag='Quest item / Persistent reference';
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
function snap(r){const g=x.getElementGroup(r);try{return {flag:x.getFlag(r,'Record Header\\Record Flags',flag),parent:x.path(g,true,true),json:JSON.parse(x.elementToJson(r))}}finally{x.release(g)}}
async function main(){
 fs.mkdirSync(out,{recursive:true});const beforeHashes=Object.fromEntries(names.map(n=>[n,sha(path.join(game,'Data',n))]));
 x.init();x.setLanguage('English');x.setGamePath(game+path.sep);x.setGameMode(x.GM_FNV);x.loadPlugins(names.join('\n'),true,false);await x.waitForLoader(180000);
 const baseFile=x.fileByName(names[0]),targetFile=x.fileByName(names.at(-1)),base=x.getRecord(baseFile,0x138c03,false),target=x.getRecord(targetFile,0x138c03,false);
 const report={mode,isolated_game:game,input_hashes:beforeHashes,before:{base:snap(base),target:snap(target)},save_file_called:!isRead};
 if(!isRead){
  const destGame=path.join(fixture,trial),destData=path.join(destGame,'Data');fs.mkdirSync(destData,{recursive:true});
  for(const n of names.slice(0,-1))fs.copyFileSync(path.join(fixture,'Data',n),path.join(destData,n));
  try{
   if(trial==='clear-ancestor')x.setFlag(base,'Record Header\\Record Flags',flag,false);
   report.before_save={base:snap(base),target:snap(target)};
   const dest=path.join(destData,names.at(-1));if(fs.existsSync(dest))throw Error('Disposable output already exists: '+dest);
   x.saveFile(targetFile,dest);report.after_save={base:snap(base),target:snap(target)};
  }finally{
   if(trial==='clear-ancestor')x.setFlag(base,'Record Header\\Record Flags',flag,report.before.base.flag);
   report.after_restore={base:snap(base),target:snap(target)};
  }
 }
 x.release(base);x.release(target);x.release(baseFile);x.release(targetFile);x.close();
 report.after_input_hashes=Object.fromEntries(names.map(n=>[n,sha(path.join(game,'Data',n))]));report.input_files_unchanged=JSON.stringify(report.input_hashes)===JSON.stringify(report.after_input_hashes);
 fs.writeFileSync(path.join(out,mode+'.json'),JSON.stringify(report,null,2),'utf8');console.log(JSON.stringify({mode,input_files_unchanged:report.input_files_unchanged,before:{base:report.before.base.flag,target:report.before.target.flag},after_save:report.after_save&&{base:report.after_save.base.flag,target:report.after_save.target.flag},after_restore:report.after_restore&&{base:report.after_restore.base.flag,target:report.after_restore.target.flag},group:report.after_save?.target.parent||report.before.target.parent}));
}
main().catch(e=>{console.error(e.message.split('\n')[0]);try{x.close()}catch{}process.exit(1)});
