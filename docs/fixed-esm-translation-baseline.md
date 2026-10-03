# VNV Fixed ESMs와 번역 기준

2026-10-03 사용자 질문: VNV 본편/DLC ESM이 기존 스크립트 표시 문구를 REFR에 옮긴 형태인지 확인.

## 제작 문서에서 확인한 변경

[VNV Utilities](https://vivanewvegas.moddinglinked.com/utilities.html)는 Fixed ESMs를 Ultimate Edition ESM Fixes Remastered의 출력으로 설명합니다. [제작자 설명](https://www.nexusmods.com/newvegas/mods/92289)은 배치 NPC/크리처 지속성, 내비메시, 잘못된 참조·소유권·플래그, 중복 EditorID 및 INFO 대화 순서용 PNAM 수정 등을 설명합니다. [VNV Decompression Guide](https://vivanewvegas.moddinglinked.com/decompress.html)는 이 도구가 본편 ESM 레코드 압축을 해제한다고 설명합니다.

이 문서들에서 스크립트에 내장된 표시 문자열을 REFR 레코드로 이전했다는 설명은 확인되지 않았습니다. 압축 해제는 스크립트 문구를 번역 가능한 별도 레코드로 바꾸는 처리와 구분합니다.

## REFR 텍스트와 스크립트 표시 이름

[GECK Reference 문서](https://geckwiki.com/index.php/Reference)는 지도 마커의 표시 이름을 참조의 Marker Data에서 설정하는 구조를 설명합니다. 따라서 REFR에서 표시 이름을 발견했다고 해서 스크립트 문자열에서 새로 옮긴 것으로 판정할 수 없습니다.

[SetActorFullName](https://geckwiki.com/index.php?title=SetActorFullName)는 Message 레코드의 제목을 사용해 이름을 변경합니다. [LNSetName](https://geckwiki.com/index.php/LNSetName)은 문자열을 직접 받아 베이스 폼의 이름을 변경합니다. 스크립트가 호출된다는 사실만으로 모든 표시 문구가 스크립트 바이트코드 안에 있는 것도 아닙니다. 실제 문자열 제공 필드/명령 인자를 구분해야 합니다.

## 로컬 조사 범위

`reports/fixed_esm_text_audit`에 설치된 원본 및 Fixed ESMs의 xtl 읽기 전용 조사 결과를 기록합니다. 추출 도구가 지원하는 필드의 통계이며 전체 레코드/스크립트 바이트코드 대조는 아닙니다. 실제 REFR 이동 여부를 개별 사례에서 확정하려면 해당 레코드와 스크립트의 xEdit/GECK 읽기 결과가 필요합니다.

본편의 추출 항목은 설치 원본 70,161개, Fixed 70,181개로 20개 차이입니다. DLC 5개는 추출 항목 수와 레코드 유형별 분포가 각각 동일합니다. 이것은 새 레코드 수가 아니라 지원 필드에서 추출한 텍스트 항목 수입니다. 도구 스키마는 REFR, SCPT, SCTX를 제외하므로 해당 항목이 통계에 없다는 사실을 실제 파일에 없다는 의미로 사용하지 않습니다. 본편 원본을 읽는 도구는 LAND 레코드 압축 해제 오류 1건도 보고했으므로 완전한 레코드 읽기 검증으로 취급하지 않습니다.

## 번역 원천

사용자 지시에 따라 본편/DLC는 제공받은 `Fallout NV KR.esm`을 우선 번역 원천으로 삼고, SST는 보조 대조 자료로 사용합니다. 이 파일은 본편 및 DeadMoney, HonestHearts, OldWorldBlues, LonesomeRoad, GunRunnersArsenal을 masters로 참조합니다. 이는 해당 DLC의 모든 문구가 번역됐다는 증거는 아닙니다.

목표 파일의 구조는 현재 VNV ESM을 유지합니다. 기존 한글 ESM의 레코드 전체로 덮어쓰지 않습니다. 완료본을 보존하고 대응하는 기존 번역 문구를 확인하는 데 사용하며, 불일치 문구를 임의 재번역하거나 자동 확정하지 않습니다.
