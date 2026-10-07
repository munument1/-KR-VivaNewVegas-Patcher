# Viva New Vegas 한국어 패쳐 v1.0.7.1

현재 MO2 프로필을 읽어 번역 파일과 활성화 설정이 반영된 프로필 텍스트를 **Output에만 생성**합니다. MO2와 게임 폴더에 직접 설치하거나 파일을 이동·삭제하지 않습니다.

## 사용 방법

1. 원본 tNVSE 71과 선행 모드를 기존 가이드대로 MO2에 설치합니다.
2. 적용할 MO2 프로필을 선택하고 MO2를 종료합니다.
3. `VNVKoreanPatcher-v1.0.7.1.exe`를 실행하고 `ModOrganizer.ini`가 있는 인스턴스 폴더를 선택합니다.
4. **Output 생성**을 누릅니다.
5. 기존 모드 파일과 선택한 프로필을 백업한 뒤 `Output/INSTALL.txt`에 표시된 실제 경로로 복사해 덮어씁니다. Mods 파일을 먼저 병합하고 프로필 텍스트를 마지막에 복사합니다.
6. MO2를 다시 엽니다. 복사한 프로필 텍스트에 필요한 한국어 모드·플러그인의 활성화 상태가 반영됩니다.

- `Output/mods` 안의 모드 폴더 → INI에 설정된 실제 Mods 폴더
- `Output/profiles/프로필명` 안의 `modlist.txt`, `plugins.txt`, `loadorder.txt` → 해당 실제 프로필 폴더
- 기존 MO2 Overwrite가 제공하던 번역 대상이 있으면 `Output/overwrite`도 생성되며, 해당 파일만 INSTALL.txt의 실제 경로에 복사합니다.

기본 경로에서는 Output의 mods와 profiles 폴더를 MO2 인스턴스 폴더로 복사해 병합할 수 있습니다. 외부 Mods/Profiles 경로는 INSTALL.txt를 따르세요. 출력에 없는 기존 파일을 삭제하지 마세요. 생성 이후 모드나 프로필 설정을 바꿨다면 Output을 다시 생성하세요.

## 번역 파일과 배치

기존 모드의 번역본은 같은 모드 경로로 출력합니다. 게임 Data에만 있는 플러그인의 번역본은 `VNV Korean Translations` 모드로, Courier's Stash 4개 ESM은 기존 Fixed ESMs 모드로 출력합니다. 게임 Data 원본은 유지합니다.

필요한 한국어 폰트·UI·라디오 모드를 켜는 프로필 텍스트를 생성합니다. KR Font와 새 번역 모드는 높은 우선순위에 배치하며 기존 비활성 선택 모드는 유지합니다. 기존 활성 플러그인과 순서는 유지하고 새 UI Strings ESP를 추가합니다. 다른 프로필은 생성하지 않습니다.

수정 tNVSE DLL은 기존 `VNV Korean Fonts - tNVSE/NVSE/plugins/tnvse.dll`에 포함됩니다. 원본 tNVSE의 셰이더·UI 파일은 기존 설치를 사용합니다. GPL-3.0 라이선스와 수정 소스는 KR Font 폴더의 `NVSE/plugins/fonts/licenses`에 포함됩니다.

SST/XEditLib 번역, MCM JSON·Translation INI, 라디오/UI 및 터미널 텍스처를 포함합니다. 변경된 영문 원문은 추측 번역하지 않으며 생성 보고서에 기록합니다. 별도 Python 설치는 필요하지 않습니다.

## 1.0.7 사용자

1.0.7에 추가했던 실제 MO2 자동 설치 기능을 1.0.7.1에서 제거했습니다. 이미 1.0.7로 설치했다면 기존 백업은 보관하세요. 1.0.7.1은 기존 설치를 자동 복구하거나 변경하지 않습니다.

실제 게임의 GMST·단축키 표시와 라이브 MO2 적용 확인은 아직 진행하지 않았습니다.
