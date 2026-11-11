# pivoxpolicy

AI 에이전트 관련 **금융 보안 규제·가이드라인을 모아, 같은 잣대로 코딩하고, 바뀐 것을 찾아내는** 연구 도구.
숭실대 학회 발표(2026-11, "AI 에이전트 시대, 금융회사 내부통제는 안전한가")를 저널·컨퍼런스 논문으로 올리기 위해
교수 피드백 — *"한·미 비교 기준이 추상적이다, 수치로 보완하라"* — 에 답하는 숫자를 만드는 것이 목적이다.

> 이 디렉터리는 `pivoxquant` 와 무관한 별도 프로젝트다. 저장소가 없어서 임시로 여기 둔다 — 아래 "별도 저장소로 옮기기".

## 무엇을 재나

**셀 하나 = 문서 × 통제 × 층.** 7개 에이전트 통제(덱 슬라이드 14)를 행으로, 관할(KR·US·EU·INTL)을 열로 놓고
각 칸에 "그 관할에서 그 통제를 요구하는 가장 센 문서의 구속력"을 적는다 — **두 층으로 따로**(코드북 v2, 2026-11-11):

| 층 | 묻는 것 | 점수 |
|---|---|---|
| `analog` 일반 통제 | 문서가 이 통제를 **사람·계정·일반 시스템**을 대상으로 요구·권고하는가 (퇴직자 계정 정지, 결재, 접근 로그…) | 0 미다룸 · 1 자율 · 2 구속력 |
| `agent` AI·에이전트 적용 | 문서가 이 통제를 **AI 시스템·모델·AI 에이전트**를 대상으로 요구·권고하는가 | 0 · 1 · 2 구속력(AI 일반) · **3 구속력 + 에이전트 명시** |

`?` = 문서는 있는데 아직 안 읽음(코딩 필요). 폐지·대체된 문서(`status: superseded`)는 매트릭스에 넣지 않는다.

**왜 두 층인가.** 처음엔 통제마다 '다룸' 한 칸이었다(v1). 발표 덱을 옮긴 1차 코더와 원문을 읽은 2차 AI 코더의 불일치 12칸이
*전부* 같은 물음 — "직원 통제의 유사물(계정 정지 · CISO 승인)이 있으면 에이전트 통제를 다룬 것인가" — 에서 갈렸다(κ 0.70).
교수 피드백 "비교 기준이 추상적" 이 가리킨 곳이 여기다. 두 층으로 나누면 그 물음이 사라지고, 논문의 주장
— *일반 통제는 구속력이 있는데 AI·에이전트에 적용한 요구는 없거나 자율뿐* — 이 **칸 단위 간극**(일반 2 · AI 2 미만)으로 세어진다.

점수는 코더가 직접 매기지 않는다. 코더는 층마다 **true/false/null 과 근거(위치 + 원문 인용)**, AI 층이 true 면 근거 조항의 대상
(`subject: agent` = 에이전트 명시 / `ai` = AI 일반)만 적는다. 문서의 `binding`(0·1·2)은 문서 레코드에 있고, 점수는 자동 계산된다
(`pivoxpolicy/schema.py::cell_score` · `layer_view`). 그래서 코더 둘의 결과를 층마다 그대로 Cohen's κ 로 비교할 수 있다.

- **판정 기준은 `registry/controls.yaml` 하나** — 층 정의, 공통 규칙 G1~G8(범위·요구의 형태·대상으로 층 가르기·증거·경계 사례),
  통제마다 `true_if` / `false_if`. 규칙은 조항 유형으로만 쓴다 — 특정 문서·조문을 이름 붙이면 κ 가 부풀려진다(테스트가 막는다).
- **코더는 같은 원문을 읽는다** — 고정 코퍼스 21건(`snapshots/corpus.json` 에 문서별 출처·범위·sha256). 본문 텍스트는 저작권 때문에
  저장소에 넣지 않는다. ISO/IEC 27001·42001 은 원문이 유료라 코퍼스에 없다(미코딩).
- 빈 양식은 `registry/codings/TEMPLATE.yaml`. v1 코딩(`deck_2026-11-01` · `ai_coder_2026-11-11`)은 기록으로 남기고 그대로 읽힌다.

## 쓰는 법

