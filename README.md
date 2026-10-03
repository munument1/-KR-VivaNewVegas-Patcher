# Viva New Vegas 한국어 패쳐

Viva New Vegas(VNV)용 한국어 Output 생성기입니다. 사용자가 VNV MO2 폴더를 지정하면 현재 프로필의 파일을 읽어 별도의 `Output`을 만들며, 원본 게임/VNV 설치 파일을 직접 수정하지 않습니다.

## 현재 상태

2026-10-03 기준 릴리즈 카탈로그에는 활성 플러그인 37개와 비활성 선택 변형 3개, 총 40개 플러그인의 검증된 번역 경로가 들어 있습니다. 40개 모두 UTF-8 fresh readback과 CP1252 legacy readback을 통과한 결과를 기반으로 xdelta3 빠른 패치를 제공합니다.

현재 테스트 VNV 설치에서 일반 사용자 경로는 69개 출력 파일을 약 12.5초에 생성했습니다. 패키징된 `VNVKoreanPatcher.exe`의 self-test도 실제 TranslationData/xdelta를 사용해 Output을 만들고 ExitCode 0으로 통과했습니다. 자동 테스트는 35/35 통과 상태입니다.

게임 내 실제 플레이 검증은 별도 단계입니다. KR-RADIO는 현행 VNV와 겹치는 compiled script block 19개가 있어 기존 Radio ESP를 그대로 포함하지 않으며, 별도 호환 ESP 작업 대상으로 남겨 두었습니다.

## 사용 방법

1. tNVSE 71 이상과 VNV를 준비합니다.
2. `VNVKoreanPatcher.exe`를 실행합니다.
3. `ModOrganizer.ini`가 있는 VNV MO2 폴더를 선택합니다.
4. **Output 생성**을 누릅니다.
5. 생성된 `Output\mods`의 내용을 VNV MO2 폴더의 `mods`에 복사합니다.

패쳐는 tNVSE DLL을 배포하지 않습니다. 한국어용 `tnvse.ini`, `tnvse_fonts.xml`, Pretendard Bold / NanumSquare ExtraBold / TmonMonsori / NeoDunggeunmo Pro 폰트와 필요한 라이선스 고지, MCM/INI 번역 및 번역 텍스처를 Output에 포함합니다. 한국어 설정은 `uiEncoding=4`, `bUTF8=1`이며 런타임 Dictionary 번역은 중복 번역을 피하기 위해 비활성화합니다. Stewie 계열용 font slot 42도 포함합니다.

## 플러그인 처리 방식

원본 SHA-256이 릴리즈 시 검증한 버전과 같으면 xdelta3 빠른 경로를 사용합니다. 복원된 ESP/ESM의 크기와 SHA-256을 다시 검사하므로 다른 바이트가 만들어지면 실패합니다.

VNV 업데이트 등으로 원본 해시가 달라진 플러그인은 YesMan-AI/xEditLib 레코드 병합 경로로 전환합니다. FormID/소유자/필드/현재 원문이 대응되는 번역만 적용하고 새 문구나 변경된 문구는 영어로 유지합니다. 개발용 정밀 검증에서는 전체 레코드와 헤더를 새 세션에서 다시 읽으며, xEdit 저장 시 TES4 ONAM의 순서만 재정렬되는 경우에는 구성원 집합이 동일한지 비교합니다.

CP1252 처리는 최종 게임 인코딩을 CP1252로 만들기 위한 것이 아닙니다. 원본 플러그인의 legacy 문자열이 UTF-8 로드 과정에서 손상되지 않았는지 검증·복구하기 위한 백엔드 절차입니다. 최종 한글 출력은 tNVSE의 UTF-8 감지 + Korean(UHC/949) UI 훅을 전제로 합니다.

## 개발 및 검증

```powershell
py -3 -m unittest discover -s tests -q
py -3 vnvkr_output.py output --mo2-root "C:\Modlists\VNV" --profile "Viva New Vegas Extended" --catalog bundles/records-release-20261003 --output Output
```

릴리즈 제작용 주요 도구는 `tools/build_font_bundle.py`, `tools/add_verified_deltas.py`, `tools/verify_optional_variants.py`, `tools/add_optional_verified_deltas.py`, `tools/prepare_release_package.py`입니다. 생성 데이터와 대형 바이너리는 `.gitignore`에 의해 Git 소스 저장소에서 제외됩니다.

자세한 진행 기록은 `docs/progress.md`, KR-RADIO 병합 기준은 `docs/radio-compatibility.md`, 외부 도구/자료 출처는 `docs/sources.md`를 참고하세요.
