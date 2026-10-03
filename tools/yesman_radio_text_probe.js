'use strict';
const fs=require('fs'),path=require('path'),root=path.resolve(__dirname,'..'),x=require(path.join(root,'.tools/YesMan-AI/node_modules/xeditlib'));
const out=path.join(root,'reports/yesman_ai_audit'),hangul=/[\uac00-\ud7af]/;
function get(r,p){try{return x.hasElement(r,p)?x.getValue(r,p):null}catch{return null}}
async function main(){
 x.init();x.setLanguage('English');x.setGamePath(path.join(root,'staging/xedit_audit_mo2/Audit Game')+'\\');x.setGameMode(x.GM_FNV);x.loadPlugins('NVKOR Radio + UI.esp',true,false);await x.waitForLoader(180000);
 const f=x.fileByName('NVKOR Radio + UI.esp'),rs=x.getRecords(f,'',false),rows=[],samples=[],counts={},sampleCounts={};
 for(const r of rs){const sig=x.signature(r),id=x.getFormID(r,true).toString(16).padStart(8,'0');const fields=[];
  for(const p of ['FULL','DESC',...(sig==='GMST'?['DATA']:[])]){const v=get(r,p);if(v!==null)fields.push({field:p,value:v});}
  if(sig==='INFO'){let responses=[];try{responses=x.getElements(r,'Responses')}catch{}for(let i=0;i<responses.length;i++){const e=responses[i],v=get(e,'NAM1');if(v!==null)fields.push({field:'NAM1',occurrence:i,value:v});x.release(e)}}
  for(const field of fields){const k=sig+'|'+field.field;if(!counts[k])counts[k]={fields:0,hangul:0,empty:0};counts[k].fields++;if(hangul.test(field.value))counts[k].hangul++;if(!field.value)counts[k].empty++;rows.push({localFormID:id,signature:sig,edid:get(r,'EDID'),...field});}
  if(['MESG','INFO','MICN'].includes(sig)&&(sampleCounts[sig]||0)<2){samples.push({localFormID:id,signature:sig,json:JSON.parse(x.elementToJson(r))});sampleCounts[sig]=(sampleCounts[sig]||0)+1}x.release(r);
 }
 fs.writeFileSync(path.join(out,'radio_owned_texts.jsonl'),rows.map(r=>JSON.stringify(r)).join('\n')+'\n','utf8');fs.writeFileSync(path.join(out,'radio_owned_samples.json'),JSON.stringify(samples,null,2),'utf8');fs.writeFileSync(path.join(out,'radio_owned_text_summary.json'),JSON.stringify({read_only:true,save_file_called:false,owned_records:rs.length,counts,note:'Own Form records remain source-plugin-owned. Korean strings here are not evidence that Fixed ESMs contain equivalent records or event wiring.'},null,2),'utf8');console.log(JSON.stringify(counts));x.release(f);x.close();
}
main().catch(e=>{console.error(e.message.split('\n')[0]);try{x.close()}catch{}process.exit(1)});
