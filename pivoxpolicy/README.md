# pivoxpolicy

AI 에이전트 관련 **금융 보안 규제·가이드라인을 모아, 같은 잣대로 코딩하고, 바뀐 것을 찾아내는** 연구 도구.
숭실대 학회 발표(2026-11, "AI 에이전트 시대, 금융회사 내부통제는 안전한가")를 저널·컨퍼런스 논문으로 올리기 위해
교수 피드백 — *"한·미 비교 기준이 추상적이다, 수치로 보완하라"* — 에 답하는 숫자를 만드는 것이 목적이다.

> 이 디렉터리는 `pivoxquant` 와 무관한 별도 프로젝트다. 저장소가 없어서 임시로 여기 둔다 — 아래 "별도 저장소로 옮기기".

## 무엇을 재나

**셀 하나 = 문서 × 통제.** 7개 에이전트 통제(덱 슬라이드 14)를 행으로, 관할(KR·US·EU·INTL)을 열로 놓고
각 셀에 "그 관할에서 그 통제를 요구하는 가장 센 문서의 구속력"을 적는다.

| 점수 | 뜻 |
|---|---|
| 0 | 어떤 문서도 다루지 않음 |
| 1 | 자율 — 가이드라인·표준·초안·감독 안내서한 |
| 2 | 구속력 있음, 에이전트를 이름 붙이지 않음 (사람·시스템 기준 규정) |
| 3 | 구속력 있음 **+ 에이전트 명시** |
| `?` | 문서는 있는데 아직 안 읽음 (코딩 필요) |

점수는 코더가 직접 매기지 않는다. 코더는 **"이 문서가 이 통제를 다루는가" (true/false/null) 와 근거 조문**만 적고,
문서의 `binding`(0·1·2) 과 `names_agents` 는 문서 레코드에 있다. 점수는 그 둘의 곱으로 자동 계산된다 (`pivoxpolicy/schema.py::cell_score`).
그래서 코더 둘의 결과를 그대로 Cohen's κ 로 비교할 수 있다.

**3 인 셀이 하나도 없으면 — 그것이 논문의 핵심 결과다.** 2026-11-11 1차 코딩 기준으로 3 은 없다 (`out/matrix-deck_2026-11-01.md`).

## 쓰는 법

```bash
cd pivoxpolicy
pip install pyyaml pytest          # 의존성은 이 둘뿐
python3 -m pivoxpolicy.cli check   # 레지스트리·코딩 스키마 검사
python3 -m pivoxpolicy.cli matrix  # 통제 × 관할 매트릭스 (--csv 가능)
python3 -m pivoxpolicy.cli gaps    # 구속력 2 미만·미코딩 셀
python3 -m pivoxpolicy.cli timeline
python3 -m pivoxpolicy.cli kappa   # 코더 둘 이상일 때 일치도
python3 -m pivoxpolicy.cli fetch   # 문서 URL 스냅숏 → snapshots/manifest.json, 바뀐 문서 보고
python3 -m pivoxpolicy.cli watch   # 발표 목록 페이지에서 새 글 찾기
python3 -m pivoxpolicy.cli intel   # RSS/Atom/JSON 피드에서 AI 에이전트 관련 새 항목 → snapshots/intel.jsonl
python3 -m pivoxpolicy.cli rubric --check   # 내부통제 평가 루브릭·평가 스키마 검사
python3 -m pivoxpolicy.cli assess example-worked_2026   # 기관 평가 프로필 (단일 등급 없음)
python3 -m pivoxpolicy.cli assess --compare             # 기관 × 차원 격자
python3 -m pivoxpolicy.cli report  # out/ 에 전부 쓰기 (매트릭스·연표·공백·κ·평가 프로필)
python3 -m pytest -q
```

## 두 가지 측정 — 혼동하지 말 것

- **통제 × 관할 매트릭스** (`matrix`): *규제·가이드라인이 무엇을 요구하나.* 문서 × 7통제, 구속력 0~3.
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
- 1차 코더 `deck_2026-11-01` 은 발표 덱의 2차 인용을 옮긴 것이다. **`provisional: true`** — 논문에 쓰려면 원문으로 2차 코딩을 하고 κ ≥ 0.61 을 확인해야 한다.

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

1. **2차 코딩** — `registry/codings/TEMPLATE.yaml` 복사 → 원문으로 30건 × 7 통제 코딩 → `kappa`. 이것이 교수 피드백에 답하는 숫자다.
2. `?` 셀 채우기 — `out/gaps-*.md` 가 목록. 특히 EU(AI Act 를 제14조 밖으로 넓힐지), 재무부 FS AI RMF 230 통제목표, ISO 42001.
3. inbox.md 의 11-01 이후 단서를 문서로 올리기 (금융위 11-05 간담회, NYDFS 05-21·09-10 서한, FSI 17개 항목 원문).
4. 한국판 공시 지표 — 미국 10-K 분석(덱 슬라이드 12)의 짝. 이 도구 범위 밖이지만 같은 레지스트리를 쓸 수 있다.
