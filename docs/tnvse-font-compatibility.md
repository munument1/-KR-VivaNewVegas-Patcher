# tNVSE 최신 폰트 방식 확인

2026-10-03 공식 Nexus 설명·변경 이력, GitHub HEAD, 사용자 제공 ZIP을 대조했다. 공식 페이지의 최신 버전은 71(2026-09-22)이며, 제공된 본체 ZIP도 파일명에 버전 71이 표시돼 있다. GitHub HEAD는 기존 소스 복사본과 같은 `11c69482acc1228750a5b1aa3cae3f938d014eb1`이다. 바이너리의 게임 내 로드 버전과 폰트 표시를 시험한 결과라는 뜻은 아니다.

## 폰트 파일과 설정

버전 63에서 FreeType 기반 SDF/MTSDF 렌더링이 추가됐다. 기존 비트맵 방식을 제거한 것이 아니라 별도 렌더링 방식이 추가된 것이다.

| 방식 | 글꼴 파일 | 설정 |
|---|---|---|
| 기존 비트맵 | `.fnt`와 `.Tex` 쌍 | 기존 게임 폰트 슬롯 INI와 Multibyte 훅, FreeType 비활성 |
| FreeType | TTF/OTF/TTC/OTC face | `tnvse_fonts.xml`의 `<font>`와 `<face>`, FreeType 활성 |

한글 FreeType 구성에는 `bEnableFreeTypeFontRendering=1`뿐 아니라 `bEnableMultibyteFontHook=1`, `uiEncoding=4`가 필요하다. `bUTF8=1`은 UTF-8 입력 감지·변환 후보 설정이며 표시 문구의 실제 인코딩과 함께 검증한다. FreeType 렌더러와 Multibyte 훅은 별도의 스위치다. FreeType만 켠 상태를 한글 설정 완료로 취급하지 않는다.

XML은 font ID별 크기, 단일/이중 바이트별 face와 크기, fallback, 외곽선, 그림자 등을 설정한다. face 경로는 `FalloutNV.exe`를 기준으로 해석하므로 패키지 경로는 `Data/NVSE/plugins/fonts/...`에 대응하도록 구성한다. 표준 슬롯 1~8, JIP 확장 슬롯 10~89를 지원하며 9번은 유효하지 않다. Stewie 메뉴의 42번도 별도 검토한다.

제공된 Default Config ZIP은 FreeType=0, Multibyte=0, uiEncoding=0이며 `tnvse_fonts.xml`의 활성 `<font>` 항목은 0개다. 기본 ZIP을 설치하기만 해서 한글 FreeType 구성이 완성되는 것은 아니다. 제공된 K-font 묶음에서는 벡터 폰트 원본(TTF/OTF/TTC/OTC)을 발견하지 못했다. 기존 `.fnt/.Tex`를 벡터 face 경로에 지정하지 않는다.

이전에 준비한 `staging/tNVSE_Korean_Candidate`는 비트맵 시험 후보다. 최신 FreeType 구성으로 완성된 패키지와 구별한다. 실제 설치, 프로필 INI, 글꼴 파일은 변경하지 않았다. 새 FreeType 한글 face 선정·XML 구성 및 게임에서의 대화/HUD/터미널/MCM/Stewie 메뉴 표시 검증이 남아 있다.

이후 원본 글꼴 후보를 `staging/font-source-candidates`에 별도로 확보하고 FNT/Tex의 글자 모양과 비교했다. 일반 나눔스퀘어와 둥근모꼴 후보는 공식/제작자 배포본이며, 몬소리체는 제3자 미러를 비교용으로 확보했다. 현재 Monofonto는 재배포 및 게임 임베딩 조건 때문에 번들에 포함하지 않는다. 후보 확보는 FreeType 구성 및 게임 검증 완료를 뜻하지 않는다. [원본 글꼴 조사](font-source-research.md).

## FreeType 적용 Output

`Output-Fonts-20261003`은 기존 번역 파일 39개와 폰트 관련 파일 11개, 총 50개 적용 파일 및 별도 설치 안내를 포함한다. 실제 MO2에는 복사하지 않았다. 현재 선택 프로필에서는 tNVSE DLL을 발견하지 못했으므로 사용자가 tNVSE 71과 선행 모드를 먼저 설치해야 한다.

