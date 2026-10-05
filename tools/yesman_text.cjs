// Supported xEditLib API adapter; no ESP/ESM byte parser or binary writer.
const fs = require('fs');
const path = require('path');
const dependencyRoot=process.env.VNVKR_NODE_MODULES || require('path').resolve(__dirname,'../.tools/YesMan-AI/node_modules');
const x = require(require('path').join(dependencyRoot,'xeditlib'));
const crypto = require('crypto');
function json(file) {return JSON.parse(fs.readFileSync(file,'utf8'));}
function fieldName(handle) {
  const match = /^([A-Z0-9_]{4})(?: -|$)/.exec(x.name(handle));
  return match ? match[1] : null;
}
function textFields(record, wanted) {
  const found=[];
  const signature=x.signature(record);
  const flatSignatures=new Set(['CELL','WRLD','REFR','ACRE','ACTI','ARMO','ARMA','WEAP','MISC','KEYM',
    'ALCH','CLAS','RACE','HDPT','HAIR','EYES','CSNO','AMEF','REPU','RCCT','FURN','MSET','COBJ','IMOD',
    'CMNY','LIGH','GMST','PROJ','CCRD','DOOR','NPC_','CREA','CONT','ENCH','TACT','MGEF','AMMO','CDCK',
    'BOOK','RCPE','MSTT','CHAL','INGR','CHIP','SPEL','NOTE','EXPL','DIAL','LSCR','WATR','ALOC']);
  if(flatSignatures.has(signature)) {
    for(const field of wanted) {
      const paths=signature==='REFR' && field==='FULL' ? ['FULL','XMRK\\FULL'] :
        signature==='NOTE' && field==='TNAM' ? ['TNAM\\Text'] : [field];
      for(const relative of paths) {
        if(!x.hasElement(record,relative))continue;
        const child=x.getElement(record,relative);
        if([3,4].includes(x.valueType(child)))found.push({field,path:relative,source:x.getValue(child)});
        x.release(child);
      }
    }
    return found;
  }
  // Only these named binary containers can enclose the selected display fields.
  // Other named subrecords (DATA physics, CTDA conditions, SCHR script metadata)
  // cannot contain these text fields and need no recursive text traversal.
  const displayContainers=new Set(['XMRK','EPFT','RDAT']);
  function walk(handle, inherited=null, prefix='') {
    let children;
    try {children=x.getElements(handle);} catch {return;}
    for (const child of children) {
      // Child groups belong to other records, not to this record's string fields.
      if([0,1,2,10,11,13].includes(x.elementType(child))) {x.release(child);continue;}
      const namedField=fieldName(child), field=namedField || inherited;
      const part=x.pathName(child,true) || x.pathName(child,false) || x.name(child);
      const relative=prefix ? prefix+'\\'+part : part;
      // vtString=3, vtLString=4 (e.g. MESG DESC). Keep both display types.
      if (field && wanted.has(field) && [3,4].includes(x.valueType(child))) {
        found.push({field,path:relative,source:x.getValue(child)});
      } else if ([9,10,11].includes(x.valueType(child)) &&
                 (!namedField || wanted.has(namedField) || displayContainers.has(namedField))) walk(child,field,relative);
      x.release(child);
    }
  }
  walk(record); return found;
}
const fileIdentities=new Map();
function identity(file, record) {
  if(!fileIdentities.has(file))fileIdentities.set(file,{masters:x.getMasterNames(file),name:x.name(file)});
  const local=x.getFormID(record,true), meta=fileIdentities.get(file), owner=meta.masters[local>>>24] || meta.name;
  return {owner:owner.toLowerCase(),id:(local & 0xffffff).toString(16).padStart(6,'0'),signature:x.signature(record)};
}
function key(row) {return [row.owner,row.id,row.signature].join('|');}
function recordJson(record) {
  // Serialize direct elements only: full CELL/DIAL JSON recursively expands
  // child records, which must be audited separately under their own identities.
  const signature=x.signature(record);
  const obj=['CELL','DIAL','WRLD'].includes(signature) ? {} : JSON.parse(x.elementToJson(record));
  if(['CELL','DIAL','WRLD'].includes(signature)) {
    for(const child of x.getElements(record)) {
      if(![0,1,2].includes(x.elementType(child)) && !/^Child Group/.test(x.name(child))) {
        Object.assign(obj,JSON.parse(x.elementToJson(child)));
      }
      x.release(child);
    }
  }
  if(obj['Record Header']) delete obj['Record Header']['Data Size']; // derived byte count
  const group=x.getElementGroup(record);
  obj.$parent=x.path(group,true,true); x.release(group);
  return obj;
}
function digest(record) {return crypto.createHash('sha256').update(JSON.stringify(recordJson(record))).digest('hex');}
function headerDigest(file) {
  const header=x.getElement(file,'File Header');
  const obj=JSON.parse(x.elementToJson(header)); x.release(header);
  if(obj['Record Header'])delete obj['Record Header']['Data Size'];
  if(obj['HEDR - Header'])delete obj['HEDR - Header']['Number of Records'];
  // PrepareSave may reorder TES4 ONAM without changing membership. Treat ONAM
  // as a set so real additions/removals still fail while harmless order churn does not.
  if(Array.isArray(obj['ONAM - Overriden Forms']))obj['ONAM - Overriden Forms'].sort();
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}
function savePreservingReferences(file, target, plugins) {
  // xEdit's PrepareSave promotes temporary ESM overrides when an ancestor is
  // persistent. Suspend that condition in copied session memory only. Ancestor
  // files are never saved while suspended; restore and audit them in finally.
  const flagPath='Record Header\\Record Flags', flag='Quest item / Persistent reference';
  const signatures=['REFR','PGRE','PMIS','ACHR','ACRE','PARW','PBEA','PFLA','PCON','PBAR','PHZD'];
  const ranks=new Map(plugins.map((p,i)=>[p.toLowerCase(),i]));
  const rank=ranks.get(x.name(file).toLowerCase());
  const suspended=new Map();
  function suspend(ancestor) {
    const parent=x.getElementFile(ancestor), name=x.name(parent); x.release(parent);
    if((ranks.get(name.toLowerCase()) ?? Infinity)>=rank) {x.release(ancestor);return;}
    const k=name.toLowerCase()+'|'+x.getFormID(ancestor,true);
    if(suspended.has(k) || !x.getFlag(ancestor,flagPath,flag)) {x.release(ancestor);return;}
    suspended.set(k,{handle:ancestor,hash:digest(ancestor)});
    x.setFlag(ancestor,flagPath,flag,false);
  }
  try {
    for(const signature of signatures) {
      for(const record of x.getRecords(file,signature,true).sort((a,b)=>b-a)) {
        try {
          if(x.isMaster(record) || x.getFlag(record,flagPath,flag))continue;
          const master=x.getMasterRecord(record);
          const overrides=x.getOverrides(master);
          suspend(master);
          for(const prior of overrides)suspend(prior);
        } finally {x.release(record);}
      }
    }
    x.saveFile(file,target);
    return {temporarily_suspended_ancestors:suspended.size};
  } finally {
    // Restore every ancestor before comparing hashes, including failure paths.
    for(const saved of suspended.values())x.setFlag(saved.handle,flagPath,flag,true);
    let failure;
    for(const saved of suspended.values()) {
      if(digest(saved.handle)!==saved.hash)failure=new Error('Ancestor structure was not restored');
      x.release(saved.handle);
    }
    if(failure)throw failure;
  }
}
function destinations(item, candidates, exactOnly=false) {
  const same=candidates.filter(c=>c.field===item.field && c.source===item.source);
  const exact=same.filter(c=>c.path===item.path);
  return new Set((exactOnly ? exact : (exact.length ? exact : same)).map(c=>c.dest));
}
async function main() {
  const request=json(process.argv[2]);
  const game=path.resolve(request.game);
  x.init(); x.setLanguage('English'); x.setGamePath(game+path.sep); x.setGameMode(x.GM_FNV);
  const koffi=require(path.join(dependencyRoot,'koffi'));
  const acp=koffi.load('kernel32.dll').func('uint GetACP()')();
  if (acp!==65001 && (['apply','verify'].includes(request.mode) || request.readCodepage!==acp))
    throw new Error('Run mutations with the isolated UTF-8 Node runtime');
  x.loadPlugins(request.plugins.join('\n'),true,false); await x.waitForLoader();
  const result={engine:'YesManAI/xEditLib',acp,files:[]};
  const fallbackByRecord=new Map();
  for(const mapping of request.fallbackMappings || []) {
    if(typeof mapping.dest!=='string' || mapping.dest.includes('\uFFFD')) throw new Error('Invalid fallback translation text');
    const k=key(mapping); if(!fallbackByRecord.has(k))fallbackByRecord.set(k,[]); fallbackByRecord.get(k).push(mapping);
  }
  const inheritTargets=new Set((request.inheritTargets || []).map(name=>name.toLowerCase()));
  const legacyFallbackRecordKeys=new Set(request.legacyFallbackRecordKeys || []);
  for (const plugin of request.targets || request.plugins) {
    const file=x.fileByName(plugin), rows=[], structures=[], changed=[], missing=[], beforeHashes=[];
    const headerHash=headerDigest(file);
    if(request.expectedHeaders?.[plugin] && headerHash!==request.expectedHeaders[plugin])
      throw new Error('Plugin header readback mismatch '+plugin);
    fileIdentities.set(file,{masters:x.getMasterNames(file),name:x.name(file)});
    const expected=new Map((request.expected?.[plugin] || []).map(r=>[key(r),r]));
    const expectedChanges=new Map();
    for(const update of request.changes?.[plugin] || []) {
      const k=key(update); if(!expectedChanges.has(k))expectedChanges.set(k,[]);
      expectedChanges.get(k).push(update);
    }
    const verified=new Set();
    const mappings=request.mappings && request.mappings[plugin] || [];
    const legacyRows=new Map((request.legacySources?.[plugin] || []).map(r=>[key(r)+'|'+r.path,r]));
    const legacyRecordKeys=new Set(request.legacyRecordKeys?.[plugin] || []);
    const inheritanceAllowed=inheritTargets.has(plugin.toLowerCase());
    const byRecord=new Map();
    for(const mapping of mappings) {
      if(typeof mapping.dest!=='string' || mapping.dest.includes('\uFFFD')) throw new Error('Invalid translation text');
      const k=key(mapping); if(!byRecord.has(k))byRecord.set(k,[]); byRecord.get(k).push(mapping);
    }
    // Apply/readback visit every record, including signatures without display
    // fields. This verifies untouched scripts, references and gameplay records.
    const allRecords=['apply','verify','snapshot','verifyLegacy'].includes(request.mode) ? x.getRecords(file,'',true) : null;
    const groups=allRecords ? [['*',allRecords]] : Object.keys(request.fields).map(signature=>[signature,null]);
    for (const [group,all] of groups) {
      const signature=group;
      if (signature==='TES4') continue; // author/description metadata is not game UI.
      // Free high handles first. xEditLib's free-slot allocator otherwise
      // repeatedly scans the live suffix of a large record array (quadratic).
      const records=(all || x.getRecords(file,signature,true)).sort((a,b)=>b-a);
      for (const record of records) {
        const signature=x.signature(record), fields=request.fields[signature] || [];
        if(signature!=='TES4') {
          const ident=identity(file,record), recordKey=key(ident);
          const wantsRows=request.includeRows!==false &&
            (!request.legacyRecordKeys || legacyRecordKeys.has(recordKey) ||
             (inheritanceAllowed && legacyFallbackRecordKeys.has(recordKey)));
          const needsItems=request.structures || wantsRows || request.mode==='apply';
          let edid='';
          if(needsItems && x.hasElement(record,'EDID')) edid=x.getValue(record,'EDID');
          const items=needsItems && (signature!=='GMST' || edid.startsWith('s')) && fields.length ?
            textFields(record,new Set(fields)) : [];
          if(request.structures && items.length) structures.push({...ident,json:recordJson(record)});
          let originalDigest;
          if(['apply','snapshot'].includes(request.mode)) originalDigest=digest(record);
          const updates=[];
          for(const item of items) {
            const row={...ident,edid,...item};
            const nativeSource=row.source;
            if(request.mode==='apply' && row.source.includes('\uFFFD')) {
              const legacy=legacyRows.get(key(row)+'|'+row.path);
              if(legacy && !legacy.source.includes('\uFFFD'))row.source=legacy.source;
            }
            if(wantsRows) rows.push(row);
            if(request.mode==='apply') {
              let candidates=byRecord.get(recordKey) || [], mappingOrigin='catalog', exactOnly=false;
              if(!candidates.length && inheritanceAllowed) {
                const inherited=(fallbackByRecord.get(recordKey) || [])
                  .filter(candidate=>candidate.field===row.field && candidate.path===row.path);
                // No Fixed ESM translation exists for this field, so this is not
                // an inheritance failure and should not inflate the untranslated count.
                if(!inherited.length)continue;
                candidates=inherited; mappingOrigin='base_inherited'; exactOnly=true;
              }
              const possible=destinations(row,candidates,exactOnly);
              if(possible.size!==1) {
                const reason=mappingOrigin==='base_inherited'
                  ? (possible.size ? 'base_inheritance_ambiguous' : 'base_record_text_changed')
                  : (possible.size ? 'ambiguous' : 'unmatched');
                missing.push({...row,reason,mappingOrigin}); continue;
              }
              const dest=[...possible][0];
              if(dest!==row.source) {
                if(row.source.includes('\uFFFD')) {missing.push({...row,reason:'source_encoding_unreadable',mappingOrigin});continue;}
                x.setValue(record,row.path,dest);
                updates.push({...row,dest,mappingOrigin,...(nativeSource!==row.source ? {nativeSource} : {})});
              }
            }
          }
          if(request.mode==='apply') {
            // Revert only edited text and compare xEdit's full record serialization.
            for(const update of updates)x.setValue(record,update.path,update.nativeSource ?? update.source);
            if(updates.length && digest(record)!==originalDigest)throw new Error('Unexpected non-text mutation '+key(ident));
            for(const update of updates)x.setValue(record,update.path,update.dest);
            changed.push(...updates); beforeHashes.push({...ident,hash:originalDigest});
          } else if(request.mode==='snapshot') {
            beforeHashes.push({...ident,hash:originalDigest});
          } else if(['verify','verifyLegacy'].includes(request.mode)) {
            const prior=expected.get(key(ident));
            if(!prior)throw new Error('Unexpected record in readback '+key(ident));
            verified.add(key(ident));
            const updates=expectedChanges.get(key(ident)) || [];
            for(const update of updates) {
              if(request.mode==='verify') {
                if(x.getValue(record,update.path)!==update.dest)throw new Error('Translation readback mismatch '+key(ident));
                x.setValue(record,update.path,update.nativeSource ?? update.source);
              } else {
                const legacy=legacyRows.get(key(update)+'|'+update.path);
                if(!legacy)throw new Error('Missing legacy snapshot field '+key(ident));
                x.setValue(record,update.path,legacy.source);
              }
            }
            if(digest(record)!==prior.hash)throw new Error('Record structure readback mismatch '+key(ident));
          }
        }
        x.release(record);
      }
    }
    if(['verify','verifyLegacy'].includes(request.mode) && verified.size!==expected.size)throw new Error('Records missing from readback '+plugin);
    if(request.mode==='apply') {
      fs.mkdirSync(request.outDir,{recursive:true});
      const target=path.join(path.resolve(request.outDir),plugin);
      if(fs.existsSync(target))throw new Error('Output already exists '+target);
      const saveAudit=savePreservingReferences(file,target,request.plugins);
      console.log(JSON.stringify({plugin,...saveAudit}));
    }
    result.files.push({plugin,masters:x.getMasterNames(file),headerHash,rows,
      ...(request.structures ? {structures} : {}),
      ...(request.mode==='apply' ? {changed,missing,beforeHashes} : {}),
      ...(request.mode==='snapshot' ? {beforeHashes} : {})}); x.release(file);
    console.log(JSON.stringify({plugin,units:rows.length,mode:request.mode||'read'}));
  }
  x.close();
  fs.mkdirSync(path.dirname(path.resolve(request.output)),{recursive:true});
  fs.writeFileSync(request.output,JSON.stringify(result,null,2));
  console.log(JSON.stringify({output:request.output,files:result.files.map(f=>({plugin:f.plugin,units:f.rows.length}))}));
}
main().catch(error=>{try{x.close();}catch{}console.error(error.stack);process.exitCode=1;});
