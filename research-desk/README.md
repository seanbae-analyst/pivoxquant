# 데이터 지식 베이스 · 리서치 데스크

데이터 관리(데이터 카탈로그, AI-ready 데이터, 거버넌스, 플랫폼, 품질·리니지) 정보를 **긁어와 쌓아 두고, 웹사이트에서 질의응답**한다. 두 층이다.

1. **질의응답 (`/`)** — 수집해 둔 공식 문서·표준·엔지니어링 블로그 안에서만 답하고, 문장마다 출처를 단다. 없으면 없다고 말한다.
2. **리서치 데스크 (`/research`)** — 지식 베이스에 없는 질문을 웹에서 깊게 조사한다. 브리프를 이슈 트리로 쪼개고, 반대 근거까지 찾아, 출처 달린 리서치 노트를 쓴다.

PivoxQuant 와는 독립된 프로젝트다. 이 폴더만 떼어 새 저장소로 옮겨도 그대로 돈다.

## 지식 베이스가 도는 방식

```
kb/sources.yaml ─┐
                 ▼
  수집(crawl)  robots.txt 준수 · 사이트맵/RSS/URL · 호스트당 1초 간격
      │
      ▼
  본문 추출·조각내기  main/article 만 · 소제목 경로 보존 · ~1,800자 조각
      │
      ▼
  임베딩  Voyage voyage-4 (문서/질문 input_type 구분)
      │
      ▼
  저장  kb/index.json (파일) 또는 Postgres + pgvector (db/schema.sql)
      │
질문 ─┴─▶ 하이브리드 검색(벡터 + 키워드, RRF) ─▶ 재정렬(rerank-2.5) ─▶ search_result 블록 ─▶ Claude 답변 + 인용
```

- **출처가 없는 문장은 없다.** 조각을 `search_result` 블록으로 넘기고 인용을 켠다. Claude 가 문장마다 `search_result_location` 인용을 돌려주고, 화면은 출처 번호와 인용문을 같이 보여준다. 인용이 하나도 없으면 "근거 부족"으로 표시하고 리서치 데스크로 안내한다.
- **변경 감지.** 본문 해시가 같으면 다시 임베딩하지 않는다. 주기적으로 `npm run ingest` 를 돌리면 바뀐 페이지만 갱신된다.
- **출처 위계 라벨**(`tier`)이 답변 화면에 보인다. 벤더 문서는 `vendor` 로 표시해 자기 주장임을 드러낸다.

### 수집

```bash
npm run ingest -- --dry-run               # 키 없이: 후보 수·조각 수만 (사이트맵 주소 확인용)
npm run ingest -- --source dbt --limit 20 # 한 출처, 20페이지
npm run ingest                            # 전체 (VOYAGE_API_KEY 필요)
npm run kb:stats                          # 현황
```

수집 대상은 `kb/sources.yaml`. 항목 하나 = 출처 하나 (`kind: sitemap | rss | urls`, 경로 정규식 `include`/`exclude`, `maxPages`, `tier`). Medium 에 올라간 블로그(Netflix, Airbnb 등)는 봇을 403 으로 막아 뺐다.

### 저장소 선택

- 기본: `kb/index.json` 파일. DB 없이 돌고, 수천 조각까지 충분하다. Vercel 에 올릴 땐 이 파일을 저장소에 커밋하거나(`.gitignore` 에서 빼고) 빌드 단계에서 만든다.
- 규모가 커지면 `DATABASE_URL` 을 주고 `db/schema.sql` 을 적용한다 (Supabase 면 pgvector 확장이 기본 제공).

## 분야 (도메인 팩)

분야는 `src/lib/research/domains/` 의 팩 하나로 정의된다. 팩 = 리서치 유형 목록(유형마다 이슈 트리 틀 + 노트 본문 틀) + 출처 위계 + 신뢰도 기준 + 시사점 절. 노출할 분야는 `NEXT_PUBLIC_RESEARCH_DOMAINS` (쉼표 구분, 예 `data` 면 데이터 전용 사이트), 기본 분야는 `NEXT_PUBLIC_RESEARCH_DOMAIN` (비면 첫 번째). 둘 이상 노출되면 화면에 탭이 생긴다.

### 데이터 (`data`, 기본)

