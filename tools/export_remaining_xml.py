"""Emit xTranslator XML v2 using the publisher's TESVT_XMLFunc.pas schema.

Only text dictionaries are written. Neither plugins nor user SSTs are modified.
"""
import csv, hashlib, json, re
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET
from audit_remaining_translation import ROOT, HANGUL
from prepare_remaining_xml_work import WORK
from bgs_translator.sst.hash import format_no_edid_key

OUTPUT=ROOT/'VNV_Translation_Workspace/08_Korean_Deliverables/Plugins_XML_20261003'
TOKEN=re.compile(r'%%|(?<!\d)%(?:\d+\$)?[-+#0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[a-zA-Z]|</?(?:font|br|img|div|p)(?:\s[^<>]*)?/?>|&[A-Za-z0-9_]+;',re.I)
def read(n):return json.loads((WORK/(n+'.json')).read_text(encoding='utf-8'))
def write(n,obj):(OUTPUT/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def emit(path,plugin,rs):
    root=ET.Element('SSTXMLRessources');params=ET.SubElement(root,'Params')
    for tag,t in [('Addon',plugin),('Source','en'),('Dest','ko'),('Version','2')]:ET.SubElement(params,tag).text=t
    content=ET.SubElement(root,'Content')
    for r in rs:
        e=ET.SubElement(content,'String',{'List':str(r['list_index'])})
        ET.SubElement(e,'EDID').text=r.get('edid') or format_no_edid_key(r['formid'])
        attrs={'id':str(r['index_n']),'idMax':str(r['index_max'])} if r['index_max'] else {}
        ET.SubElement(e,'REC',attrs).text=r['signature']+':'+r['field']
        ET.SubElement(e,'Source').text=r['source'];ET.SubElement(e,'Dest').text=r['dest']
    ET.indent(root,space='  ');path.parent.mkdir(exist_ok=True,parents=True)
    # Character references retain CRLF through XML normalization/readback.
    data=ET.tostring(root,encoding='unicode').replace('\r','&#13;')
    path.write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'+data,encoding='utf-8')
    entries=ET.parse(path).getroot().findall('Content/String')
    assert len(entries)==len(rs)
    for e,r in zip(entries,rs):
        assert e.findtext('Source')==r['source'] and e.findtext('Dest')==r['dest']
        assert e.findtext('REC')==r['signature']+':'+r['field']
        assert int(e.get('List'))==r['list_index']
        assert int(e.find('REC').get('id','0'))==r['index_n']

def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    unique=read('unique')
    lookup={(r['signature'],r['field'],r['source']):r['dest'] for r in read('korean_translations')}
    for n in read('note_translations'):
        matches=[r for r in unique if r['source'].startswith(n['prefix'])]
        assert len(matches)==1,n['prefix']
        r=matches[0];lookup[(r['signature'],r['field'],r['source'])]=n['dest']
    assert all((r['signature'],r['field'],r['source']) in lookup for r in unique)
    accepted=read('accepted');pending=read('pending')
    for r in pending:r['dest']=lookup[(r['signature'],r['field'],r['source'])];r['method']='new_translation'
    rs=accepted+pending;corrected=[]
    for c in read('reuse_corrections'):
        matches=[r for r in rs if r['source'].startswith(c['prefix'])]
        assert matches,c['prefix']
        for r in matches:
            corrected.append(dict(r,previous_dest=r['dest']));r['dest']=c['dest'];r['method']='reviewed_current_source_correction'
    for r in rs:
        if r['source'].startswith('<div>\r\nIn order to heal a crippled limb,'):
            parts=['<div>\r\n불구가 된 부위를 치료하려면 침대에서 잠을 자거나, 의사를 찾거나, 스팀팩으로 직접 치료할 수 있습니다. 하드코어 모드에서는 의료 가방을 사용하거나 의사의 치료를 받아야 합니다.',
                   '스팀팩은 일반적인 체력 회복에 사용할 수 있으며, 이때 부위 손상도 조금 회복됩니다. 손상된 부위에 직접 사용해 부위를 치료할 수도 있습니다.']
            if '&sXBXBtn;' in r['source']:
                parts.append('스팀팩으로 부위를 직접 치료하려면 핍-보이의 능력치 화면에서 &sXBXBtn;을 눌러 부위 모드로 전환하세요. &sXBLStick;로 부위를 선택하고 &sXBABtn;을 눌러 선택한 부위에 스팀팩을 사용하세요.')
            else:parts.append('스팀팩으로 부위를 직접 치료하려면 핍-보이의 능력치 화면에서 해당 부위를 마우스 왼쪽 버튼으로 클릭하세요.')
            parts.append('황무지에는 여러 종류의 스팀팩이 있습니다. 능력치 화면에 표시되는 수량은 소지한 모든 종류의 스팀팩을 합친 값입니다. 이 화면에서 스팀팩을 사용하면 가장 약한 종류부터 소비됩니다.')
            if '&sXBXBtn;' in r['source']:parts.append('하드코어 모드에서는 의료 가방을 사용하거나 의사의 치료를 받아야 불구가 된 부위를 치료할 수 있습니다.')
            corrected.append(dict(r,previous_dest=r['dest']));r['dest']='\r\n<p>\r\n'.join(parts);r['method']='reviewed_current_source_correction'
    # All new/reused dictionaries must preserve actual script variables and UI tags.
    for r in rs:
        if r['method']=='user_existing_korean':continue
        assert Counter(TOKEN.findall(r['source']))==Counter(TOKEN.findall(r['dest'])),(r['plugin'],r['source'],r['dest'])
        if r['signature']=='MESG':
            assert all(r['source'].count(t)==r['dest'].count(t) for t in ('^','|'))
        assert '\ufffd' not in r['source']+r['dest']
    grouping=defaultdict(list)
    for r in rs:
        if r['method']=='user_existing_korean' or r['source']==r['dest']:continue
        grouping[r['plugin']].append(r)
    summary=[]
    input_summary=json.loads((ROOT/'reports/remaining_translation_audit/summary.json').read_text(encoding='utf-8'))
    for f in input_summary:
        plugin=f['plugin'];source=ROOT/'VNV_Translation_Workspace/01_Plugins'/plugin
        assert hashlib.sha256(source.read_bytes()).hexdigest()==f['sha256']
        group=grouping[plugin]
        addition=[r for r in group if r['method'] in ('new_translation','reviewed_normalized_source_reuse','reviewed_equivalent_wording_reuse','reviewed_current_source_correction')]
        if group:emit(OUTPUT/(plugin+'_en_ko.xml'),plugin,group)
        if addition:emit(OUTPUT/'추가분만'/(plugin+'_추가_en_ko.xml'),plugin,addition)
        summary.append(dict(plugin=plugin,xml_entries=len(group),additional_entries=len(addition),already_korean=sum(r['plugin']==plugin and r['method']=='user_existing_korean' for r in rs),source_sha256=f['sha256'],methods=dict(Counter(r['method'] for r in group))))
    write('translation_rows.json',rs);write('internal_unchanged.json',read('locked'));write('reuse_corrections_applied.json',corrected)
    stats=dict(plugins=summary,new_unique_texts=sum(lookup[(r['signature'],r['field'],r['source'])]!=r['source'] for r in unique),new_translated_units=sum(r['dest']!=r['source'] for r in pending),corrected_reuse_units=len(corrected),exported_entries=sum(len(v) for v in grouping.values()),internal_unchanged=len(read('locked')),unresolved_player_texts_in_audited_fields=0,retained_abbreviations=['LAER'],validation={'xml_readback':'passed','variables_and_ui_markup':'passed','source_hashes':'passed','native_supplement_fields':271,'xTranslator_import':'not_run','game_test':'not_run'},xml_schema_source='https://github.com/MGuffin/xTranslator/blob/main/TESVT_XMLFunc.pas')
    write('validation.json',stats)
    # Vanilla xTranslator omits the FNV low-Intelligence player response field.
    # Ship a reviewable definition copy; never edit the installed application.
    definition_source=Path(r'F:/번역/프로그램/xTranslator/Data/FalloutNV/_recorddefs.txt')
    defs=definition_source.read_text(encoding='utf-8-sig')
    if 'Def_:TDUM=DIAL=0' not in defs:
        assert 'Def_:FULL=****=0' in defs
        defs=defs.replace('Def_:FULL=****=0','Def_:TDUM=DIAL=0\nDef_:FULL=****=0',1)
    def_output=OUTPUT/'xTranslator_필드설정/Data/FalloutNV/_recorddefs.txt'
    def_output.parent.mkdir(parents=True,exist_ok=True)
    def_output.write_text(defs,encoding='utf-8')
    write('xtranslator_definition_patch.json',dict(source=str(definition_source),source_sha256=hashlib.sha256(definition_source.read_bytes()).hexdigest(),added='Def_:TDUM=DIAL=0',purpose='DIAL TDUM Dumb Response: low-Intelligence player choice',installed_application_modified=False,xedit_definition_source='https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFNV.pas'))
    with (OUTPUT/'번역 검토.csv').open('w',encoding='utf-8-sig',newline='') as fp:
        w=csv.writer(fp);w.writerow(['플러그인','FormID','EDID','레코드','반복 번호','방식','원문','번역'])
        for group in grouping.values():
            for r in group:w.writerow([r['plugin'],f'{r["formid"]:08X}',r.get('edid'),r['signature']+':'+r['field'],r['index_n'],r['method'],r['source'],r['dest']])
    lines=['# VNV 남은 플러그인 번역 XML (2026-10-03)','',
       '상위 폴더의 XML은 기존 번역 재사용분과 신규 번역·수정분을 합친 파일입니다. 우선 이 파일을 사용하세요.',
       '`추가분만` 폴더는 이번에 추가·검토·수정한 항목만 담았습니다. 기존 SST 적용 뒤 추가분만 가져오려는 경우 사용할 수 있습니다. 두 세트를 모두 적용할 필요는 없습니다.','',
       '1. xTranslator를 종료하고 설치 폴더의 `Data/FalloutNV/_recorddefs.txt`를 백업하세요. 동봉한 `xTranslator_필드설정` 안의 파일로 교체한 뒤 다시 실행하세요. 기존 필드 정의에 `Def_:TDUM=DIAL=0` 한 줄만 추가한 복사본입니다. 저지능 전용 대화 선택지(TDUM)를 표시하기 위해 필요합니다. 현재 버전의 정의가 바뀌었다면 새 정의에서 FULL/DESC fallback 바로 앞에 그 한 줄을 직접 추가하세요.',
       '2. xTranslator를 FalloutNV 모드, 원문 en / 번역 ko로 열고 `01_Plugins`에 있는 같은 이름의 플러그인을 불러옵니다.',
       '3. 해당 XML을 가져옵니다. EDID/레코드와 원문을 함께 대조하는 방식으로 적용하세요.',
       '4. 수치와 새 대사를 확인한 뒤 플러그인을 저장하고 SST를 생성합니다. 저장한 번역본은 기존 `번역 완료` 폴더에 넣으시면 됩니다.','',
       '| 플러그인 | 합본 XML 항목 | 추가·수정 항목 | 이미 한글인 항목 |','|---|---:|---:|---:|']
    for f in summary:lines.append(f'| {f["plugin"]} | {f["xml_entries"]} | {f["additional_entries"]} | {f["already_korean"]} |')
    lines+=['','Atmospheric Lighting Tweaks와 Bad Touch는 조사한 표시 텍스트가 이미 한글이라 새 XML이 필요하지 않습니다.',
       f'신규 번역은 {stats["new_unique_texts"]}개 고유 문구이며, {stats["new_translated_units"]}개 항목에 적용됩니다. 기존 재사용 번역 {len(corrected)}개 항목의 잘못된 수치·누락 문단도 고쳤습니다. 변수(%g, %.0f, %%), UI 태그와 버튼 토큰을 검증했습니다.',
       'QUST:NNAM 목표, REFR 지도명, XATO 동작 이름, TDUM 대사 표시, BPTN 부위명, NOTE:TNAM 쪽지 본문 등 기본 추출에서 빠졌던 필드를 공식 xEditLib 읽기로 보완했습니다. 반복 번호와 List는 기존 SST 및 xTranslator FalloutNV/_recorddefs.txt와 같은 레코드의 필드 순서에서 확인했습니다.',
       '내부 EditorID/디버그 이름, 배우 연기 지시문(NAM2), 메타데이터, 빈 문자열은 원문으로 유지했습니다. LAER는 무기 약어로 유지했습니다.',
       'XML 형식은 xTranslator 제작자의 TESVT_XMLFunc.pas(v2)에서 확인했습니다. 파싱과 원문·번역·식별값 재읽기는 통과했습니다. 실제 xTranslator 가져오기와 게임 내 표시는 아직 확인하지 않았습니다.',
       '스크립트 내부 문자열이나 Radio 호환 ESP의 컴파일 작업은 이 XML 범위에 포함되지 않습니다. 이 파일로 VNV 전체 스크립트가 완역됐다는 뜻은 아닙니다.',
       '사용자가 새로 완료한 FalloutNV, DeadMoney, OldWorldBlues ESM/SST는 수신·재사용했으며 이 파일에서 다시 번역하지 않았습니다. 게임, MO2, 사용자 플러그인과 SST는 수정하지 않았습니다.',
       '현재 배포 EXE/Output은 이 XML을 자동으로 포함하지 않습니다. xTranslator 반영본을 받은 뒤 패쳐 데이터에 통합할 수 있습니다.','',
       '[XML 형식 출처](https://github.com/MGuffin/xTranslator/blob/main/TESVT_XMLFunc.pas)']
    (OUTPUT/'읽어주세요.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
