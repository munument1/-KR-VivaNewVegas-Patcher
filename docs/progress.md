# 진행 상태

## 2026-10-03 최종 패쳐 조립 갱신

- 활성 플러그인 37개에 104,195건 번역 적용 후 UTF-8 fresh readback 37/37 및 CP1252 legacy readback 37/37 통과.
- 비활성 선택 변형 3개도 별도 정밀 검증 통과: YUP 선택판 15,151건, HighPriorityLOD 2건, TreeLOD_Vanilla 6건.
- 총 40개 플러그인 모두 정확한 원본 SHA-256용 xdelta3 fast path를 제작하고 encode/decode 라운드트립으로 번역본 SHA-256 일치를 확인함.
- `vnvkr_output.py`는 정확한 검증 원본이면 xdelta fast path를 사용하고, 원본 해시가 달라진 업데이트 플러그인만 YesMan-AI/xEditLib 레코드 병합 경로로 전환함.
- 빠른 실제 Output 시험: 69개 파일, 제외 0개, 약 12.54초. 플러그인 40개 모두 `exact_source_verified_delta` 상태.
- 패키징된 `VNVKoreanPatcher.exe --self-test C:\\Modlists\\VNV`가 배포 폴더의 TranslationData/Backend를 실제 사용해 Output을 생성하고 ExitCode 0, 약 16.77초로 통과.
- 자동 테스트 35/35 통과.
- 최종 폰트 후보를 사용자 실사용 tNVSE 설정 기반으로 교체: Pretendard Bold / NanumSquare ExtraBold / TmonMonsori / NeoDunggeunmo Pro. 슬롯 1~8 및 42, `uiEncoding=4`, `bUTF8=1`, Dictionary runtime translation OFF. 모든 사용 폰트가 한글 완성형 11,172자를 포함함.
- tNVSE DLL 및 `TTW KOR Radio + UI.esp`는 배포물에서 제외. tNVSE 71 이상은 별도 설치 요구.
- 현재 배포 폴더는 약 449.6MB이며 TranslationData 약 201.2MB, 업데이트 fallback용 Backend 약 220.5MB. 게임 내 실제 플레이 QA와 KR-RADIO 19개 compiled script 충돌 호환 ESP는 아직 남음.

2026-10-03. VNV 설치 완료 경로는 `C:/Modlists/VNV`이며 선택 프로필은 Viva New Vegas Extended입니다. 기존 한글 번역은 아직 적용하지 않은 상태입니다.

- 구현: MO2 오프라인 파일 목록, 해시가 고정된 xdelta3 차분 생성·검증·적용, 별도 출력, 원본/프로필 보호.
- 검증: 합성 파일을 사용한 실제 xdelta 왕복 및 오류 거부 시험 14개 통과. 게임 플러그인 구조 및 실제 구동 검증은 아직 수행하지 않음.
- 확보: 사용자 제공 본편/라디오·UI 번역 원천, K-font, XP font fix, Bit-O-Matic, tNVSE 본체 및 기본 설정 ZIP의 목록/해시.
- 준비: 설치하지 않은 tNVSE CP949 + UTF-8 감지 후보와 슬롯 1~8 설정 조각.
- 감사: 기존 원천에서 한글 문구 확인. 추출 도구의 인코딩 분기/원문 바이트/문맥 누락은 별도 기록.
- 수집: `VNV_Translation_Workspace`에 활성 ESP/ESM 43개, 비활성 선택본 3개, MCM/Translations 및 UI·스크립트 참고 파일을 모음. Base/Extended 프로필 및 모드 메타정보를 복사하고 BSA 22개에서 텍스트 후보 121개를 추출함. 741개 수집 파일의 복사본/원본 SHA-256 일치를 확인했으며 설치 상태는 변경하지 않음.

## 사용자 번역본 접수

처음에는 사용자가 직접 번역하고 에이전트가 검증/패키징만 담당했으나, 후속 요청으로 남은 플러그인·MCM·Translations 번역 작업도 명시적으로 승인했습니다. 남은 플러그인은 XML로 전달하고 사용자가 반영한 뒤 SST로 저장합니다. 이미 완료한 사용자 번역본은 보존합니다.

본편/DLC의 추가 작업은 사용자 지시에 따라 `Fallout NV KR.esm`을 우선 번역 원천으로 사용하고 SST는 보조 대조 자료로 사용합니다. 목표 구조는 현재 VNV Fixed ESMs를 유지합니다. KR-RADIO의 새 방송 레코드는 별도 호환 ESP가 필요하며, Fixed ESMs에 모두 포함돼 있지 않습니다.

