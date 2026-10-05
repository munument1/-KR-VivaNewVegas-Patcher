# Viva New Vegas 한국어 패쳐

Viva New Vegas(VNV)용 한국어 Output 생성기입니다. 사용자가 VNV MO2 폴더를 지정하면 현재 프로필의 파일을 읽어 별도의 `Output`을 만들며, 원본 게임/VNV 설치 파일을 직접 수정하지 않습니다.

## 현재 상태

2026-10-05 기준 v1.0.2 릴리즈 카탈로그에는 활성 플러그인 37개와 비활성 선택 변형 3개, 총 40개 플러그인의 검증된 번역 경로가 들어 있습니다. 40개 모두 UTF-8 fresh readback과 CP1252 legacy readback을 통과했으며, 기준 버전에서는 40/40 모두 xdelta3 빠른 경로를 사용할 수 있습니다.

v1.0.2에서는 대형 `FalloutNV.esm`의 xdelta source window를 파일 크기에 맞게 조정해 기존 약 124.5MiB delta를 약 2.34MiB로 줄였습니다. 기준 VNV 버전은 빠른 verified delta 경로를 사용하고, 업데이트로 원본 해시가 달라진 플러그인은 기존 YesMan-AI/xEditLib 레코드 병합 경로로 자동 전환합니다. xEditLib의 Documents/My Games, INI, plugins.txt, saves, cache, temp 경로도 패쳐의 임시 작업 폴더로 격리했습니다.

라디오 표시 문자열은 `VNVKR UI Strings.esp`에 통합했고, 라디오 자막은 UTF-8 문자열을 그대로 보존하도록 수정한 `MojaveRadioCaptions.dll`을 함께 제공합니다. 로딩 스크린 메시지, UI GMST, Radio INFO 문자열도 같은 UI Strings 플러그인에 포함됩니다.

패쳐는 작업이 끝나면 `Output.report.json`과 `Output.report.txt`를 생성합니다. 보고서에서는 정상 패치, 업데이트 후 전체 적용, 업데이트 후 일부 문구 미적용, 업데이트 후 한글 적용 없음, VNV에서 제거된 플러그인, 비활성 플러그인, 새로 발견된 플러그인의 Fixed ESM 번역 상속 결과를 구분해 확인할 수 있습니다.

현재 릴리즈 카탈로그에 없는 활성 ESP/ESM도 자동 검사합니다. 새 플러그인이 `FalloutNV.esm` 또는 공식 DLC ESM의 레코드를 그대로 오버라이드하고, 원 소유자/FormID/레코드 타입/필드 경로/현재 영문 원문이 모두 검증된 Fixed ESM 번역과 일치할 때만 해당 필드의 한국어를 상속합니다. 모드가 원문을 변경했거나 동일성이 확실하지 않은 레코드는 자동 번역하지 않습니다.

## 설치 전 준비

다음이 먼저 준비되어 있어야 합니다.