```bash
cd pivoxpolicy
pip install pyyaml pytest          # 의존성은 이 둘뿐
python3 -m pivoxpolicy.cli check   # 레지스트리·코딩 스키마 검사
python3 -m pivoxpolicy.cli matrix  # 통제 × 관할 — 두 층 나란히 (--layer analog|agent 로 한 층, --csv, --coder)
python3 -m pivoxpolicy.cli gaps    # AI·에이전트 층이 구속력 2 미만인 칸 (옆에 일반 층 점수)
python3 -m pivoxpolicy.cli timeline
python3 -m pivoxpolicy.cli kappa   # 코더 간 일치도 — 층마다 (인자 없으면 두 층 코더 둘, `kappa A B` 로 지정)
python3 -m pivoxpolicy.cli incident-kappa   # 사건 × 통제 코딩 일치도
python3 -m pivoxpolicy.cli fetch   # 문서 URL 스냅숏 → snapshots/manifest.json, 바뀐 문서 보고
python3 -m pivoxpolicy.cli watch   # 발표 목록 페이지에서 새 글 찾기
python3 -m pivoxpolicy.cli intel   # RSS/Atom/JSON 피드에서 AI 에이전트 관련 새 항목 → snapshots/intel.jsonl
python3 -m pivoxpolicy.cli rubric --check   # 내부통제 평가 루브릭·평가 스키마 검사
python3 -m pivoxpolicy.cli assess example-worked_2026   # 기관 평가 프로필 (단일 등급 없음)
python3 -m pivoxpolicy.cli assess --compare             # 기관 × 차원 격자
python3 -m pivoxpolicy.cli report  # out/ 에 전부 쓰기 (매트릭스·연표·공백·κ·평가 프로필)
python3 -m pivoxpolicy.cli incidents  # AI 에이전트 보안 사건 45건 × 7통제 교차표
python3 -m pivoxpolicy.cli site    # out/index.html 정적 대시보드 (Pivox 블랙·골드 — matrix·동향·사건·프로필 한 장)
python3 -m pytest -q
```

## 대시보드 (out/index.html)

`site` 명령이 레지스트리 + intel.jsonl 을 한 페이지로 낸다. 디자인은 **PivoxQuant·PivoxMap·PivoxData 와 맞췄다**
(Vantablack `#050505` + Bronze `#B8956A` + Pretendard, 뉴스 사이트형 한 페이지, 알약·박스·글로우·italic 없음).
토큰·CSS 는 `pivoxpolicy/templates/`(pivoxmap globals.css · pivoxdata research.css 에서 옮긴 것, pivoxpolicy-research 워크플로가 추출).
섹션: 지금 바뀐 것(규제 동향) · 사건(AI 에이전트 보안) · 통제×관할 매트릭스(브론즈 알파 히트, AA 대비 확인) · 공백 · 평가 프로필(16차원) · 연표 · 문서 색인 · 출처·방법.
빨강·초록은 안 쓴다(가격색은 가격에만). 대시보드의 동향·사건은 AI 에이전트 관련성 필터를 거친다(intel.jsonl 전체 수집과 별개).

## 커스텀 API 어댑터

JSON Feed 가 아닌 공공 API 는 `feeds.yaml` 의 `adapter:` 로 읽는다(`pivoxpolicy/intel.py::parse_adapter`, 2026-11-11 실측 응답 모양):
`kev`(CISA KEV — AI 플랫폼 벤더·제품명으로 걸러 '실제 악용된 AI 플랫폼 취약점') · `nvd`(prompt injection CVE, 실행 때 최근 90일 창) ·
`federalregister`(연방관보 AI agents) · `assembly`(국회 의안 — 전자금융거래법·인공지능) · `fsi_bbs`(금보원 보도자료·소식 POST 엔드포인트).

## 세 가지 측정 — 혼동하지 말 것

- **통제 × 관할 매트릭스** (`matrix`): *규제·가이드라인이 무엇을 요구하나.* 문서 × 7통제, 구속력 0~3.
- **사건 × 통제** (`incidents`): *실제 AI 에이전트 사건에서 어느 통제가 실패했나.* 45건, 증거 수준(1차·벤더·보도)별로 센다.
  related_controls(1차, finder 판단) 와 `registry/incident_codings/`(2차, 블라인드) 를 `incident-kappa` 로 비교한다 — 아래 '2차 코딩 결과'.
