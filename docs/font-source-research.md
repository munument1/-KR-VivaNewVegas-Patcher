# K-font 원본 글꼴 후보 조사

2026-10-03 사용자 제공 FNT 7개를 읽고 TTF/OTF 후보를 별도 작업 폴더에 준비했다. 설치된 게임, MO2, 기존 Output, 원본 FNT/Tex는 수정하지 않았다.

후보 폴더: `staging/font-source-candidates`. 출처, 파일 해시, 내부 글꼴 이름, 버전, 한글 지원 범위는 `manifest.json`에 있다. `font-shape-comparison.png`는 원본 비트맵과 후보의 글자 모양 비교표다.

| 기존 FNT | 확보한 후보 | 판단 |
|---|---|---|
| nanumsquare 18/20/22 | 네이버 공식 NanumSquare 1.000, Light/Regular/Bold/ExtraBold | 나눔스퀘어 계열과 부합한다. 이 비교에서는 Bold/ExtraBold가 가깝지만 굵기 확정은 보류한다. |
| Tmon20/30 | TmonMonsori Black 1.1.0 | 한글 표본의 모양이 매우 가깝다. 몬소리체가 유력하다. 다운로드는 제3자 미러이므로 원본 배포본 및 라이선스 문서 대조가 남아 있다. |
| dunggunmo-fixedsys 18 | 제작자 배포 DungGeunMo 1.301 | 둥근모꼴+Fixedsys 후보를 확보했다. 크기·효과·버전까지 동일하다고 확정하지 않는다. |
| Monofonto_STn | 제작자 DaFont 배포 Monofonto Regular 5.003 | 영문 모양은 부분적으로 가깝지만 옛 버전과 같다고 볼 수 없다. FNT에는 한글도 있으며 후보 Monofonto에는 한글이 없어 혼합 글꼴 가능성이 있다. |

나눔스퀘어 일반판 4개 굵기는 한글 완성형 11,172자를 지원한다. `_ac` 4개 굵기는 2,479자만 지원하므로 한글 기본 face로 선정하지 않는다. 둥근모꼴과 확보한 몬소리체도 완성형 11,172자를 지원한다. Monofonto는 한글을 지원하지 않는다.

## 비교의 범위

DC Font Generator 공식 소스의 296바이트 FNT 헤더, 56바이트 문자 항목, CP949 문자 인덱스, Tex RGBA 배치를 따라 원본 글자를 읽었다. FNT 헤더의 이름은 텍스처 참조 이름이며 원본 TTF 이름을 보증하지 않는다.

한글 13자와 영문/숫자 9자를 비교했다. 비트맵 알파와 후보 윤곽을 정규화한 뒤 겹치는 영역을 비교했고, 후보 크기 14~36px 및 획 확장 0/1px를 조사했다. 실제 글자가 없는 후보의 missing-glyph 모양은 점수에서 제외했다. 수치는 글꼴 식별 확률이 아니다. 기존 외곽선/글로우, 래스터라이저, 수동 수정, 다른 글꼴에서 가져온 문자 때문에 원본 굵기나 파일 버전을 확정할 수 없다. 비교표의 크기는 가장 가까운 시험값이며 게임의 최종 설정값이 아니다.

`tools/prepare_font_candidates.py`는 비교 후보를 내려받고 메타데이터를 수집한다. `tools/compare_font_candidates.py`는 FNT/Tex를 읽어 비교표와 `comparison.json`을 만든다. 어느 스크립트도 게임에 설치하거나 패쳐 번들에 글꼴을 넣지 않는다.

## 배포 조건

- **나눔스퀘어:** 네이버는 저작권 안내와 라이선스를 포함한 번들/재배포를 허용한다. 공식 안내 원문을 `NanumSquare/NAVER-license-source.html`에 보관했다.
- **둥근모꼴+Fixedsys:** 제작자가 퍼블릭 도메인으로 명시했다. 제작자 페이지 사본과 출처를 보관했다.
- **몬소리체:** 산돌구름 페이지 상단의 OFL 문구만으로 판단했던 초기 기록을 정정한다. 실제 상세 요약표는 OFL 비해당이며 TMON 자체 조건을 안내한다. 이후 티몬 디자인스토리 제작자 안내에서 게임/앱 임베딩 허용과 번들 시 출처·라이선스 동봉 조건을 직접 확인했다. 원본 TTF를 수정하지 않고 제작자 안내 및 사용 조건 사본, 출처를 함께 넣어 로컬 폰트 적용 후보에 포함했다. 다운로드 경로는 여전히 제3자 미러다.
- **현재 Monofonto:** 제작자 안내의 Desktop License는 폰트 파일 공유 및 게임 임베딩을 포함하지 않는다. 비교용 후보로만 보관하고 배포 번들에는 포함하지 않는다. 현재판의 조건을 과거판에 소급해서 판단하지 않는다.

## 출처

- [네이버 공식 나눔 글꼴](https://hangeul.naver.com/fonts/search?f=nanum)
- [네이버 라이선스 안내](https://help.naver.com/service/30016/contents/18088?osType=PC&lang=ko)
- [둥근모꼴+Fixedsys 제작자 배포](https://cactus.tistory.com/193)
- [Tmon몬소리 파운드리 목록](https://www.sandollcloud.com/free-font/703/TmonMonsoriOTF)
- [티몬 제작자 사용·게임 임베딩 안내](https://brunch.co.kr/@creative/32)
- [몬소리체 다운로드 미러](https://github.com/withstep/TmonMonsori)
- [Monofonto 제작자 배포·라이선스 설명](https://www.dafont.com/monofonto.font)
- [현재 Monofonto 공식 제품 설명](https://typodermicfonts.com/monofonto/)
- [DC Font Generator 공식 소스](https://github.com/TIAIMM/DC_Font_Generator_Community_Fork)

이후 `Output-Fonts-20261003`에 3종 TTF와 FreeType XML 시험 구성을 생성했다. 게임 안에서의 표시 검증과 최종 크기·효과 조정은 수행하지 않았다.
