# Pivoxmap — data catalog 틈새시장 조사

> 작성: 2026-09-11 · 대상: 배상현(CEO) · 확인일 전부 2026-09-11
> 방법: WebSearch 10건(쿼리 전문 §7) + 인수건 2건만 1차 발표문으로 교차확인.
> **⚠️ 근거 등급 낮음.** 위 온보딩 조사(`onboarding-competitor-research_2026-09-06.md`)처럼 앱 번들·규제 PDF를
> 직접 뜯은 게 아니라 **검색 요약·벤더 블로그 위주**다. §7 의 "검증 안 된 것" 을 먼저 읽어라.
> **⚠️ 제품 정의 미상.** 이 레포에 `pivoxmap` 문자열 **0건**(`grep -ril pivoxmap .`, node_modules/.git 제외, 2026-09-11).
> 그래서 "Pivoxmap 에 맞는 틈새"가 아니라 **"data catalog 시장에 지금 남은 틈"** 을 쟀다. §6 의 질문 4개에 답하면 범위가 좁혀진다.

---

## 0. 한 줄 결론

**범용 데이터 카탈로그는 2026 현재 닫히는 중이다.** 독립 카탈로그 스타트업은 3사 연속 피인수됐고(Castor→Coalesce 2025-03,
Secoda→Atlassian 2025-12), 아래층(테이블 포맷 컨트롤 플레인)은 Databricks·Snowflake 가 오픈소스로 무료화했고,
위층(엔터프라이즈 거버넌스)은 Collibra·Alation 이 인수로 메우고 있다.
남은 틈은 "사람이 브라우징하는 카탈로그"가 아니라 **"에이전트가 런타임에 질의하는 컨텍스트"** 인데,
거기도 이미 OpenMetadata 2.0 · DataHub · Marmot 이 MCP 로 들어와 있다 — **범용 포지션은 이미 만원이다.**

1인 개발자가 들어갈 자리는 셋 중 하나다:
**(a) 글로벌 SaaS 가 못 들어오는 규제 수직** · **(b) 기존 카탈로그가 안 덮는 자산 종류** · **(c) 카탈로그를 *채우는* 문제.**
(c) 가 가장 일관되게 확인된 미해결 통증이다 — 실패 원인 조사에서 도구가 아니라 **콘텐츠 공백**이 반복해 나온다.

---

## 1. 시장 크기 — 숫자는 못 믿는다

| 출처 | 2026 시장 규모 추정 | 성장률 |
|---|---|---|
| Research and Markets | — | 2032 USD 6.21B, CAGR 25.4% |
| SNS Insider | — | 2035 USD 19.84B, CAGR 21.14% |
| Coherent Market Insights | USD 3.01B | — |
| (검색 요약 중 미귀속 2건) | USD 1.59B / USD 4.68B | — |
| Persistence(추정) | USD 1.43B | — |
| Fortune Business Insights (메타데이터 관리 툴, 상위 범주) | USD 17.41B | 2034 USD 81.15B, CAGR 21.22% |

**같은 해 추정치가 1.43B ~ 4.68B 로 3.3배 벌어진다.** 전부 리서치밀 리포트고 방법론 비공개다.
→ **이 표를 의사결정·피치에 쓰지 마라.** 여기서 건질 건 숫자가 아니라 방향 하나뿐: 카테고리는 아직 자라고 있다.

---

## 2. 지난 18개월 구조 변화 — 이게 진짜 신호다

| 날짜 | 사건 | 근거 등급 |
|---|---|---|
| 2025-03-19 | **Coalesce 가 CastorDoc 인수** → `Coalesce Catalog` 로 편입. "모던 데이터 스택 최초의 카테고리 간 인수"(CEO 발언) | 공식 발표문 |
| 2025-05 | **Alation 이 Numbers Station AI 인수** (구조화 데이터용 에이전트) → Agentic Platform 베타 | 2차 |
| 2025-06 | **Collibra 가 Raito 인수** (데이터 접근 거버넌스) | TechCrunch |
| 2025-07 | **Collibra 가 Deasy Labs 인수** (비정형·LLM 자산 거버넌스) | 2차 |
| 2025-12-04 | **Atlassian 이 Secoda 인수** → Rovo AI 에 흡수. 총 조달 $16.3M 짜리가 워크플로 회사로 흡수됐다 | 공식 발표문 |
| 2026-02-18 | **Apache Polaris 가 ASF Top-Level Project 승격** (Snowflake·Dremio 후원) | 2차 |
| 2026-03 | **Apache Gravitino 1.2.0** — "카탈로그의 카탈로그" 연합 메타데이터 레이크 | 2차 |
| 2026-08 | **OpenMetadata 2.0 RC** — "the open context layer for data and AI" 로 리브랜딩. MCP·지식그래프·stored memory 탑재. 주 소비자를 **사람 → 에이전트**로 선언 | 2차 |

