# Viva New Vegas 한국어 패쳐

Viva New Vegas(VNV)의 **현재 MO2 프로필에 실제로 설치된 파일**을 기준으로 한국어 Output을 만드는 패쳐입니다. 게임 설치 폴더의 원본 ESM/ESP를 번역 소스로 사용하지 않으며, 원본 VNV 설치도 직접 수정하지 않습니다.

## v1.0.6 변경점

v1.0.6부터 플러그인 번역 데이터의 기준을 **xTranslator SST**로 통일했습니다.

- 전용 SST가 있는 플러그인: 해당 SST를 우선 적용
- 전용 SST가 없는 플러그인: FalloutNV + 공식 DLC SST에서 정확히 일치하는 override 문자열만 fallback
- direct SST와 fallback이 동시에 가능한 경우 direct SST가 우선
- `owner + FormID + record signature + field + path + 현재 영문 원문`이 일치할 때만 번역
- 새 문구나 모드가 변경한 영문 문구는 추측 번역하지 않음

플러그인 처리 백엔드도 바뀌었습니다.

- **Node.js 제거**
- **Koffi 제거**
- **YesMan 어댑터 제거**
- **xdelta 빠른 경로 제거**
- Python 워커가 `ctypes`로 `XEditLib.dll`을 직접 호출
- 전체 플러그인을 CP1252/UTF-8로 반복 검증하던 4단계 경로 제거
- UTF-8 적용 1회 + 저장본 fresh readback 1회로 단순화

저장본 재검증에서는 마스터 순서, 플러그인 헤더, 전체 레코드 인덱스, 실제 수정 레코드의 비문자 구조가 유지되는지 확인합니다. UTF-8 로드에서 `�`가 발생한 문자열은 자동 번역하지 않습니다.

## 번역 범위

패쳐가 번역 대상으로 다루는 것은 다음 세 종류입니다.

1. 현재 MO2 프로필의 **ESP/ESM 플러그인**
2. **MCM JSON**
3. **Translations 계열 텍스트** — `MCM/Translations`, `Interface/Translations`, 모드별 `*_Translations.ini` 등

한국어 출력에 필요한 폰트 설정은 지원 파일로 유지할 수 있지만, 기존 별도 라디오 DLL·번역 텍스처 같은 런타임 오버레이는 v1.0.6 SST 패쳐의 번역 범위에서 제외합니다.

## 플러그인 원본 선택

패쳐는 `ModOrganizer.ini`에서 현재 프로필과 실제 Mods 경로를 읽고 MO2의 winner 파일을 사용합니다.

특히 공식 ESM은 다음 원칙을 따릅니다.

```text
게임 설치 폴더\Data\FalloutNV.esm     ← 번역 소스로 사용하지 않음

MO2\mods\Fixed ESMs\FalloutNV.esm    ← 실제 번역 원본
MO2\mods\Fixed ESMs\DeadMoney.esm
MO2\mods\Fixed ESMs\HonestHearts.esm
...
```

따라서 VNV의 Fixed ESMs 정리/수정 내용이 번역본에서도 유지됩니다. Fixed ESMs 제공 파일을 찾을 수 없으면 게임 Data 파일로 자동 대체하지 않고 오류를 냅니다.

MO2의 `mods`, `profiles`, `overwrite`가 `ModOrganizer.ini`와 다른 드라이브에 있어도 지원합니다.

## SST 적용 방식

예를 들어 `Goodies.esp`에 전용 SST가 있으면 다음 순서로 처리합니다.

```text
Goodies 전용 SST
      ↓ 우선
Goodies.esp 현재 레코드
      ↓
전용 SST가 다루지 않은 vanilla/DLC override
      ↓
FalloutNV + DLC SST fallback
```

`Goodies - Jacobstown Water Fix.esp`처럼 전용 SST가 없는 플러그인은 본편/DLC fallback만 사용합니다.

fallback은 단순 영문 문자열 치환이 아닙니다. 원 소유자, FormID, 레코드 타입, 필드 경로와 현재 영문 원문까지 모두 맞아야 적용됩니다. 모드가 해당 문구를 수정했다면 영어 상태로 보존합니다.

