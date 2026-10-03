# 작업 기준과 출처

확인일: 2026-10-03 (한국 시간).

| 출처 | 확인한 내용 | 이 작업에서의 적용 |
|---|---|---|
| [VNV Introduction](https://vivanewvegas.moddinglinked.com/intro.html) | Base와 Extended가 분리되며 영문 게임 기준 | 설치된 프로필별 목록 및 번들을 분리 |
| [VNV Wabbajack](https://vivanewvegas.moddinglinked.com/wabbajack.html) | Extended 자동 설치, 후처리 및 업데이트 절차, 사용자 모드에 [NoDelete] 사용 | 설치·후처리가 끝난 해시 사용, 한글 모드에 [NoDelete] 권장 |
| [VNV User Interface](https://vivanewvegas.moddinglinked.com/hud.html) | UI 모드 설치 안내 | 실제 설치된 UI/XML/MCM을 별도 회수·검수 |
| [VNV Bug Fixes](https://vivanewvegas.moddinglinked.com/bugfix.html) | YUP 등의 버그 수정 모드 | 구버전 번역 플러그인으로 기능 패치를 덮지 않고 현행 파일에 번역 적용 |
| [공식 가이드 저장소](https://github.com/ModdingLinked/Viva-New-Vegas) | 현재 가이드 원천 | 설치된 팩 버전은 로컬 파일 해시로 별도 고정 |
| [xdelta3](https://github.com/jmacd/xdelta/releases/tag/v3.2.0) | 공식 Windows 바이너리, VCDIFF 차분 | 원본/번역본을 구조 해석 없이 차분 생성·재구성 |

공식 웹 가이드와 현재 Wabbajack 설치 버전이 항상 같다고 가정하지 않습니다. 본편/DLC·Base·Extended 경계는 설치 완료 후 프로필을 비교해 결정합니다. 한국어 번역 원천은 사용자가 제공한 파일 묶음으로 등록했습니다. 상세 내용은 korean-source-intake.md를 참고하세요. 현재 VNV 설치 경로·팩 버전과 실제 한글 런타임 구동은 확정하지 않았습니다.

이 프로젝트의 차분 번들은 파일 검수 문서를 보관하지만 그 문서의 주장이나 플러그인 구조를 자동 검증하지 않습니다. 실제 번역 작업 및 xEdit 검증 근거가 있어야 게임용 번들로 배포할 수 있습니다.

xdelta 도구 출처/무결성 정보는 tools/xdelta_source.json에 기록합니다. 다운로드 바이너리는 .tools에만 두고 저장소에 포함하지 않습니다. 향후 실행파일 배포에 동봉할 경우 Apache 2.0 라이선스와 필요한 고지를 함께 제공합니다.