- **내부통제 평가 프로필** (`assess`): *한 금융회사가 공개 자료상 무엇을 하는가.* 기관 × 16차원, 증거 수준 0~3.
  - 16차원 = 7통제(agent_control) + 경고→조치 연결(connection 2) + 모의해킹 4요소(testing 4) + 사고 대응(response 3).
  - **단일 등급으로 뭉치지 않는다.** 차원별 레벨 프로필 + 그룹 분포만. 레벨은 "증거 수준" 이지 "통제 유무" 가 아니다.
  - 실제 기관 평가는 명예훼손·공정성 때문에 시드에 넣지 않았다 — `example-worked_2026` 은 가상 예시다.
  - 설계 근거: `registry/rubric.yaml` (덱 슬라이드 2·14·15 + pivoxmap 평가체계 노트). provisional — 리서치 워크플로가 FSB·OWASP ASI·NCCoE 원문으로 basis 를 채우면 교체.

`pip install -e .` 하면 `pivoxpolicy` 명령으로도 된다.

## 디렉터리

```
registry/
  controls.yaml          7개 통제 정의 + 주제 태그
  feeds.yaml             intel 이 읽는 RSS/Atom/JSON 피드 77곳 (KISA 보호나라·금융위·과기정통부·개인정보위·NIST·연준·FDIC·재무부·SEC·FSB·EBA·ESMA·ECB·FCA·BoE·NCSC·JFSA + AI 위협 벤더·arXiv·보안매체). pivoxpolicy-research 워크플로(2026-11-11)가 찾아 검증
  incidents.yaml         AI 에이전트 보안 사건 45건(2025-01~) — ai_role · evidence_level · 관련 통제. source_url 전부 2026-11-11 HTTP 200 재확인
  frameworks.yaml        루브릭 basis 가 가리키는 13개 프레임워크(FSB·NCCoE·IR 8596·OWASP ASI·CSA MAESTRO·NYDFS·COSO·BCBS·EU AI Act·SEC S-K 106 …)
  sources.yaml           watch 가 보는 발표 목록 페이지 (금융위·금보원·금감원·NIST·연준·OCC·FDIC·NYDFS·재무부·FINRA·FSB)
  documents/<id>.yaml    문서 1건 = 파일 1개 (30건, 2026-11-11)
  codings/<coder>.yaml   코더 1명 = 파일 1개. TEMPLATE.yaml 을 복사해 2차 코더를 만든다
  inbox.md               확인은 했지만 아직 문서로 안 넣은 단서 (날짜·출처 포함)
snapshots/
  manifest.json          id 별 url·sha256·크기·받은 시각·HTTP 상태·에이전트 언급 수·목록 링크 (git 추적)
  content/               받은 본문 (git 추적 안 함)
out/                     report 가 쓰는 매트릭스·연표·공백·κ (git 추적 — 논문에 붙일 표)
tests/                   pytest 22개, 네트워크 없이 돈다
```

## 문서 레코드 규칙

- `url` 이 없으면 `url_note` 에 왜 없는지 적는다 ("확인 필요 — …"). `url_verified` 는 **실제로 200 을 받은 날**만 적는다.
- `binding` 0 = 보도자료·보고서(규범 아님, 점수 안 냄) · 1 = 자율 · 2 = 구속력. `doc_type` 과 모순이면 `check` 가 거절한다.
- `names_agents` 는 원문을 안 봤으면 `null`. 추측으로 true/false 를 넣지 않는다.
- `summary` 끝에 **어디서 알았는지**(덱 노트 / 보도 / 원문) 를 `source_note` 로 남긴다.
- 1차 코더 `deck_2026-11-01` 은 발표 덱의 2차 인용을 옮긴 것이다. **`provisional: true`**. 2차 코더 `ai_coder_2026-11-11` 은 원문 기반 — 아래.

## 2차 코딩 결과 (2026-11-11, `report` 가 out/ 에 다시 쓴다)

블라인드 AI 에이전트 5개(문서 KR·US·EU/INTL 3 + 사건 2)가 1차 코딩·문서 요약·incidents.yaml·out/ 을 보지 않고
원문(law.go.kr 고시·법령 본문, 공식 PDF·HWPX, SEC·NIST·NYDFS 원문)을 읽어 코딩했다.
**같은 모델 계열의 두 판단이다 — κ 는 '입력이 다른 두 AI 판단의 일치' 이지 사람 코더 간 신뢰도가 아니다.** 논문엔 사람 코더 1명을 더한다.

| 측정 | 셀 | κ | 파일 |
|---|---|---|---|
| 문서 × 통제 covered | 80 (둘 다 코딩한 칸) | **0.705** substantial · 점수 κ 0.764 | `out/kappa-*.md` |
| 사건 × 통제 실패 | 315 (45 × 7) | **0.417** moderate | `out/incident-kappa-*.md` |

