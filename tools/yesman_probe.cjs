// Library API probe only: never parses or edits plugin bytes itself.
const fs = require('fs');
const path = require('path');
const x = require('../.tools/YesMan-AI/node_modules/xeditlib');
const root = path.resolve(__dirname, '..');
const game = path.resolve(root, 'staging/xedit_audit_mo2/Audit Game');
const target = path.resolve(root, 'staging/yesman_probe');
fs.mkdirSync(target, {recursive: true});
const pluginPath = path.join(target, 'VNVKR_EncodingProbe.esp');
const wanted = '시험 한글 번역 - 가나다';
async function main() {
  x.init(); x.setLanguage('English'); x.setGamePath(game + path.sep); x.setGameMode(x.GM_FNV);
  x.loadPlugins(process.argv.includes('--read') ? 'VNVKR_EncodingProbe.esp' : 'FalloutNV.esm', true, false); await x.waitForLoader();
  if (process.argv.includes('--read')) {
    const file = x.fileByName('VNVKR_EncodingProbe.esp');
    const records = x.getRecords(file, 'NOTE', true);
    const readback = x.getValue(records[0], 'FULL');
    const ok = readback === wanted;
    fs.writeFileSync(path.join(target, 'readback.json'), JSON.stringify({wanted, readback, ok}, null, 2));
    for (const record of records) x.release(record);
    x.release(file); x.close();
    console.log(JSON.stringify({wanted, readback, ok}));
    if (!ok) process.exitCode = 2;
    return;
  }
  const file = x.addFile('VNVKR_EncodingProbe.esp', true);
  const group = x.addElement(file, 'NOTE');
  const record = x.addElement(group, '.');
  x.addElementValue(record, 'EDID', 'VNVKR_EncodingProbe');
  x.addElementValue(record, 'FULL', wanted);
  const inMemory = x.getValue(record, 'FULL');
  const preview = JSON.parse(x.elementToJson(record));
  if (inMemory !== wanted) throw new Error('In-memory Unicode mismatch');
  fs.writeFileSync(path.join(target, 'preview.json'), JSON.stringify({wanted, inMemory, record: preview}, null, 2));
  // This is a disposable encoding fixture, not a mod to install.
  x.saveFile(file, pluginPath);
  x.release(record); x.release(group); x.release(file); x.close();
  console.log(JSON.stringify({pluginPath, wanted, inMemory, saved: fs.existsSync(pluginPath)}));
}
main().catch(error => {try {x.close();} catch {} console.error(error.stack); process.exitCode = 1;});