## 사용 방법

GitHub Releases에서 최신 패키지를 받은 뒤 압축을 풉니다.

```text
VNVKoreanPatcher/
├─ VNVKoreanPatcher.exe
├─ VNVKRXEditWorker.exe
├─ TranslationData/
└─ Backend/
   ├─ XEditLib.dll
   ├─ FalloutNV.Hardcoded.dat
   └─ icudtl.dat
```

`VNVKoreanPatcher.exe`를 실행하고 **`ModOrganizer.ini`가 있는 VNV MO2 인스턴스 폴더**를 선택합니다.

예:

```text
C:\Modlists\VNV
```

게임 폴더나 `mods` 폴더 자체를 선택하지 마세요. 패쳐가 INI에서 현재 프로필과 실제 Mods 경로를 읽습니다.

Output 생성 버튼을 누르면 현재 프로필의 플러그인과 번역 대상 텍스트를 읽어 별도 Output을 만듭니다. 원본 MO2 파일은 직접 수정하지 않습니다.

생성된 `Output\mods` 안의 각 모드 폴더를 MO2가 실제로 사용하는 `mods` 폴더에 합치면 됩니다.

## 속도와 검증

기존 방식:

```text
CP1252 snapshot
→ UTF-8 적용
→ UTF-8 검증
→ CP1252 최종 검증
```

v1.0.6:

```text
UTF-8 SST 적용
→ 저장본 fresh readback 검증
```

전체 ESM/ESP 재로딩 횟수를 절반 수준으로 줄였습니다. CP1252 전체 재검증은 제거했지만 검증 자체를 없앤 것은 아닙니다. 저장 후 다시 열어 구조와 실제 번역 결과를 확인하고, UTF-8로 안전하게 읽히지 않는 문자열은 수정하지 않습니다.

## 방화벽/Defender 관련

v1.0.5까지는 Node 런타임과 Koffi를 통해 XEditLib을 호출했습니다. v1.0.6은 Node와 Koffi를 포함하지 않습니다. 패키지의 Python XEdit 워커가 `XEditLib.dll`을 직접 호출하며 네트워크 연결은 필요하지 않습니다.

## 패치 결과 보고서

생성 후 `Output.report.json`과 `Output.report.txt`가 만들어집니다. 플러그인별 SST direct 번역 수, 본편/DLC fallback 번역 수, 현재 원문과 맞지 않아 건너뛴 항목, MO2 provider, 저장본 검증 결과를 확인할 수 있습니다.

## 업데이트 대응

VNV나 개별 모드가 업데이트되어도 패쳐는 현재 MO2 파일을 다시 읽습니다. SST의 레코드/필드/영문 원문이 그대로라면 번역을 적용하고, 원문이 달라졌다면 해당 문자열만 건너뜁니다. 구버전 ESP/ESM 자체를 통째로 덮어쓰지 않습니다.

## 개발

SST 원본 폴더 예:

```text
F:\번역\프로그램\xTranslator\UserDictionaries\FalloutNV
```

SST 카탈로그 생성:

```powershell
py -3 tools\build_sst_catalog.py --base-catalog bundles\records-release-20261005 --sst-dir "F:\번역\프로그램\xTranslator\UserDictionaries\FalloutNV" --output bundles\sst-release-20261006
```

테스트 및 릴리즈 빌드:

```powershell
py -3 -m unittest discover -s tests -q
.\tools\build_release.ps1
```

핵심 파일:

- `vnvkr_sst.py` — xTranslator SSU8/SSU9 SST 파서
- `vnvkr_xelib.py` — XEditLib ctypes 래퍼
- `vnvkr_xedit_worker.py` — 플러그인 SST 적용/검증
- `vnvkr_xedit.py` — MO2 작업 세션 백엔드
- `tools/build_sst_catalog.py` — direct SST + 본편/DLC fallback 카탈로그 생성
- `tools/build_release.ps1` — Windows 패키지 빌드

외부 도구 및 기준 출처는 `docs/sources.md`를 참고하세요.