- `01_Plugins/번역 완료`의 ESP/ESM 27개를 입력 후보로 등록함.
- `01_Plugins` 루트에는 추가 작업 중인 파일 10개가 있음. FalloutNV.esm, DeadMoney.esm, OldWorldBlues.esm은 이쪽에 있으며 같은 이름의 SST 사전이 있음. HonestHearts, LonesomeRoad, GRA 및 시작 장비 팩 4개는 완료 폴더에 있음.
- 최초 수집한 활성 플러그인 43개 중 6개는 현재 플러그인 폴더에서 발견되지 않음. 번역 불필요로 사용자가 제외했는지 아직 확인하지 않았으며 자동 복원하지 않음.
- Optional 3개는 사용자 완료 보고를 기록함. 현재 Output에는 설치된 각 제공 모드 폴더에 복사본을 넣으며 활성화나 로드 순서는 변경하지 않음.
- MCM 추가 작업 목록은 itr-nvse.json 및 SoMS.json 2개임. 사용자가 정리한 목록을 유지함.
- Translations는 INI 사전 7개임. 총 582개 대입 항목 중 빈 값 1개가 있음. 중복 키(AguaFria의 $ActionPoints, ExtraGoodies의 $Level), 메시지 제어 접두사 및 %% 보호 표기를 기록함.
- 지정한 xTranslator FalloutNV UserDictionaries 루트의 SST 95개를 목록화하고 공식 SST 리더로 내부 영문·한글·필드 식별 정보를 대조함. Auto/Backup/백업 하위 폴더는 제외함. 같은 이름의 사전 존재만으로 원문/레코드 매칭 성공을 판정하지 않음.
- 원본 플러그인 및 Optional 제공 파일 46개는 수집 당시의 SHA-256과 모두 일치함. 사용자 번역본의 구조·스크립트 보존과 게임 구동 검증은 별도 단계임.

상세 현황은 로컬 `VNV_Translation_Workspace/00_Translation_Status_20261003/번역작업현황.md` 및 `intake.json`에 기록함. `tools/audit_translation_intake.py`는 플러그인/SST 내부 구조를 해석하지 않는 파일 목록 도구이며 원본과 사용자 번역 파일을 수정하지 않음.

최종 설치 흐름은 VNV 및 tNVSE 설치 후 MO2 위치를 입력해 `Output`을 생성하고, 사용자가 Output 안의 `mods` 폴더를 MO2 루트에 직접 복사하는 것입니다. 프로그램은 설치 원본을 수정하지 않습니다. 글꼴·tNVSE 설정·보충 텍스트 번역 ESP·번역 텍스처는 후속 포함 대상이며 현재 Output에는 없습니다. Fallout NV KR.esm 스크립트 번역의 별도 ESP는 실제 스크립트/레코드 대조 뒤 제작합니다.

## 수동 덮어쓰기 Output 구현

- `vnvkr_output.py`: 실제 선택 프로필의 loose 제공 경로를 찾고, 설치와 동일한 `mods/<제공 모드>/<Data 상대 경로>`로 출력함. Steam Data의 시작 장비 팩은 활성 Fixed ESMs 모드에 배치함.
- 사용자 완료 27개 + Optional 3개 + MCM 2개 + INI 7개, 총 39개 파일을 Output에 생성함. 원본 해시 재검사에서 변경 0개.
- MCM/INI 906개 항목, 표시 문구 변경 867개, 브랜드명·단위 유지 39개, 미대응 0개. JSON 설정 구조·INI 중복 키·보호 토큰 검사를 통과함.
- 업데이트된 MCM/INI는 항목별 병합하여 새 항목·변경된 영문·모호한 대응을 원문으로 남김. 파일 제공 모드 이름이 달라져도 현행 경로로 출력함.
- 업데이트된 플러그인의 부분 번역은 아직 미구현. 버전이 달라지면 해당 파일을 제외하고 다른 출력은 계속함. 전체 작업 실패로 처리하지 않음.
- 자동 검사 24개 통과. GUI 구성 smoke 통과. 게임 구동 및 플러그인 내부 구조 검증은 미수행.
- `vnvkr_gui.py`, `VNV_KR_Output.cmd`: MO2 경로 입력 → Output 생성. 기존 출력은 보존하고 새 이름을 사용함.

## FalloutNV 레코드 도구 전환과 Radio 감사

기존 xEdit MCP 실행기는 FalloutNV를 지원하지 않아 실행을 거절했다. 이후 사용자가 제공한 YesManAI 도구를 선택하라는 지시에 따라 공식 YesMan-AI의 xEditLib API로 작업을 전환했다. API가 플러그인 읽기·저장을 담당하며 임의 플러그인 바이너리 파서는 작성하지 않았다. 원본과 분리한 복사본만 사용한다. 별도 Node 복사본에 UTF-8 프로세스 매니페스트를 적용해 한글 저장과 새 세션 readback을 확인했으며, 시스템 로캘과 설치된 Node는 변경하지 않았다.