**문서 불일치 12칸은 전부 같은 방향**(1차 false · 2차 true)이고, 대부분이 *직원 통제의 유사물을 에이전트 통제로 볼 것인가* 다 —
전자금융감독규정 §13①11(인사조치 시 계정 정지) = 즉시중단? · NYDFS §500.15(b) CISO 서면 승인 = 사람 승인? · CISA BOD 22-01 FAQ 의 자산 격리 = 즉시중단?
`controls.yaml` 은 통제마다 `employee_analog` 와 `agent_requirement` 를 둘 다 적지만 **어느 쪽이 '다룸' 인지 판정 규칙이 없다**(교수 피드백 '비교 기준이 추상적' 과 같은 지점).

- 그래서 관할 점수가 판단에 따라 갈리는 칸이 **6** (`out/matrix-diff-*.md`): KR 인벤토리 0→2 · 사람승인 1→2 · 즉시중단 1→2, US 고유ID 1→2 · 사람승인 0→2 · 즉시중단 0→2.
  덱의 'US 사람승인·즉시중단 0' 은 엄격한 읽기(agent_requirement)에서만 성립한다.
- **코더와 무관하게 남는 것**: 어느 관할에도 점수 3(구속력 + 에이전트 명시)이 없다. 에이전트를 이름 붙인 요구는 자율 문서(금보원 평가기준 · NIST NCCoE · FSB)에만 있다.
- 사건: 두 코더가 모두 실패를 본 사건 — 최소권한 **18** · 사람승인 **9** · 공급자 8 · 고유ID 6 · 즉시중단 2 · 인벤토리 1 · 감사기록 **0**.
  1차의 '감사기록 20 · 즉시중단 14' 는 2차에서 2 · 2 — 2차는 원문이 그 통제의 실패를 *적어야* 참으로 봤고, 1차는 '로그로 못 찾았다' 류를 추론했다. 이 둘도 판정 규칙(원문 명시 vs 추론)을 먼저 정해야 한다.

## 알고 있는 한계 (2026-11-11 실측)

- `law.go.kr` 은 1.3 KB 자바스크립트 껍데기만 내려준다. 해시로 개정을 못 잡는다 → 규정 개정은 사람이 확인.
- `fsec.or.kr`(금보원) · `fss.or.kr`(금감원) 목록은 스크립트 렌더링 → 링크 0건. 해시 변경만 보인다.
- `eur-lex.europa.eu` 는 HTTP 202 + 빈 본문(봇 차단). `iso.org` 는 403. 두 곳은 URL 만 두고 `url_verified: null`.
- `cisa.gov` 는 curl 에는 403, 이 도구의 urllib 에는 200 — UA 에 따라 다르다.
- watch 는 **앵커 텍스트 키워드**로 거른다. 제목에 키워드가 없는 문서는 놓친다. 그래서 inbox.md 에 사람이 본 것을 따로 적는다.

## 별도 저장소로 옮기기

GitHub 에 빈 `pivoxpolicy` 저장소를 만든 뒤, `pivoxquant` 루트에서:

```bash
git subtree split --prefix=pivoxpolicy -b pivoxpolicy-split
```

```bash
git push git@github.com:seanbae-analyst/pivoxpolicy.git pivoxpolicy-split:main
```

옮긴 다음 `pivoxquant` 에서는 이 디렉터리와 `.dockerignore` 의 `pivoxpolicy` 줄을 지운다.

## 다음 할 일 (우선순위)

1. **판정 규칙을 정하고 사람 코더 1명** — `controls.yaml` 에 통제마다 '유사물(직원 통제)만 있으면 다룸인가' 를 한 줄로 정한 뒤
   (권장: 두 층으로 — `covered_analog` · `covered_agent`), 사람이 원문으로 코딩 → 세 코더 κ. 사건도 '원문 명시만 참' 규칙을 codebook 에.
2. `?` 셀 채우기 — `out/gaps-*.md` 가 목록. 특히 EU(AI Act 를 제14조 밖으로 넓힐지), 재무부 FS AI RMF 230 통제목표, ISO 42001.
3. inbox.md 의 11-01 이후 단서를 문서로 올리기 (금융위 11-05 간담회, NYDFS 05-21·09-10 서한, FSI 17개 항목 원문).
4. 한국판 공시 지표 — 미국 10-K 분석(덱 슬라이드 12)의 짝. 이 도구 범위 밖이지만 같은 레지스트리를 쓸 수 있다.