**해석 (이게 이 문서의 핵심):**
독립 카탈로그는 **단독 제품으로 안 팔린다.** 워크플로(Atlassian)·변환(Coalesce)·쿼리엔진(Databricks/Snowflake)에
**붙어야** 팔린다. 1인 창업자가 "카탈로그 회사"를 세우면 현실적 경로가 **피인수 하나**로 좁아진다.
그게 목표면 합리적 선택이지만, 무료 베타로 유저 붙이는 PivoxQuant 식 경로와는 게임이 다르다.

---

## 3. 들어가지 마라 — 확인된 레드오션 3

1. **범용 엔터프라이즈 카탈로그.** Collibra·Alation·Atlan·Microsoft Purview·Coalesce Catalog. 영업 주도 시장(Select Star 조차 연 $70k~$90k 구간으로 인용된다). 1인 창업자가 살 수 없는 유통 경로.
2. **Iceberg REST 카탈로그 구현체.** Polaris·Unity Catalog·Glue·Nessie·Lakekeeper 가 전부 **오픈소스 무료**이고, 벤더들이 전략적으로 손해 보며 민다. 여기서 과금할 방법이 없다.
3. **"AI-ready context layer" 범용 포지션.** Atlan · OpenMetadata 2.0 · DataHub · OvalEdge · Tellius · Marmot 이 **문자 그대로 같은 문구**를 쓴다(전부 2026 콘텐츠). 카피로는 차별화 불가.

> 부수 관찰: 이 카테고리 검색 1페이지를 **Atlan 자체 SEO 콘텐츠가 장악**하고 있다
> (`atlan.com/know/*`, `atlan.com/data-catalog-tools/`, 경쟁사 이름 단 비교글 다수).
> 즉 **구매자가 보는 정보가 벤더 소유**다. 이 비대칭 자체가 기회지만 그건 제품이 아니라 미디어다 (§4-E).

---

## 4. 틈새 후보 6개

| # | 틈새 | 왜 비어 있나 | 이미 있는 놈 | 1인 난이도 | 판정 |
|---|---|---|---|---|---|
| A | **카탈로그 "채우기"** — 문서·오너십 자동 생성/유지 | 실패 원인 조사에서 가장 일관된 통증. 세우는 게 아니라 **채우는 게** 안 된다 | Atlan·Coalesce·Secoda 의 기능 일부 (제품 아님) | 中 | ★ 유력 |
| B | **한국 금융권 규제 수직** — 마이데이터 2.0·신용정보업감독규정·망분리 | 글로벌 SaaS 가 구조적으로 못 들어옴(온프레·심사). CEO 도메인과 겹침 | 삼성SDS·국내 SI (솔루션 아님) | 中上 | ★ 유력 |
| C | **에이전트 질의 감사·증거** — 어떤 에이전트가 어떤 메타데이터로 뭘 물었나 | 모두가 MCP 서버는 붙였는데 **그 뒤 기록**은 아무도 안 판다 | 확인된 전용 제품 없음 (미검증) | 中 | ○ 조사 더 |
| D | **비-테이블 자산** — API·큐·토픽·시트·Notion | 전통 카탈로그가 테이블 중심 | **Marmot 이 25+ 플러그인으로 이미 침범** | 下 | △ 좁아짐 |
| E | **중립 비교·평가 미디어** | SERP 를 벤더가 장악 (§3 주석) | dqlabs·thedatagovernor 등 다수 | 下 | ✕ 제품 아님 |
| F | **경량 단일 바이너리 셀프호스트** | OSS 카탈로그는 Kafka+ES 요구, 0.5~1 FTE 유지비 | **Marmot 이 MIT 로 이미 함** (단일 바이너리 + Postgres) | 下 | ✕ 닫힘 |