- 실제 MercenaryPack 복사본에 새 NOTE, 변경된 영문 메시지, 변경된 장비 무게를 넣은 업데이트 시험에서 알려진 문구 3개만 번역되고 새/변경 영문 2개는 그대로 남았다. 전체 레코드 구조의 새 세션 readback도 통과했다.
- `vnvkr_yesman.py`와 `tools/yesman_text.cjs`에 항목별 플러그인 병합/전체 레코드 재검증 경로를 구현했다. 사용자 완료본 27개에서 기능 필드가 일치하는 번역 22,979개를 회수했다. 보호 토큰이 바뀐 1개는 보류하며, 기능 차이 레코드 115개와 인코딩 확인이 필요한 문구는 별도 기록한다.
- 자동 검사 28개 통과. 실제 VNV 전체 native Output의 새 세션 검증에서 YUP의 ACRE `FalloutNV.esm:138C03`에 persistent flag와 Temporary/Persistent 그룹 변화가 탐지됐다. xEditLib 저장 전후의 차이이므로 무시하지 않고 새 Output 게시를 중단했다. 기존 Output와 배포 EXE는 그대로이며 native 백엔드는 아직 실험 경로다. 저장 API의 자동 보정 제어 또는 다른 검증된 적용 경로를 해결해야 한다.
- 공식 API를 UTF-8/CP1252 두 프로세스 인코딩으로 대조해 기존 CP1252 표시 문구 15개가 저장 후에도 그대로임을 확인했다. 프로세스 매니페스트만 사용했고 시스템 로캘은 바꾸지 않았다.
- `Fallout NV KR.esm` 90,402개는 모두 현행 대응 레코드다. KR-RADIO 2,915개 중 2,237개는 자체 새 레코드이며 한국어 방송 MESG 416개와 대화/스크립트 연결이 있다.
- Radio override 678개를 현행 및 Steam 폴더 master 복사본으로 비교했다. 기존 VNV와 Radio가 모두 바꾼 compiled script block 19개를 찾았다. Goodies 등의 퀘스트 처리 코드가 덮이는 사례가 있어 원본 Radio ESP 전체 복사 대신 별도 호환 ESP 병합이 필요하다.
- 기존 추출 스키마가 놓친 표시 필드 번역 재사용 후보 2,598개도 공식 API로 확보했다. 실제 문맥/필드 경로를 포함해 별도 감사 파일에 기록했으며 아직 전체 적용 완료를 뜻하지 않는다.

Radio 상세 계획: [radio-compatibility.md](radio-compatibility.md). 호환 ESP 저장·스크립트 컴파일·게임 실행은 아직 수행하지 않았다.

남은 작업: 추가 플러그인 번역 XML 전달, 사용자 반영/SST를 토대로 번역 데이터 갱신, FNV 레코드 백엔드 및 보충 스크립트 ESP, 글꼴·설정·텍스처 포함, 실제 게임 검증.

## 최신 tNVSE 폰트 및 미대응 단위 재확인

2026-10-03 공식 Nexus 최신 버전 71과 GitHub HEAD를 재확인했다. 제공 ZIP과 같은 버전 표기이며 버전 63부터 FreeType 기반 폰트 방식이 추가됐다. TTF/OTF/TTC/OTC + `tnvse_fonts.xml` 구성과 기존 비트맵 `.fnt/.Tex` 구성을 구별한다. 제공 Default Config의 활성 font 항목은 0개이므로 새 한글 face와 XML 구성이 필요하다. 기존 미설치 비트맵 후보와 게임 설치는 수정하지 않았다.

사용자 재확인대로 미대응은 ESP 전체가 아니라 문구/필드 단위다. 동일 MESG의 FULL은 번역하고 업데이트된 DESC만 영문으로 유지하는 실제 플러그인 시험을 자동 검사에서 확인한다. 최종 배포본은 이 정책을 만족해야 하며, 기존 파일 해시 불일치 제외 경로를 완성된 부분 번역으로 취급하지 않는다. [상세 확인](tnvse-font-compatibility.md).

## K-font 원본 후보 확보