| 유형 | 이슈 트리 틀 | 노트 본문 |
|---|---|---|
| 데이터 카탈로그 구축 | 목적·범위 → 메타데이터 모델 → 도구 선택 → 수집 자동화 → 운영 체계 | 도구 비교 표, 자동/수동 경계, 채택 지표, 첫 90일 |
| AI-ready 데이터 | 정의·기준 → 데이터 계약·스키마 → 준비 파이프라인 → 평가 → 사례 | 정의 비교 표, 파이프라인 단계 표(RAG/학습 구분), 준비도 지표 |
| 데이터 거버넌스 | 프레임워크 → 역할·조직 → 정책·강제 수단 → 규제 → 성숙도·실패 | 프레임워크 표, 규제 요구 표, 코드로 강제되는 것과 아닌 것 |
| 플랫폼 아키텍처 | 선택지·테이블 포맷 → 선택 기준 → 실제 비용 → 운영 → 전환 사례 | 기준별 비교 표, 비용 사례, 전환 사례 |
| 품질·관측·리니지 | 품질 차원·규칙 → 도구 → 관측의 한계 → 리니지 자동화 → 운영 | 도구 표, 잡는 것/놓치는 것, SLA·사고 대응 |
| 도구·벤더 비교 | 후보·범주 → 기능 → 연동 → 비용·운영 → 제3자 평가 | 후보 표, 기능 표(로드맵 분리), 커뮤니티 건강 |
| 자유 질문 | MECE 이슈 트리 (도구는 버전·라이선스 포함) | 하위 질문별 발견 |

출처 위계: 표준·규제 원문 > 공식 문서·릴리스 노트·저장소 > 논문·컨퍼런스 > 도입 기업 엔지니어링 블로그 > 애널리스트 > 벤더 백서 > 개인 블로그. 벤더 주장과 제3자 도입 후기를 구분하고, 오픈소스 기능은 버전을 붙인다. 시사점 절은 "적용 시사점" — 먼저 할 것과 미룰 것.

### 컨설팅 (`consulting`)

| 유형 | 이슈 트리 틀 | 노트 본문 |
|---|---|---|
| 시장 규모 | 시장 정의 → 탑다운 → 바텀업 → 성장 드라이버 → 기존 추정치 | 두 방법의 추정치 나란히, 가정과 차이 원인 |
| 경쟁 환경 | 플레이어 → 규모·점유율 → 포지셔닝 → 최근 12개월 → 진입 장벽 | 경쟁 지도 표, 빈자리 |
| 산업 구조 | 밸류체인 → 수익 풀 → 5 forces → 구조 변화 → 수익성 분포 | 단계별 표, 힘마다 강/중/약 |
| 사례 벤치마크 | 사례 선정 → 조건 → 실행 → 결과 → 성패 요인 | 사례 비교 표, 의뢰인과의 차이 |
| 규제·정책 | 법령·관할 → 인허가 요건 → 개정 동향 → 제재 사례 → 해외 비교 | 요건 표, 시행 시점 |
| 자유 질문 | MECE 이슈 트리 | 하위 질문별 발견 |

출처 위계: 공공 통계 > 협회 > 공시 > 리서치 기관 > 언론 > 블로그. 시사점 절은 의뢰 배경에 비춘 함의.

모든 분야에 공통: **핵심 요약**(사실 + So what) → 본문(소제목마다 So what 한 줄) → **시사점** → **근거 신뢰도와 한계**, 그리고 부록(주장·판정 표, 수치표, 출처 목록).

### 새 분야 추가

`domains/` 에 `DomainPack` 모양의 파일 하나를 넣고 `domains/index.ts` 의 `DOMAINS` 에 등록한다. 파이프라인·화면은 손대지 않는다. `domains.test.ts` 가 팩의 불변식(custom 유형 존재, 빈 틀 없음)을 검사한다.

## 왜 이렇게 만들었나

- **출처 위계가 분야마다 있다.** 조사·추출·판정 단계가 팩의 위계와 신뢰도 기준으로 주장을 매긴다.
- **수치는 값·단위·연도·지역을 떼어 놓지 않는다.** 추출 단계가 수치 주장을 구조화해 부록 수치표로 만든다. 시장 규모는 탑다운과 바텀업을 별도 하위 질문으로 강제해 삼각검증한다.
- **반증이 기본이다.** 조사 단계와 별개로 반증 단계가 "이 주장을 무너뜨릴 근거"를 따로 검색한다. 판정은 유지 / 기각 / 미결 셋뿐이고, 기각된 주장은 보고서에 사실처럼 쓰지 않는다.
- **출처 없는 숫자는 없다.** 추출 단계에서 모델이 실제로 열어 본 URL 이 아닌 출처는 버린다. 보고서 부록에 주장별 출처 번호와 반대 출처가 표로 붙는다.
- **서버는 아무것도 저장하지 않는다.** 보고서는 브라우저 localStorage 에만 남고 `.md` 로 내려받는다.
- **파이프라인은 네트워크를 모른다.** `pipeline.ts` 는 `Llm` 인터페이스 세 동작(`searchTurn` / `parseJson` / `streamText`)만 부른다. 실제 구현은 `llm.ts`, 테스트는 가짜 구현.