- 정상 설치된 **[Viva New Vegas](https://vivanewvegas.moddinglinked.com/intro.html)**
- **[Mod Organizer 2(MO2)](https://github.com/ModOrganizer2/modorganizer/releases)** 기반 VNV 설치
- **[tNVSE 71 이상](https://www.nexusmods.com/newvegas/mods/95088)**
- VNV에서 사용하는 **[UIO(User Interface Organizer)](https://www.nexusmods.com/newvegas/mods/57174)** 구성
- 게임과 MO2를 완전히 종료한 상태

패쳐는 tNVSE DLL 자체를 배포하지 않습니다. 기존 VNV 설치에 tNVSE가 정상 동작하는 상태에서 사용하는 것을 전제로 합니다.

가능하면 설치 전 MO2 폴더를 백업하거나, 최소한 현재 프로필과 중요한 사용자 설정을 백업하는 것을 권장합니다.

## 설치 방법

### 1. 릴리즈 파일 받기

GitHub Releases에서 최신 `VNVKoreanPatcher-YYYYMMDD.zip`을 받은 뒤 원하는 폴더에 압축을 풉니다.

압축 안에는 대략 다음과 같은 구조가 있습니다.

```text
VNVKoreanPatcher/
├─ VNVKoreanPatcher.exe
├─ TranslationData/
└─ Backend/
```

`TranslationData`와 `Backend` 폴더는 EXE 옆에 그대로 있어야 합니다. 파일만 따로 빼서 실행하지 마세요.

### 2. 패쳐 실행

`VNVKoreanPatcher.exe`를 실행합니다.

패쳐에서 **VNV의 MO2 루트 폴더**를 지정합니다.

예시:

```text
C:\Modlists\VNV
```

올바른 폴더라면 그 안에 보통 다음 항목이 보입니다.

```text
ModOrganizer.exe
ModOrganizer.ini
mods/
profiles/
overwrite/
```

게임 설치 폴더인 아래 경로를 선택하는 것이 아닙니다.

```text
C:\Games\Steam\steamapps\common\Fallout New Vegas
```

즉 **게임 폴더가 아니라 VNV의 MO2 폴더를 선택**해야 합니다.

### 3. Output 생성

패쳐에서 **Output 생성**을 누릅니다.

패쳐는 현재 VNV 프로필과 설치된 파일을 읽어서 별도의 `Output` 폴더를 만듭니다. 이 단계에서는 VNV 원본을 직접 수정하지 않습니다.

정상적인 VNV 버전에서는 대부분의 검증된 플러그인이 xdelta3 빠른 경로를 사용합니다. `FalloutNV.esm`은 v1.0.1부터 패키지 용량 절감을 위해 항상 YesMan-AI/xEditLib 레코드 병합 경로를 사용합니다. 다른 플러그인도 VNV 업데이트 등으로 원본 해시가 달라지면 같은 병합 경로로 전환합니다.

### 4. Output을 VNV에 복사

생성이 끝나면 Output 안의 **`mods` 폴더 내용**을 VNV MO2 루트의 `mods` 폴더에 복사합니다.

예를 들어:

```text
생성된 Output
└─ mods
   ├─ Fixed ESMs
   ├─ YUP - Base Game and All DLC
   ├─ Goodies
   ├─ tNVSE Default Config
   ├─ VNV Korean UI Strings
   ├─ VNV Korean Radio Captions
   └─ ...

↓

C:\Modlists\VNV\mods\
```

중요한 점은 **`Output\mods` 폴더 자체를 `mods` 안에 한 번 더 넣는 것이 아니라**, 그 안에 있는 각 모드 폴더를 기존 `C:\Modlists\VNV\mods\`에 합치는 것입니다.

Windows에서 기존 파일을 바꿀지 물어보면 **덮어쓰기/교체**를 선택합니다. 번역 플러그인과 MCM/Translations, tNVSE 설정이 기존 VNV 모드 폴더에 들어가야 하기 때문입니다.

패쳐가 만드는 Output은 현재 VNV의 모드 폴더 구조를 그대로 따라갑니다. 따라서 `FalloutNV.esm`, YUP, Goodies 등은 별도의 “한글패치 모드” 하나에 몰아넣는 방식이 아니라 **각 원래 VNV 모드 폴더의 번역본으로 교체**됩니다.

### 5. MO2에서 새 모드 활성화

MO2를 실행하고 왼쪽 모드 목록에서 다음 두 모드가 생성됐는지 확인합니다.

- **VNV Korean UI Strings**
- **VNV Korean Radio Captions**

둘 다 체크해서 활성화합니다.

`VNV Korean Radio Captions`는 NVSE DLL/UI 파일 모드라 별도 ESP가 없습니다.

### 6. VNVKR UI Strings.esp 활성화

MO2 오른쪽 **Plugins** 탭에서 다음 플러그인을 체크합니다.

```text
VNVKR UI Strings.esp
```

이 ESP에는 다음 종류의 한국어 문자열이 포함됩니다.

- UI GMST
- 로딩 스크린 메시지
- 라디오 방송용 INFO 문자열
- 라디오 자막에서 사용하는 표시 문자열

YUP, Goodies, ExtraGoodies 등 필요한 마스터 뒤에 로드되어야 합니다. MO2가 마스터 의존성을 지키는 한 임의로 앞쪽으로 올리지 않는 것을 권장합니다.

### 7. tNVSE 한국어 설정 확인

Output은 기존 **tNVSE Default Config** 모드에 한국어용 설정을 반영합니다.

주요 값은 다음과 같습니다.

```ini
bEnableFreeTypeNativeAtlas = 0
bEnableFreeTypeFontCommandBuffer = 0
uiFreeTypeFontDistanceFieldMode = 1
uiReorderDoorPrompt = 2
sOptionalStructuralParticle = ""
bMultibyteInput = 1
bEnableDictionaryTranslation = 0
```

또한 한국어 표시를 위해 다음 설정을 사용합니다.

```ini
uiEncoding = 4
bUTF8 = 1
```

런타임 Dictionary 번역은 중복 번역을 막기 위해 비활성화합니다.

폰트 구성에는 다음 계열이 포함됩니다.

- Pretendard Bold
- NanumSquare ExtraBold
- TmonMonsori
- NeoDunggeunmo Pro
- font slot 1~8
- Stewie 계열용 font slot 42

기존 `tNVSE Default Config` 모드가 활성화되어 있었다면 그대로 활성화 상태를 유지하면 됩니다.

### 8. 게임 실행 후 확인

게임은 평소처럼 **MO2에서 실행**합니다.

처음 테스트할 때는 다음 항목을 확인하는 것이 좋습니다.

- 메인 UI와 Pip-Boy가 한글로 표시되는지
- 일반 대사와 자막이 한글인지
- 자막 앞 NPC/생물 이름이 한글인지
- 문 상호작용 문구가 한글인지
- 퀘스트 진행/완료 메시지가 한글인지
- 로딩 스크린 메시지가 한글인지
- 라디오 진행자 대사가 한글인지
- 라디오 자막이 깨지지 않고 정상 한글로 표시되는지
- MCM 메뉴와 각 모드의 Translations 파일이 한글로 적용되는지

라디오 자막 DLL을 교체한 뒤에는 **게임을 완전히 종료하고 다시 실행**해야 합니다. 실행 중 DLL만 바꿔서는 새 버전이 로드되지 않습니다.

## Output에 포함되는 항목

현재 릴리즈 Output에는 다음이 포함됩니다.

- VNV 관련 ESP/ESM 번역 40개
- MCM/INI/JSON 번역
- `MCM/Translations` 번역
- 한국어 `tnvse.ini`
- `tnvse_fonts.xml`
- 한국어용 폰트
- 번역 텍스처
- `VNVKR UI Strings.esp`
- `MojaveRadioCaptions.dll`
- `MojaveRadioCaptions.ini`
- Radio Captions HUD XML
- UIO 등록 파일

tNVSE 본체 DLL은 포함하지 않습니다.

## 패치 결과 보고서

Output 생성 후 패쳐의 **패치 결과 보기** 버튼을 누르면 상세 텍스트 보고서를 열 수 있습니다.

보고서는 플러그인을 다음처럼 분류합니다.

- **정상 패치**: 검증된 원본과 일치해 xdelta 또는 기존 번역 경로가 정상 적용됨
- **이미 한글 적용됨**: 현재 플러그인이 검증된 한국어 결과 해시와 일치해 느린 재병합 없이 그대로 재사용함
- **업데이트 감지 - 번역 전체 적용**: 원본 해시는 달라졌지만 현재 레코드에 기존 번역이 모두 대응됨
- **업데이트 감지 - 일부 문구 미적용**: 대응되는 기존 문구는 번역했고, 새 문구/변경 문구는 영어로 보존함
- **업데이트 감지 - 한글 적용 없음**: 기존 번역 기준과 대응되는 문구가 없어 해당 플러그인에 번역을 적용하지 못함
- **이번 설치에서 제거됨**: 카탈로그에는 있으나 현재 VNV에 파일이 없어 Output을 생성하지 않음
- **신규 플러그인 - Fixed ESM 동일 레코드 번역 상속**: 새 플러그인의 바닐라/DLC 오버라이드 중 안전하게 일치한 필드만 자동 번역
- **신규 플러그인 - 상속 가능한 동일 레코드 없음**: 새 플러그인은 발견했지만 안전하게 상속할 Fixed ESM 번역이 없음

신규 플러그인 자동 상속은 플러그인 자체의 새 대사나 새 설명을 추측 번역하지 않습니다. 기존 공식 ESM의 검증된 번역을 정확히 재사용할 수 있는 레코드만 처리합니다.

## 업데이트하거나 VNV를 다시 설치한 경우

VNV가 업데이트되거나 일부 모드를 다시 설치하면 한국어로 교체했던 파일이 원본으로 돌아갈 수 있습니다.

그 경우:

1. 최신 패쳐 릴리즈를 받습니다.
2. 현재 VNV MO2 폴더를 다시 지정합니다.
3. Output을 새로 생성합니다.
4. 새 Output의 `mods` 내용을 다시 VNV의 `mods`에 합칩니다.
5. `VNV Korean UI Strings`, `VNV Korean Radio Captions`, `VNVKR UI Strings.esp`가 활성화되어 있는지 확인합니다.

기존 Output을 계속 재사용하기보다 **현재 VNV 상태를 기준으로 다시 생성**하는 것을 권장합니다.

## 문제 해결

### 대부분 한글인데 일부 플러그인 내용만 영어로 나오는 경우

Output의 번역 플러그인이 실제 VNV `mods` 폴더에 덮어써졌는지 확인하세요. 특히 다음과 같은 파일은 기존 VNV 모드 폴더 안의 번역본으로 교체되어야 합니다.

```text
Fixed ESMs\FalloutNV.esm
YUP - Base Game and All DLC\YUP - Base Game + All DLC.esm
Goodies\Goodies.esp
Goodies\ExtraGoodies.esp
```

### UI는 한글인데 로딩 화면 또는 라디오가 영어인 경우

다음을 확인하세요.

- `VNV Korean UI Strings` 모드 활성화
- `VNVKR UI Strings.esp` 활성화
- `VNV Korean Radio Captions` 모드 활성화

### 라디오 자막의 한글이 깨지는 경우

최신 릴리즈의 `MojaveRadioCaptions.dll`을 사용하고 있는지 확인하세요. 현재 버전은 게임 문자열이 이미 유효한 UTF-8이면 그대로 사용하고, 레거시 문자열일 때만 CP1252 변환을 사용합니다.

DLL 교체 뒤에는 반드시 게임을 완전히 종료한 뒤 다시 실행하세요.

### 폰트가 깨지거나 한글 입력/표시가 이상한 경우

`tNVSE Default Config\NVSE\plugins\tnvse.ini`가 Output의 버전으로 교체되었는지 확인하고, tNVSE가 71 이상인지 확인하세요.

## 플러그인 처리 방식

원본 SHA-256이 릴리즈 시 검증한 버전과 같으면 xdelta3 빠른 경로를 사용합니다. v1.0.2에서는 `FalloutNV.esm`도 최적화된 약 2.34MiB verified delta를 사용합니다. xdelta로 복원된 ESP/ESM은 크기와 SHA-256을 다시 검사하므로 검증된 결과와 다른 바이트가 만들어지면 실패합니다.

VNV 업데이트 등으로 원본 해시가 달라진 플러그인은 YesMan-AI/xEditLib 레코드 병합 경로로 전환합니다. FormID/소유자/필드/현재 원문이 대응되는 번역만 적용하고 새 문구나 변경된 문구는 영어로 유지합니다. 개발용 정밀 검증에서는 전체 레코드와 헤더를 새 세션에서 다시 읽으며, xEdit 저장 시 TES4 ONAM의 순서만 재정렬되는 경우에는 구성원 집합이 동일한지 비교합니다.

CP1252 처리는 최종 게임 인코딩을 CP1252로 만들기 위한 것이 아닙니다. 원본 플러그인의 legacy 문자열이 UTF-8 로드 과정에서 손상되지 않았는지 검증·복구하기 위한 백엔드 절차입니다. 최종 한글 출력은 tNVSE의 UTF-8 감지 + Korean(UHC/949) UI 훅을 전제로 합니다.

## 개발 및 검증

```powershell
py -3 -m unittest discover -s tests -q
py -3 vnvkr_output.py output --mo2-root "C:\Modlists\VNV" --profile "Viva New Vegas Extended" --catalog bundles/records-release-20261005 --output Output
.\tools\build_release.ps1
```

현재 저장소에는 패쳐 본체, 릴리즈 빌드에 필요한 최소 도구, 회귀 테스트만 유지합니다. 일회성 번역 감사·프로브·카탈로그 제작 스크립트와 작업 중간 산출물은 Git 소스 저장소에서 제외했습니다.

핵심 빌드 도구는 `tools/build_release.ps1`, `tools/prepare_release_package.py`, `tools/setup_xdelta.ps1`, `tools/setup_yesman_utf8_node.py`, `tools/yesman_text.cjs`입니다. 외부 도구와 자료 출처는 `docs/sources.md`를 참고하세요.