### A. 카탈로그를 *채우는* 문제 — 가장 근거가 단단한 틈
여러 출처가 같은 말을 한다: *"카탈로그의 가장 어려운 부분은 세우는 게 아니라 채우는 것"*, *"사람들은 게으른 게 아니라
무엇이 '충분히 좋은지', 누가 먼저 써야 하는지 몰라서 망설인다"*, *"정기 갱신이 없으면 낡고 결국 안 쓰인다"*.
→ **카탈로그가 아니라 카탈로그의 콘텐츠를 지속 생산·감쇠 관리하는 한 기능 제품.** 기존 카탈로그(DataHub/OpenMetadata/Unity)에
**얹는** 형태면 유통이 열린다 — 카탈로그 회사와 싸우지 않고 그들의 실패를 메운다.
**PivoxQuant 의 "기록 → 거울" 루프와 구조가 같다**: 자산은 도구가 아니라 축적된 기록, 그리고 그 기록의 감쇠를 막는 마찰.

### B. 한국 금융권 규제 수직
마이데이터 2.0 후속으로 신용정보업감독규정이 개정됐고, 관리적·물리적·기술적 보안 준수 + 기능 적합성 심사 + 보안 취약점 점검이
**의무화**됐다(금융위). 이런 요건은 글로벌 SaaS 카탈로그가 못 맞춘다 — 그게 방벽이다.
CEO 가 자본시장법·PIPA·신용정보법을 이미 읽어 온 도메인이라 **진입 비용이 남들보다 싸다.**
단, **2026 기준 카탈로그 관련 신규 감독규정은 검색으로 확인 못 했다** — 이 가정 위에 제품을 세우기 전 1차 확인 필수(§7).

### C. 에이전트 질의 감사
벤더 인용으로 *"MCP 에만 의존하는 agentic analytics 프로젝트의 60% 가 2028 까지 실패한다 — MCP 는 컨텍스트를 **옮기는**
프로토콜이지 **만드는** 게 아니다"* 가 돈다(원출처 미확인, §7). 이게 사실이든 마케팅이든, **에이전트가 데이터를 만진 흔적**을
남기라는 요구는 규제 산업에서 반드시 온다. 지금은 아무도 전용 제품으로 안 판다(**미검증 — 조사 부족**).

---

## 5. 추천 — 2개로 좁히고, 각각 죽이는 질문 하나

| | 추천 1: **A + C** (에이전트 시대의 카탈로그 콘텐츠 레이어) | 추천 2: **B** (한국 금융 수직) |
|---|---|---|
| 포지션 | 카탈로그를 **대체하지 않고 채운다.** DataHub/OpenMetadata/Unity 위에 얹는다 | 국내 금융사 온프레 메타데이터 + 규제 증빙 |
| 왜 1인 가능 | 통합 1개(dbt 또는 Postgres)로 시작 가능, 인프라 요구 낮음 | 고객 수가 적어 영업이 1인 범위, 도메인 이미 보유 |
| 첫 검증 (코드 짜기 전) | OSS 카탈로그 쓰는 팀 10곳에 *"카탈로그에 문서 채워져 있나? 마지막 갱신 언제?"* 만 물어라 | 국내 금융사 데이터 담당 5명에게 *"메타데이터 관리 감사 지적 받은 적 있나"* 만 물어라 |
| **죽이는 질문** | *"채워지지 않는 게 도구 탓이 아니라 조직 탓이면, 소프트웨어로는 못 고친다."* 조사 출처 다수가 **경영진 지원·조직 문제**를 실패 원인으로 든다 — 그러면 이 틈새는 제품이 아니라 컨설팅이다 | *"국내 금융사는 이걸 솔루션으로 사나, SI 로 만드나?"* SI 로 만든다면 1인 제품 회사가 설 자리가 없다 |

**공통 전제:** 둘 다 **B2B 영업 제품**이다. PivoxQuant(무료 베타·개인 유저·바이럴 없음)와는 판매 방식이 완전히 다르다.
1인 창업자가 두 게임을 동시에 하면 컨텍스트 스위칭에서 진다 — **Pivoxmap 은 PivoxQuant 의 후속이 아니라 대체여야 성립할 가능성이 높다.** 이건 시장이 아니라 CEO 가 결정할 문제다.

