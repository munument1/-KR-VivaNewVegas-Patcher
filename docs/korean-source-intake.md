# 제공받은 본편 번역 원천

2026-10-03에 사용자가 제공한 로컬 파일 묶음을 이 프로젝트의 번역 원천으로 등록했습니다. 원본은 읽기만 했으며 게임/MO2에는 설치하지 않았습니다.

원천: `C:/Users/seung/OneDrive/Desktop/drive-download-20261003T025622Z-1-001/`

## 본편/DLC 번역 원천 우선순위

2026-10-03 사용자 지시: 본편과 DLC의 추가 번역 대조에는 `본편/Fallout NV KR.esm`을 우선 원천으로 사용합니다. xTranslator `FalloutNV` UserDictionaries의 SST는 보조 대조 자료입니다. 완료 폴더의 사용자 번역본은 보존합니다.

목표 파일은 VNV에 설치된 현행 본편/DLC ESM입니다. 기존 한글 ESM에서 대응하는 번역 문자열을 확인하되, 그 ESM 전체나 오래된 레코드를 현행 파일 위에 덮어쓰지 않습니다. 대상 레코드의 기능/스크립트/식별자를 유지하고, 원문·문맥·반복 필드가 다른 항목은 별도 검토 대상으로 남깁니다. 후속 사용자 요청으로 남은 문구의 새 번역과 XML 전달도 승인되었으며, 기존 완료본은 보존합니다.

| 구성 | 용도 | 확인 상태 |
|---|---|---|
| 본편/Fallout NV KR.esm | 기존 번역 문자열 회수 원천 | xtl 읽기 전용 감사 완료; 손실 없는 회수와 VNV 대응 검증은 남음 |
| 본편/NVKOR Radio + UI.esp | 라디오·UI 보충 번역 원천 | xtl 읽기 전용 감사 완료; 손실 없는 회수와 VNV 대응 검증은 남음 |
| 본편/Bit-O-Matic.7z | SPECIAL 검사 화면 텍스처 | 7-Zip 목록 확인: DDS 7개, 실행파일 없음 |
| K-font/K-font/Textures/fonts | 비트맵 한글 글꼴 | .fnt/.Tex 쌍 7종 확인 |
| XP font fix | UIO를 통한 XP/방사선 HUD 글꼴 설정 | XML과 UIO 등록 파일 확인, 현재 VNV UI와 호환성은 미검증 |

21개 파일, 합계 343,399,309바이트입니다. 파일별 SHA-256과 크기는 `reports/supplied_sources_20261003.json`에 기록했습니다. `tools/audit_sources.py`로 새 보고서 경로를 지정해 다시 확인할 수 있습니다. 이 수치는 파일 재고이며 번역률이 아닙니다.

## 런타임 기준

2026-10-03 최신 공식 자료 재확인: 최신 버전은 71이며 사용자 제공 ZIP과 같은 버전 표기다. 버전 63부터 FreeType SDF/MTSDF가 추가됐고 TTF/OTF/TTC/OTC와 `tnvse_fonts.xml`을 사용한다. 기존 `.fnt/.Tex`도 FreeType을 비활성화하면 사용할 수 있다. 아래 미설치 후보는 비트맵 기준이며 새 FreeType 한글 구성 완료본이 아니다. [최신 폰트 감사 및 적용 규칙](tnvse-font-compatibility.md)에 상세 근거를 기록했다.