| 슬롯 | face | 크기 |
|---|---|---|
| 1 / 6 / 7 / 42 | NanumSquare Bold | 20px |
| 2 | NanumSquare Bold | 18px |
| 3 | NanumSquare Bold | 22px |
| 4 | TmonMonsori Black | 20px |
| 5 | DungGeunMo | 18px, 영문 셀 9 / 한글 셀 18 |
| 8 | TmonMonsori Black | 30px |

크기는 기존 K-font의 슬롯 배치·명시 크기에서 출발한 시험값이다. `verticalMetrics=freetype`로 face의 행 높이를 사용하고, 본문 색상은 게임 UI 색상을 따른다. 터미널에는 외곽선·그림자를 넣지 않는다. 나머지 슬롯에는 얇은 외곽선과 그림자를 사용한다. `_ac`와 현재 Monofonto는 포함하지 않는다.

`vnvkr_fonts.py`가 활성 tNVSE 설정 제공 경로에 INI와 XML을 병합한다. INI의 FreeType=1, Multibyte=1, uiEncoding=4, bUTF8=1만 설정하고 다른 옵션은 유지한다. XML은 슬롯 1~8/42를 구성하고 다른 슬롯 및 미지 속성/요소를 보존한다. 제공 모드가 없으면 `mods/VNV Korean Fonts - tNVSE`를 생성하며, 사용자가 체크하고 tNVSE보다 아래에 배치해야 한다. DLL은 이 폰트 묶음에 포함하지 않는다.

`bundles/manual-copy-fonts-20261003`과 새 `dist/font-build-20261003/VNVKoreanPatcher`가 폰트 구성을 포함한다. 기존 Output 및 기존 EXE는 보존했다. 자동 검사 31개, 출력 해시·현행 원본 해시·폰트 완성형 지원 범위 및 GUI 생성자 확인을 통과했다. 패키지 빌드는 완료했지만 EXE의 GUI 조작 및 실제 게임 표시는 검증하지 않았다.

## 원문이 추가된 플러그인의 적용 규칙

미대응 처리는 파일 전체가 아니라 표시 문구/필드 단위다. 같은 ESP/ESM 안의 기존 대응 문구는 번역하고, 새 레코드·새 표시 필드·변경된 원문·모호한 대응만 현재 원문으로 유지한다. 같은 레코드에 `FULL` 번역이 있고 `DESC`가 업데이트됐다면 `FULL`은 번역하고 `DESC`만 영문으로 남긴다. 게임 기능, 숫자, 스크립트, 참조를 유지한다.

실제 MercenaryPack 복사본 시험에서 같은 MESG의 FULL은 `용병 팩`, 업데이트된 DESC는 영문으로 남았으며, 새 NOTE도 영문으로 유지됐다. 별도의 장비·무기 이름은 번역됐다. 이 동작을 자동 검사에 명시했다.

기존 배포 EXE의 해시 일치 복사 경로는 이 최종 요구사항을 아직 만족하지 않는다. 항목별 병합 실험 경로는 해당 시험을 통과했지만, 전체 VNV 저장 검증에서 YUP persistent flag/그룹 자동 보정이 발견돼 최종 EXE 적용은 보류돼 있다. 원문 레코드가 추가됐다는 이유로 ESP 전체를 건너뛰는 동작을 최종 정책으로 채택하지 않는다.

## 근거

- [tNVSE 공식 Nexus 설명·변경 이력](https://www.nexusmods.com/newvegas/mods/95088)
- [공식 FreeType 폰트 설정 안내](https://github.com/TIAIMM/tNVSE/blob/11c69482acc1228750a5b1aa3cae3f938d014eb1/docs/english%20config/tnvse_fonts.xml)
- `reports/tnvse_font_format_audit_20261003.json`: 제공 ZIP 해시·기본 설정·최신 소스 확인.
- `tests/test_yesman.py`: 같은 레코드 안의 번역/미대응 필드 공존과 새 레코드 영문 유지 검사.
