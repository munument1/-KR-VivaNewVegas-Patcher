'use strict';
// Official API read-only snapshots and dependency inspection; no plugin parser/writer.
const fs=require('fs'),path=require('path'),root=path.resolve(__dirname,'..'),x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
const out=path.join(root,'reports/yesman_ai_audit'),radio='NVKOR Radio + UI.esp';
const manifest=JSON.parse(fs.readFileSync(path.join(root,'VNV_Translation_Workspace/source_manifest.json'),'utf8'));
const mode=process.argv.includes('--steam')?'steam':'vnv',game=path.join(root,mode==='steam'?'staging/radio_steam_audit_game':'staging/xedit_audit_mo2/Audit Game')+'\\';
const originals=manifest.files.filter(f=>f.category==='01_Plugins').map(f=>f.data_path);
const names=mode==='steam'?['FalloutNV.esm','DeadMoney.esm','HonestHearts.esm','OldWorldBlues.esm','LonesomeRoad.esm']:originals;
const nameSet=new Set(names.map(s=>s.toLowerCase())),mastersCache=new Map(),hex=n=>n.toString(16).padStart(8,'0').toUpperCase();
function fileName(r){const f=x.getElementFile(r);try{return x.name(f)}finally{x.release(f)}}
function identity(r){const f=x.getElementFile(r);try{const n=x.name(f);if(!mastersCache.has(n))mastersCache.set(n,x.getMasterNames(f));const ms=mastersCache.get(n),id=x.getFormID(r,true);return {owner:ms[id>>>24]||n,low24:(id&0xffffff).toString(16).padStart(6,'0').toUpperCase(),signature:x.signature(r)}}finally{x.release(f)}}
function key(r){const i=identity(r);return i.owner.toLowerCase()+'|'+i.low24+'|'+i.signature}
function get(r,p){try{return x.hasElement(r,p)?x.getValue(r,p):null}catch{return null}}
function winner(r){const master=x.getMasterRecord(r),all=[master,...x.getOverrides(master)];let best=0,order=-1;for(const h of all){const f=x.getElementFile(h);try{const n=x.name(f),o=x.getFileLoadOrder(f);if(nameSet.has(n.toLowerCase())&&o>order){best=h;order=o}}finally{x.release(f)}}for(const h of all)if(h!==best&&h!==r)x.release(h);return best;}
function snapshot(record){
 const fields={},refs=[],errors=[];
 function walk(h,p,field=null){
  let type,vt;try{type=x.elementType(h)}catch{return}if([0,1,2,11].includes(type)&&h!==record)return;
  try{vt=x.valueType(h)}catch{vt=null}
  const n=x.name(h),m=/^([A-Z0-9_]{4})(?: -|$)/.exec(n);if(m)field=m[1];
  if(vt===5){let target=0;try{target=x.getLinksTo(h);const id=identity(target),value=id.owner.toLowerCase()+'|'+id.low24+'|'+id.signature;fields[p]={field,vt,value};refs.push({path:p,field,target:id});}catch{fields[p]={field,vt,value:x.getValue(h),unresolved:true}}finally{if(target&&target!==record)x.release(target)}return;}
  if(vt===6){let value;try{value=x.getUIntValue(h)}catch{value=x.getValue(h)}fields[p]={field,vt,value};return;}
  let children=[];try{children=x.getElements(h)}catch{}
  if(children.length){for(let i=0;i<children.length;i++){const e=children[i],name=type===5?'['+i+']':x.name(e),label=/^([A-Z0-9_]{4})(?: -|$)/.exec(name),part=label?label[1]:name;walk(e,p?p+'\\'+part:part,field);x.release(e)}}else if(h!==record){try{fields[p]={field,vt,value:x.getValue(h)}}catch{errors.push({path:p,type,vt})}}
 }
 // getElements(record) contains its fields, not its descendant INFO/CELL group records.
 for(const c of x.getElements(record)){const n=x.name(c);if(n==='Record Header'){const flags=get(c,'Record Flags');fields['Record Header\\Record Flags']={field:null,vt:6,value:flags};}else walk(c,/^([A-Z0-9_]{4})(?: -|$)/.exec(n)?.[1]||n);x.release(c)}
 return {fields,refs,errors};
}
async function main(){
 x.init();x.setLanguage('English');x.setGamePath(game);x.setGameMode(x.GM_FNV);x.loadPlugins([...names,radio].join('\n'),true,false);await x.waitForLoader(180000);
 const f=x.fileByName(radio),masters=x.getMasterNames(f),records=x.getRecords(f,'',true),result=[],owned=[],gmstEdid=new Map();
 for(const n of names){const cf=x.fileByName(n),rs=x.getRecords(cf,'GMST',true);for(const r of rs){const edid=get(r,'EDID');if(edid){const k=key(r),load=x.getFileLoadOrder(cf),entry={identity:identity(r),file:n,load,edid,data:get(r,'DATA')};let el=0;try{el=x.getElement(r,'DATA');entry.value_type=x.valueType(el)}catch{}finally{if(el)x.release(el)}if(!gmstEdid.has(edid)||gmstEdid.get(edid).load<load)gmstEdid.set(edid,entry)}x.release(r)}x.release(cf)}
 for(const r of records){const id=identity(r),raw=x.getFormID(r,true),isOwned=(raw>>>24)===masters.length,edid=get(r,'EDID'),source=snapshot(r);
  if(isOwned){const same=id.signature==='GMST'?gmstEdid.get(edid):null;owned.push({key:key(r),identity:id,edid,source,...(same?{same_edid_current:same}:{})});}
  else{const w=winner(r);if(!w)throw Error('No current override match '+key(r));const current=snapshot(w);result.push({key:key(r),identity:id,edid,winner:fileName(w),source,current});if(w!==r)x.release(w)}x.release(r);
 }
 x.release(f);x.close();
 fs.writeFileSync(path.join(out,'radio_override_'+mode+'_snapshots.jsonl'),result.map(r=>JSON.stringify(r)).join('\n')+'\n','utf8');fs.writeFileSync(path.join(out,'radio_override_'+mode+'_owned.jsonl'),owned.map(r=>JSON.stringify(r)).join('\n')+'\n','utf8');console.log(JSON.stringify({mode,override_count:result.length,owned_count:owned.length,output:out}));
}
main().catch(e=>{console.error(e.message.split('\n')[0]);try{x.close()}catch{}process.exit(1)});
