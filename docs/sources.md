# 작업 기준과 출처

확인일: 2026-10-06 (한국 시간).

| 출처 | 확인한 내용 | 이 작업에서의 적용 |
|---|---|---|
| VNV 공식 가이드/저장소 | 현재 VNV 설치·모드 구성 기준 | 현재 MO2 프로필과 provider를 번역 원본으로 사용 |
| xTranslator SST | New Vegas 번역 사전(SSU8/SSU9) | 플러그인 번역의 권위 원본. 전용 SST 우선, 본편+DLC SST fallback |
| XEditLib | Bethesda 플러그인 레코드 읽기/수정/저장 | Python `ctypes`에서 직접 호출. Node/Koffi 어댑터 없음 |
| MO2 `ModOrganizer.ini` | 실제 Mods/Profiles/Overwrite 경로 | 경로가 인스턴스 폴더 밖에 있어도 설정값을 따라감 |

## 플러그인 원본 정책

게임 설치 폴더의 `Data`는 Fallout: New Vegas 설치 확인에만 사용합니다. 번역할 ESM/ESP는 현재 MO2 프로필의 winner 파일만 사용합니다. 공식 본편/DLC ESM은 활성화된 `Fixed ESMs` provider에서 읽습니다.

## SST 정책

- 플러그인 전용 SST가 있으면 direct mapping으로 사용합니다.
- 전용 SST가 없거나 direct SST가 다루지 않은 vanilla/DLC override에는 본편+DLC SST fallback을 사용합니다.
- fallback은 owner/FormID/signature/field/path/source가 모두 정확히 일치할 때만 적용합니다.
- xTranslator `oldData` 행, source=dest 행, U+FFFD가 포함된 행, 안정적인 FormID가 없는 source-only 행은 자동 적용하지 않습니다.

## 인코딩/검증 정책

v1.0.6은 전체 플러그인을 CP1252와 UTF-8로 여러 번 재로딩하지 않습니다. UTF-8 XEdit 세션으로 번역을 적용한 뒤 저장본을 새 세션에서 한 번 다시 열어 마스터 순서, 헤더, 전체 레코드 인덱스와 수정 레코드 구조를 검증합니다. UTF-8로 안전하게 읽히지 않는 문자열은 수정하지 않습니다.

## 배포 구성

배포물에는 Node.js, Koffi, YesMan 어댑터, xdelta 런타임을 포함하지 않습니다. 플러그인 처리에 필요한 것은 `VNVKRXEditWorker.exe`, `XEditLib.dll`, `FalloutNV.Hardcoded.dat`, `icudtl.dat`와 라이선스 고지입니다.