2026-10-03 네이버 공식 나눔스퀘어, 제작자 둥근모꼴+Fixedsys, 비교용 몬소리체 미러 및 현행 Monofonto 후보를 `staging/font-source-candidates`에 확보했다. 내부 이름·버전·한글 지원 범위·해시와 비트맵 모양 비교표를 기록했다. 몬소리체가 유력하며 나눔스퀘어 굵기와 Monofonto 혼합/옛 버전은 확정하지 않았다. 일반 나눔스퀘어는 완성형 11,172자, `_ac`는 2,479자이므로 구분한다. 현행 Monofonto는 배포용으로 포함하지 않는다. 게임·MO2·Output에는 설치하지 않았다. [상세 조사](font-source-research.md).

## FreeType 폰트 적용 파일 생성

사용자의 적용 지시에 따라 `Output-Fonts-20261003`에 TTF 3종, FreeType XML, 한글 INI 설정 및 글꼴 출처/사용 조건을 포함했다. 기존 번역 파일을 포함한 적용 파일 50개와 설치 안내가 있다. 나눔스퀘어 Bold / 티몬 몬소리체 / 둥근모꼴로 슬롯 1~8/42를 구성한다. 티몬 제작자 안내에서 게임 임베딩 허용을 확인했으며 OFL로 잘못 분류했던 초기 기록도 정정했다.

패쳐의 설정 병합 경로를 추가해 현행 tNVSE INI의 다른 옵션과 XML의 추가 슬롯/미지 설정을 유지한다. 새 모드가 필요하면 GUI 및 설치 안내가 활성화 방법을 표시한다. 새 패쳐는 `dist/font-build-20261003/VNVKoreanPatcher`에 있으며 기존 EXE는 보존한다. 자동 검사 31개 및 출력 해시/한글 글자 지원/GUI 생성자 확인을 통과했다. 실제 VNV 및 게임 원본은 변경하지 않았다. 현재 선택 프로필에는 tNVSE DLL이 없으며 게임 내 표시 검증은 남아 있다. 플러그인의 native 저장 자동 보정 문제는 이 폰트 변경으로 해결되지 않았고 기존 버전 고정 복사 정책은 그대로다.

## 남은 플러그인 XML 전달 (2026-10-03 추가 완료본 반영)

사용자가 FalloutNV.esm, DeadMoney.esm, OldWorldBlues.esm과 같은 이름의 새 SST를 저장했다. 현재 완료 폴더는 30개이며 미완료 루트는 7개다. 앞선 27개/10개 집계는 이전 수신 시점의 기록이다. 새 3종의 파일/SST 해시는 `reports/remaining_xml_work_20261003/new_completed_intake.json`에 기록했다.

`VNV_Translation_Workspace/08_Korean_Deliverables/Plugins_XML_20261003`에 AguaFria, Better Brotherhood, DLC Enhancements, ExtraGoodies, Goodies의 XML 합본 5개(2,300개 항목)와 추가분 XML 5개를 생성했다. 신규 번역은 고유 문구 275개/적용 항목 306개이고, 재사용 번역의 현재 수치·기능 설명·누락 도움말 등 32개 항목을 수정했다. ALT와 Bad Touch의 조사한 표시 필드는 이미 한글이므로 새 XML을 만들지 않았다.

기본 xtl 추출 외에 공식 xEditLib로 QUST NNAM, 지도 이름, 동작 이름, 저지능 대사, 신체 부위명 및 NOTE TNAM 본문을 읽었다. NOTE TNAM은 타입에 따라 Text/Topic 컨테이너이며 Text 자식만 읽어야 한다는 것을 확인해 어댑터를 보완했다. 반복 식별값·변수·태그·버튼 토큰·CRLF·원본 해시/XML 재읽기를 검증했고 기존 자동 검사 31개도 통과했다. XML은 xTranslator 제작자의 TESVT_XMLFunc.pas v2 형식으로 직렬화했으며 xtl의 미지원 CLI XML export나 미검증 임시 EET writer를 사용하지 않았다.

xTranslator 기본 FalloutNV 정의에는 DIAL TDUM(저지능 전용 선택지)이 없어, `Def_:TDUM=DIAL=0` 한 줄을 추가한 설정 복사본과 적용 안내를 동봉했다. 설치된 xTranslator 설정은 수정하지 않았다. 내부 이름·연기 메모·빈 문자열·이진 코드 등 271개는 원문으로 유지하고 LAER 약어도 유지했다. 조사한 필드의 미해결 표시 문구는 0개이며, 스크립트 문자열/Radio 호환 ESP 전체 완료를 뜻하지 않는다.

실제 xTranslator 가져오기·사용자 Finalize 및 게임 검증은 남아 있다. 이번 XML과 새 완료 3종을 기존 EXE/Output 데이터에 아직 통합하지 않았으며 사용자 반영본/SST를 받은 뒤 카탈로그를 갱신한다. 기존 MO2/게임/플러그인/SST/Output/배포 EXE는 변경하지 않았다.
