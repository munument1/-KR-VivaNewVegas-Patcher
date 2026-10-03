// A disposable copy of a real plugin models a future upstream update.
const fs=require('fs'),path=require('path');
const x=require('../.tools/YesMan-AI/node_modules/xeditlib');
const root=path.resolve(__dirname,'..');
async function main(){
 const game=path.join(root,'staging/xedit_audit_mo2/Audit Game');
 x.init();x.setLanguage('English');x.setGamePath(game+path.sep);x.setGameMode(x.GM_FNV);
 x.loadPlugins('MercenaryPack.esm',true,false);await x.waitForLoader();
 const file=x.fileByName('MercenaryPack.esm');
 const armor=x.getRecords(file,'ARMO',true)[0];
 x.setFloatValue(armor,'DATA\\Weight',43.5);
 const message=x.getRecords(file,'MESG',true)[0];
 x.setValue(message,'DESC','Extra updated English description!');
 const group=x.addElement(file,'NOTE'),note=x.addElement(group,'.');
 x.addElementValue(note,'EDID','VNVKR_UpstreamUpdateFixture');
 x.addElementValue(note,'FULL','New untranslated upstream note');
 const output=path.join(root,'staging/yesman_update_fixture/current/Data/MercenaryPack.esm');
 fs.mkdirSync(path.dirname(output),{recursive:true});
 x.saveFile(file,output);
 for(const handle of [note,group,message,armor,file])x.release(handle);
 x.close();console.log(JSON.stringify({output,fixture:true,installed:false}));
}
main().catch(error=>{try{x.close();}catch{}console.error(error.stack);process.exitCode=1;});