## 구조

```
src/lib/kb/
  types.ts        SourceConfig · Doc · Chunk · KbStore · Embedder · AskEvent
  text.ts         HTML → 본문, 본문 → 조각, 인용 단위 분할 (순수)
  crawl.ts        robots · 사이트맵 · RSS · 페이지 수집 (fetch 주입 가능)
  ingest.ts       수집 → 임베딩 → 저장, 해시로 변경 감지
  embed.ts        Voyage 임베딩·재정렬
  store-memory.ts 파일 저장소 + 하이브리드 검색(RRF)
  store-pg.ts     Postgres + pgvector 저장소
  answer.ts       search_result 블록 + 인용 스트리밍 답변
  index.ts        조립 (DATABASE_URL 유무로 저장소 선택)
kb/sources.yaml   수집 대상
db/schema.sql     pgvector 스키마
scripts/ingest.ts 수집 CLI · scripts/kb-stats.ts 현황
src/app/api/ask/route.ts        POST {question} → text/event-stream (AskEvent)
src/app/api/kb/stats/route.ts   GET 현황
src/components/ask-desk.tsx     질의응답 화면

src/lib/research/
  domains/      도메인 팩 — data.ts · consulting.ts · index.ts(등록부·기본 분야)
  types.ts      Brief(분야·유형·주제·범위·배경) · Claim(수치 필드 포함) · Report · 이벤트
  pipeline.ts   계획 → 조사(병렬) → 반증 → 판정 → 집필. 순수 오케스트레이션
  llm.ts        Anthropic 구현 — web_search / web_fetch 서버 도구, 구조화 출력, 스트리밍, server-side fallback
  prompts.ts    팩의 틀·위계를 끼워 넣는 단계별 지시문 (한국어)
  schemas.ts    zod 스키마 (Plan / Claims / Verdicts)
  sources.ts    응답 블록에서 출처 URL 수집 (순수)
  report.ts     부록(주장·판정 표, 수치표, 출처 목록) 렌더 (순수)
  sse.ts        이벤트 인코딩/디코딩 (서버·브라우저 공용)
src/app/api/research/route.ts   POST {domain?, type?, topic, geography?, timeframe?, context?} → text/event-stream
src/components/research-desk.tsx 화면
```

## 실행

```bash
cp .env.example .env.local   # ANTHROPIC_API_KEY 채우기
npm install
npm run dev                  # http://localhost:3000
```

검증:

```bash
npm run typecheck && npm run lint && npm test && npm run build
npm run ingest -- --dry-run --source iceberg --limit 5   # 크롤러 실측
```

## 비용 감각

기본 모델은 `claude-opus-5`. 브리프 하나 = 기획 1회 + (검색 턴 + 추출) × 하위 질문 4~5 + 반증 검색 1회 + 판정 1회 + 집필 1회. 검색 턴은 하위 질문당 웹 검색 최대 6회(`RESEARCH_MAX_SEARCHES`), 반증은 +2회. 비용을 낮추려면 `RESEARCH_MODEL=claude-sonnet-5`.

안전 분류기가 요청을 거절하면 서버가 대체 모델로 같은 요청을 다시 돌린다 (`fallbacks: "default"`). 끄려면 `llm.ts` 의 `base` 에서 `betas` 와 `fallbacks` 를 지운다.

## 배포

Vercel 에 그대로 올라간다. 환경변수 `ANTHROPIC_API_KEY` 만 넣으면 된다. API 라우트의 `maxDuration = 300` 은 플랜에 따라 상한이 다르니 확인할 것.

## 새 저장소로 떼어내기

```bash
# pivoxquant 루트에서
git subtree split --prefix=research-desk -b research-desk-only
# 새 저장소를 GitHub 에서 만든 뒤
git push git@github.com:<you>/research-desk.git research-desk-only:main
```