[tNVSE 공식 페이지](https://www.nexusmods.com/newvegas/mods/95088)와 [소스 저장소](https://github.com/TIAIMM/tNVSE)를 확인했습니다. 조사에 사용한 소스 스냅샷은 `11c69482acc1228750a5b1aa3cae3f938d014eb1`입니다. 현행 소스의 `docs/default config/tnvse.ini` 및 `tnvse/Src/load_config.cpp`에서 다음 설정을 확인했습니다.

- `[Multibyte] bEnableMultibyteFontHook=1`: 다중 바이트 글꼴 훅.
- `uiEncoding=4`: UHC/CP949 한글.
- `bUTF8=1`: UTF-8 원문 감지 후 선택된 UI 인코딩으로 변환. 실제 원천 인코딩 확인 후 사용할지 결정합니다.
- `[FreeTypeFont] bEnableFreeTypeFontRendering=0`: 제공받은 비트맵 글꼴을 시험할 때의 후보 경로. 벡터 글꼴 시험은 별도 검증합니다.

런타임 원천은 사용자가 제공한 `C:/Users/seung/OneDrive/Desktop/tnvse/`의 tNVSE 본체 ZIP(파일명에 버전 71)과 Default Config ZIP(파일명에 버전 6)입니다. 실제 ZIP에서 tnvse.dll, 기본 설정 3개, 셰이더와 메뉴 리소스를 확인했습니다. DLL의 Windows FileVersion 리소스는 비어 있으므로 파일명 버전과 해시를 기록하며 로드된 플러그인 버전은 아직 확인하지 않았습니다. VNV 요구 모드 및 실제 실행 버전은 설치 완료 후 확인합니다.

`tools/prepare_runtime.py`로 작업 폴더 `staging/tNVSE_Korean_Candidate`에 **미설치 후보**를 만들었습니다. ZIP 해시·파일별 해시·설정 변경은 `reports/tnvse_runtime_20261003.json`에 기록했습니다. Multibyte 훅=1, uiEncoding=4, bUTF8=1을 적용하고 FreeType 및 런타임 사전 기능은 기본값 0을 유지합니다. ZIP의 디버그 PDB와 save_display_names.dat는 후보에 넣지 않습니다.

이 후보에는 비트맵 글꼴이나 번역 ESM/ESP를 복사하지 않았습니다. 제공받은 K-font를 별도 모드로 사용하는 구성이며, 슬롯 1~8의 검토용 INI 조각은 `reports/tnvse_runtime_20261003.FalloutCustom.fragment.ini`입니다. 실제 프로필 INI와 모드 순서는 수정하지 않았습니다.

K-font의 Read ME는 슬롯 1~9 설정을 제안하지만 9번의 `Pretendard-SemiBold.fnt`는 묶음에 없습니다. 현행 tNVSE의 `tnvse_fonts.xml` 안내에는 표준 1~8 및 JIP 확장 10~89가 명시되며 9번을 invalid로 설명합니다. 따라서 이 Read ME를 프로필 INI에 그대로 적용하지 않습니다. 슬롯 1~8과 VNV UI/Stewie 확장 글꼴을 분리해서 확인합니다.

## 패쳐 연결 방식

본편 ESM/ESP는 번역 원천입니다. 이 파일들을 VNV 뒤에 그대로 로드하거나 이름을 바꿔 원본을 대체하는 결과는 아직 만들지 않았습니다. VNV의 YUP·후속 패치가 변경한 레코드를 유지하면서 원천의 한글 문자열을 문맥별로 대응시킨 뒤 검수본과 차분을 생성합니다.

바이트 인코딩을 먼저 확인합니다. CP1252로 잘못 디코딩된 번역이나 U+FFFD가 들어간 추출 결과는 검수된 한글 번역으로 사용하지 않습니다. FormID·레코드·필드·반복 순서·퀘스트 단계·대화 문맥·원문 바이트의 보존 가능 여부도 함께 확인해야 합니다.

## 문자열 감사 결과

bgs-translator 0.9.0rc1의 읽기 전용 추출 및 추출 SQLite 감사를 수행했습니다. 결과와 한계는 `reports/source_audit/FINDINGS.md` 및 `sqlite_encoding_audit.json`에 있습니다.

| 원천 | 추출 단위 | 한글 포함 후보 | 디코딩 역변환이 중복되는 단위 |
|---|---:|---:|---:|
| Fallout NV KR.esm | 88,832 | 81,064 | 2,409 |
| NVKOR Radio + UI.esp | 1,529 | 1,001 | 12 |

한글 후보 수에는 엄격한 CP1252→UTF-8 재해석으로 확인한 문구가 포함됩니다. 이는 검수된 번역 수·전체 게임 번역률 또는 최종 적용 수가 아닙니다. SQLite의 `untranslated` 상태는 새 프로젝트의 번역 대상 열이 비어 있다는 뜻이며 이미 한글인 원천을 미번역으로 판단하지 않습니다.

FormID/EditorID와 필드 반복 인덱스는 추출되지만 전체 원문 페이로드·NUL 종단·디코딩 분기와 부모 대화 문맥은 저장되지 않습니다. 특히 2,409/12개 단위는 저장된 문자열만으로 원래 텍스트 바이트를 유일하게 복원할 수 없습니다. 이 감사 DB를 그대로 확정 번역 메모리로 내보내지 않았습니다. 게임 원본과 지원 도구에서 원문 바이트 및 문맥을 다시 확인한 뒤 대응표를 확정합니다. FormID의 상위 로드 인덱스는 플러그인별 master 이름으로 정규화해야 합니다.

설치 완료 후 필요한 작업은 영문 원본 및 Base/Extended 프로필 목록, 번역 대응표, 글꼴/텍스처의 MO2 오버레이 준비, 구조/스크립트 보존 검증과 실제 게임 표시 시험입니다. 아직 번역 커버리지, 패치 충돌 해결 또는 게임 구동 성공을 주장하지 않습니다.
