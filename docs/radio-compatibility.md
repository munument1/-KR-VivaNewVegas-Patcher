# KR-RADIO와 VNV 호환 번역 ESP

2026-10-03 사용자 제공 `NVKOR Radio + UI.esp`를 현행 VNV Extended의 43개 플러그인과 공식 YesMan-AI/XEditLib API로 대조했다. Fixed ESMs에 KR-RADIO 내용이 모두 들어 있다는 전제는 틀렸다.

- KR-RADIO 총 2,915개: 현행 레코드 override 678개, 자체 소유 새 레코드 2,237개.
- 새 레코드: GMST 1,452개, MESG 417개, INFO 282개, DIAL 85개, MICN 1개. 새 MESG 416개에는 한국어 방송 메시지가 있다.
- 기존 override 574개에는 자체 새 레코드로 향하는 링크 1,166개가 있다. 새 대화 연결과 내장 스크립트는 방송 메시지를 표시하는 기능이므로 번역 문구만 기존 ESM에 옮기는 것으로 대체할 수 없다.

본편 번역 원천 `Fallout NV KR.esm`은 90,402개 모두 현행 레코드에 대응하며 자체 새 FormID가 없다. 본편 번역은 현행 VNV ESM/ESP의 표시 필드에 병합한다. KR-RADIO의 추가 UI 설정과 방송 기능은 별도 호환 ESP로 보존한다.

## 기존 Radio ESP를 그대로 쓰면 생기는 충돌

현행 winner와 Steam 폴더의 master 복사본을 비교한 결과, Radio override 678개 중 script/link 차이는 603개다. compiled script block 517개 중 19개는 Radio와 VNV가 모두 수정했다. 제공 모드는 Goodies 13개, ExtraGoodies 3개, YUP 3개다. Steam 비교본은 현재 설치된 파일의 복사본이며 순정 원본 인증을 받은 파일이라는 뜻은 아니다.

예를 들어 `FalloutNV.esm:0EA4F2`의 Goodies 스크립트는 블랙 마운틴 SegmentVar 증가와 VMS57 퀘스트 시작·목표 표시를 수행한다. Radio는 ShowMessage를 넣으면서 SegmentVar 증가를 주석 처리한다. Radio 전체를 뒤에 놓으면 이 현행 코드를 덮어쓸 수 있다. 스크립트 의도와 대화 전환 흐름을 함께 검토해 병합해야 한다.

현행 GMST와 같은 EDID인 새 Radio 설정 113개 중 한글 110개는 현행 설정의 DATA 번역 병합 후보다. `sBloodParticleDefault`의 NIF 경로는 번역문이 아니며 VNV 경로를 유지한다. 나머지 기존 EDID 없는 GMST 1,339개는 추가 설정으로 보존 필요성을 검토한다.

## 제작 기준

1. 기존 override는 현행 winner를 바탕으로 Radio의 필요한 기능 변화와 번역을 병합한다.
2. 새 MSG/INFO/DIAL/MICN과 추가 GMST를 별도 ESP에 보존한다. FormID 참조와 INFO Topic 부모 연결을 함께 유지한다.
3. 양쪽이 수정한 script block 19개는 실행 의도를 합친 뒤 FNV용 도구로 실제 컴파일한다. SCTX만 바꾸거나 SCDA와 참조표를 따로 복사하지 않는다.
4. 출력 복사본을 새 API 세션에서 다시 읽어 참조·스크립트·VNV 필드를 검증한다. MO2에서 방송 자막, 대화 전환, 퀘스트 진행, 메뉴를 실제 시험한다.

현재 단계는 조사와 병합 계획 작성이다. 호환 ESP의 저장·스크립트 컴파일·게임 실행 검증은 아직 수행하지 않았다. 실제 설치와 원본 Radio ESP는 수정하지 않았다.

상세 근거: `reports/yesman_ai_audit/radio_override_merge_plan.md`, `radio_override_summary.json`, `radio_override_script_block_plans.jsonl`, `RADIO_AND_MISSING_FIELDS_FINDINGS.md`.