---

## 6. 다음 세션이 먼저 답해야 할 것 — 코드가 아니라 정의

이 조사는 **Pivoxmap 이 뭔지 모르는 상태**에서 쟀다. 아래 4개에 답하면 §4 표의 절반이 즉시 지워진다.

1. **"map" 이 뭘 뜻하나?** 데이터 계보 시각화(lineage map)? 자산 지도? 아니면 카탈로그와 무관한 지리 데이터?
2. **고객이 누구인가?** 데이터 엔지니어(개발자 주도, OSS 유통) vs 금융사 담당자(영업 주도) — 이게 제품 형태를 전부 결정한다.
3. **한국인가 글로벌인가?** 한국이면 §4-B 만 살고, 글로벌이면 §4-A/C 만 산다.
4. **오픈소스인가?** Marmot(MIT)·OpenMetadata·DataHub 가 이미 무료다. 유료 폐쇄 소스로 들어가면 **왜 무료 대신 이걸 사나**에 답해야 한다.

**데이터 권리 경고 (PivoxQuant 의 FMP §2.2.2 재발 방지):** 카탈로그 제품은 남의 데이터의 *메타데이터*를 수집·표시한다.
기업 스키마·컬럼명·샘플값은 **고객 기밀**이고, 샘플값을 서버에 올리는 순간 PIPA·신용정보법 범위에 들어온다.
아키텍처 첫 줄부터 **"샘플값은 고객 경계 밖으로 안 나간다"** 를 못 박아라 — 나중에 못 고친다.

---

## 7. 방법 · 검증 안 된 것

**WebSearch 쿼리 10건 (2026-09-11):**
`data catalog market size 2026 metadata management growth forecast` ·
`data catalog startups 2026 Atlan Secoda Select Star Castor funding` ·
`MCP server semantic layer AI agents need metadata context data catalog 2026` ·
`Iceberg REST catalog wars Unity Catalog Polaris Lakekeeper 2026 open catalog` ·
`why data catalog projects fail adoption problem shelfware complaints practitioners` ·
`Collibra Alation 2026 layoffs acquisition AI governance market consolidation` ·
`한국 데이터 카탈로그 시장 데이터 거버넌스 솔루션 2026 국내 기업` ·
`unstructured data catalog RAG AI ready metadata startup 2026 niche` ·
`"data catalog" small team startup pricing too expensive open source DataHub OpenMetadata self-hosted 2026` ·
`new data catalog startups 2026 seed funding "context layer" agent metadata launch` ·
`Marmot data catalog open source 2026 lightweight alternative developer-first` ·
`금융권 데이터 거버넌스 의무 데이터 카탈로그 메타데이터 관리 감독규정 2026 마이데이터` ·
(+ 교차확인 2건) `Atlassian acquires Secoda December 2025 announcement` · `Coalesce acquires CastorDoc 2025 data catalog acquisition announcement`

**1차 자료로 확인한 것 (2건뿐):** Coalesce→CastorDoc 인수(coalesce.io 공식 발표, 2025-03-19) · Atlassian→Secoda 인수(secoda.co 공식 블로그, 2025-12-04).

**검증 안 된 것 — 이 위에 제품을 세우기 전에 직접 재라:**
- 시장 규모 전부 (§1). 리서치밀 3.3배 편차.
- Select Star 연 $70k~$90k 가격 — 벤더 비교 블로그 인용, 공식 가격표 아님.
- "MCP 의존 agentic analytics 60% 가 2028 실패" — Cube 기사 인용, **원출처(Gartner 추정) 미확인**.
- Secoda 총 조달 $16.3M — Tracxn 스니펫.
- **§4-C 에 전용 경쟁자가 없다는 주장** — "없다"를 말할 만큼 안 쟀다. CLAUDE.md 원칙 위반 직전이라 `○ 조사 더` 로만 표시했다.
- **한국 금융권 카탈로그 관련 2026 신규 감독규정** — 검색으로 못 찾았다. `확인 불가`. 금융위·금감원 원문을 직접 읽어야 §4-B 가 성립한다.
- 국내 경쟁 솔루션 지형 — 한국어 검색 1회로는 전혀 부족하다. 사실상 **미조사**.
