# Anthropic API 호출 인벤토리 (백엔드)

**작성일**: 2026-05-28
**Wave**: v55-X2
**SoT 작성 방법**: `grep -rn "messages.create\|from anthropic\|ANTHROPIC_API_KEY" --include="*.py" services/ routes/ agent_worker/ app.py`
**제약**: grep 결과만 인용. 추측·코드 변경 X.

---

## 1. 호출 모듈 (코드 진입점)

총 **6개 모듈**이 `anthropic.Anthropic(...)` 클라이언트를 직접 인스턴스화하거나 사용한다. 사용 모델은 전부 **`claude-haiku-4-5-20251001`** (단일).

| # | 모듈 (file:line) | 클라이언트 init | 호출 패턴 | 사용 함수 수 |
|---|---|---|---|---|
| 1 | `services/ai/service.py:209-210` | `anthropic.Anthropic(api_key=…, timeout=20.0, max_retries=1)` | `self.client.messages.create()` × 6 + `messages.stream()` × 1 | 7 |
| 2 | `services/ai/models.py:53-54` | `anthropic.Anthropic(api_key=…, timeout=20.0, max_retries=1)` (lazy `_get_client()`) | `_claude_json()` 헬퍼 → `client.messages.create()` × 1 (재사용) | 3 (EarningsCallToneAnalyzer, AISectorRotation, AIRiskSummary) |
| 3 | `services/data/fetcher.py:477-486` | per-call `anthropic.Anthropic(...)` (재사용 X) | `_score_news_with_ai()` 내부 1회 | 1 |
| 4 | `services/agents/journal_companion.py:187-197` | lazy `Anthropic()` (env-only) | `_invoke_llm()` 1회 | 1 (AGENT_ENABLED=1일 때만) |
| 5 | `services/support/chatbot.py:455` | `services.container.ai.client` 재사용 (모듈 1과 동일 인스턴스) | `ai.client.messages.create()` × 1 | 1 (SUPPORT_CHAT_LLM_ENABLED=1일 때만) |
| 6 | `agent_worker/claude_client.py:24,62` | `Anthropic(api_key=…)` lazy | `client.messages.create()` × 1 (헬퍼) | 3 시나리오 (weekly_report / evening_reflection / morning_briefing) |

또한 **artifact services 7개**가 모듈 1 (`services/ai/service.py`)의 `AIService().client`를 재사용해 `messages.create()`를 직접 호출한다 (모듈 1 카운트와 별개로 명시):

| Artifact service | line | max_tokens | 모델 |
|---|---|---|---|
| `weekly_memo_service.py` | 1346 | 900 | MODEL (Haiku) |
| `earnings_prebrief_service.py` | 514 | 400 | `claude-haiku-4-5` (literal) |
| `dd_checklist_service.py` | 219 | 400 | `ai_service.MODEL` |
| `quarterly_self_report_service.py` | 458, 549 | 200 / 500 | `ai_service.MODEL` |
| `risk_board_service.py` | 605 | 400 | `ai_service.MODEL` |
| `self_audit_service.py` | 336 | 400 | `ai_service.MODEL` |
| `year_end_letter_service.py` | 437 | 600 | `ai_service.MODEL` |

---

## 2. 호출처 분류 (실시간 vs 사전생성)

### 2-A. 실시간 호출 (user 요청 시 즉시) — `routes/ai.py`

전부 `@api_auth` + `@require_tier("pro")` (earnings-tone 일부 제외) + `@ai_rate_limit`. user가 버튼 클릭하면 즉시 호출.

| Endpoint | routes/ai.py line | 호출 함수 | max_tokens (output) | 사전생성 가능? |
|---|---|---|---|---|
| `POST /api/ai/swot` | 99 | `ai.generate_swot()` | 4000 | △ 부분 (자기보유 종목은 가능, 임의 종목은 X) |
| `POST /api/ai/competitor` | 157 | `ai.generate_competitor_analysis()` | 4000 | △ 부분 |
| `POST /api/ai/sector-trend` | 203 | `ai.generate_sector_trend()` | 4000 | ○ (11 섹터 nightly 사전생성 가능) |
| `POST /api/ai/chat` (SSE stream) | 290 | `ai.chat_stream()` | 4000 (stream) | ✗ 대화 인터랙티브 |
| `POST /api/ai/commentary` | 321 | `ai.generate_commentary()` | 4000 | △ 부분 |
| `POST /api/ai/morning-summary` | 347 | `ai.generate_morning_summary()` | 4000 | ○ (시장 단위 1회/일) |
| `POST /api/ai/coaching` | 388 | `ai.generate_coaching()` | 4000 | ○ (user별 1회/일 또는 1회/주) |
| `POST /api/ai/earnings-tone` | 489 | `EarningsCallToneAnalyzer.analyze()` | 1500 (JSON) | ○ (실적발표 후 1회) — 24h cache 이미 존재 |
| `GET  /api/ai/earnings-tone/<ticker>` | 507, 571 | 동상 | 1500 | ○ 동상 |
| `GET  /api/ai/sector-regime` | 595 | `AISectorRotation.analyze()` | 1500 | ○ 6h cache 이미 존재. nightly로 충분 |
| `POST /api/ai/risk-summary` | 699 | `AIRiskSummary.generate()` | 1500 | ○ user별 1회/일 |
| `POST /api/support/chat` (support chatbot) | (별도 route) | `_call_model()` | 600 (기본) | ✗ 인터랙티브, FAQ → 모델은 fallback |

또한 다음은 **간접 실시간** (다른 path에서 호출):

| 호출처 | 트리거 | 사전생성 가능? |
|---|---|---|
| `fetcher.py:_score_news_with_ai` | `score_news_sentiment(ticker)` — landing/detail 페이지 진입 시 | △ 인기 종목 top-N만 사전 가능. 10min in-memory cache 존재 |
| `journal_companion._invoke_llm` | `/api/agent/query` (Premium Plus) | ✗ 인터랙티브, AGENT_ENABLED=0 default |

### 2-B. 배치/스케줄 호출 (cron / in-process scheduler)

**전제**: app.py에 RUN_SCHEDULER=1일 때 26개 APScheduler 잡 등록 (`services/scheduler/cron_jobs.py` + app.py:1374-1842 내장 스케줄러). 다음은 artifact run_* 호출 (LLM 포함분만):

| Artifact run_* | 호출 위치 | 빈도 | LLM 호출 발생 (1 user당) | 사전생성 가능? |
|---|---|---|---|---|
| `WeeklyMemoService.run_weekly()` | app.py:1379 | 주 1회 (일요일 09:00 KST per scripts/README.md) | 1 (Haiku, max 900) | ○ 최우선 후보 |
| `MonthlyBragService.run_monthly()` | app.py:1397 | 월 1회 | 0 (LLM 호출 없음 — grep 결과) | n/a |
| `BragCardService.run_monthly()` | app.py:1416 | 월 1회 | 0 | n/a |
| `BurnRateService.run_monthly()` | app.py:1535 | 월 1회 | 0 | n/a |
| `CreditRatingService.run_monthly()` | app.py:1551 | 월 1회 | 0 | n/a |
| `DividendIncomeService.run_monthly()` | app.py:1569 | 월 1회 | 0 | n/a |
| `MonthlyFinanceService.run_monthly()` | app.py:1588 | 월 1회 | 0 | n/a |
| `RiskBoardService.run_monthly()` | app.py:1606 | 월 1회 | 1 (Haiku, max 400) per user | ○ |
| `InsiderMirrorService.run_weekly()` | app.py:1685 | 주 1회 | 0 | n/a |
| `EarningsPrebriefService.run_scan_digest()` | app.py:1797 | 15분마다 (스캔) | 1 (Haiku, max 400) per ticker | △ 실적 임박 ticker만 |
| (annual) `YearEndLetterService.generate_for_user()` | 별도 트리거 | 연 1회 | 1 (Haiku, max 600) | ○ |
| (quarterly) `QuarterlySelfReportService.generate_for_user()` | 별도 트리거 | 분기 1회 | 1-N (Haiku, max 200 thesis-당 + 1 summary max 500) | ○ |
| `SelfAuditService.generate_for_user()` | trigger route | 사용자 트리거 | 1 (Haiku, max 400) | △ |
| `DDChecklistService.generate_for_user()` | 별도 트리거 | 사용자 트리거 | 1 (Haiku, max 400) | △ |

### 2-C. agent_worker 시나리오 (별도 worker process)

`agent_worker/scenarios/*` 3개:
- `morning_briefing.py` — 매일 아침
- `evening_reflection.py` — 매일 저녁
- `weekly_report.py` — 주 1회

전부 `agent_worker.claude_client.invoke_agent()` 경유 → `client.messages.create()` 1회. **사전생성 후보 (○)**.

---

## 3. LLM 없는 artifact (LLM 호출 0회 — grep 확인)

`services/artifacts/*_service.py` 중 `messages.create` grep 0회 매칭:

- `brag_card_service.py`
- `burn_rate_service.py`
- `capital_allocation_service.py`
- `credit_rating_service.py`
- `dividend_income_service.py`
- `insider_mirror_service.py`
- `kpi_dashboard_service.py`
- `monthly_brag_service.py`
- `monthly_finance_service.py`
- `portfolio_segment_service.py`
- `pre_trade_checklist_service.py`
- `sp500_backtest_service.py`

12개 artifact는 **순수 데이터 계산** — Anthropic API 호출 0. Max 라우팅 마이그레이션 대상 아님. (CC Max도 토큰 안 씀.)

---

## 4. 토큰 사용 추정 (grep 기반)

**Output max_tokens**는 코드에서 직접 추출:

| 호출처 | output max | 입력 prompt 추정 | 비고 |
|---|---|---|---|
| `ai.service` swot/commentary/coaching/competitor/sector_trend/morning_summary | 4000 | ~500-3000 (analysis_data context) | 가장 무거움 |
| `ai.service` chat_stream | 4000 | history 최근 10턴 + context | 스트리밍 |
| `ai.models` _claude_json (earnings_tone) | 1500 | transcript 최대 30000 chars (~7500 tokens) | input 비용 큼 |
| `ai.models` _claude_json (sector_regime) | 1500 | ~200 chars | 가벼움 |
| `ai.models` _claude_json (risk_summary) | 1500 | portfolio metrics ~500-1000 chars | 가벼움 |
| `data.fetcher` _score_news_with_ai | 300 | headlines 8개 × ~100 chars | 가벼움 |
| `agents.journal_companion` _invoke_llm | 800 | ctx payload + persona prompt | 중간 |
| `support.chatbot` _call_model | 600 | KB(~2000 chars) + history + message | 중간 |
| `weekly_memo` _generate_ai_v3_block | 900 | data dump ~1500 chars | 중간 |
| `earnings_prebrief` (질문 생성) | 400 | ~500 chars | 가벼움 |
| `dd_checklist` | 400 | ticker list | 가벼움 |
| `quarterly_self_report` (thesis check × N) | 200 | per-thesis | N에 비례 |
| `quarterly_self_report` (summary) | 500 | 분기 요약 input | 중간 |
| `risk_board` | 400 | seed text | 가벼움 |
| `self_audit` | 400 | ctx ~1000 chars | 가벼움 |
| `year_end_letter` | 600 | 거래 요약 ~2000 chars | 중간 |

**호출 총량 추정 (출시 후 100 user / 일 가정)**:
- 실시간 `routes/ai.py` (Pro tier): SWOT/competitor/sector_trend/commentary/morning_summary/coaching/risk_summary/chat — 한 user당 추정 5-20회/일 (탐색 행동에 따라 가변). 100 user × 10회 = **1,000 calls/day**, 평균 input 1k + output 2k = **3M tokens/day**.
- artifact cron blast (LLM 포함 5개: weekly_memo, earnings_prebrief, risk_board, year_end, quarterly, self_audit, dd_checklist): 100 user × 빈도 weekly(1)+monthly(1)+annual(1)+quarterly(1) → **평균 ~5 calls/user/week → ~70 calls/day**.
- fetcher news scoring: ticker 진입마다 (10min cache 있음). 추정 1k calls/day.
- agent_worker 3 scenarios × 100 user × 빈도 → **~300 calls/day**.

→ **현 trajectory 합산 ~2,400 calls/day**. Haiku $1/1M input + $5/1M output 기준 **월 ~$30-50** 추정. 정확 SoT는 `anthropic_usage_log` 테이블 (migration 042) — prod에서 _do_migrations 누락 가능성 (`feedback_prod_schema_selfheal`).

---

## 5. fallback 동작 (key 미설정 시)

코드 전체에서 다음 패턴 일관 적용 — `ANTHROPIC_API_KEY` 미설정 또는 호출 실패 시 **soft fallback** (raise X):

| 모듈 | 미설정 시 동작 |
|---|---|
| `ai.service` | `self.available = False` → 모든 generate_* 가 `None` 반환 → routes/ai.py가 503/404 응답 |
| `ai.models` | `_get_client()` 가 `None` → `_claude_json` `None` → 호출처에서 500 또는 `{"available": false}` |
| `data.fetcher._score_news_with_ai` | `None` 반환 → keyword-based `_score_news_keywords` fallback |
| `journal_companion._invoke_llm` | `""` 반환 → gate가 T5 refusal로 변환 |
| `support.chatbot._call_model` | `SUPPORT_CHAT_LLM_ENABLED` 미설정 → FAQ만 사용 (이미 default OFF) |
| `weekly_memo._generate_ai_v3_block` | `_ai_v3_fallback()` placeholder 사용 (memo 자체는 발송됨) |
| `earnings_prebrief`/`dd_checklist`/`risk_board`/`self_audit` 등 | placeholder 또는 빈 응답 — artifact PDF/email은 그래도 발송 |
| `agent_worker.claude_client` | `RuntimeError("ANTHROPIC_API_KEY not set")` raise — worker가 죽으면 cron이 그날 잡 실패로 표시 |

**결론**: `ANTHROPIC_API_KEY=""`로 두고 출시해도 시스템은 안 죽음. 단 user-facing 품질이 크게 떨어짐 (SWOT/coaching/chat 등이 503).

---

## 6. 사전생성 vs 실시간 매트릭스 요약

| 분류 | 호출처 | 패턴 (Phase 4 참조) |
|---|---|---|
| **즉시 사전생성 가능 (실시간성 불요)** | sector-regime / morning-summary / weekly_memo / risk_board / year_end / quarterly_self / agent_worker 3 시나리오 | **Pattern A** (CC Max 사전 캐시) |
| **부분 사전생성 (top-N 종목)** | swot / commentary / competitor / sector-trend / earnings-tone / news_scoring | **Pattern A** (인기 종목 top-100 nightly precompute) |
| **실시간 필수 (interactive)** | chat / support_chatbot / journal_companion / risk-summary (user-specific) / coaching (user-specific) | **Pattern C** (API direct) 또는 **Pattern B** (queue, latency 허용 시) |
| **LLM 호출 없음** | brag_card / burn_rate / monthly_finance 등 12개 artifact | 라우팅 대상 아님 |

다음 문서 (`MAX_ROUTING_PLAN.md`)에 Pattern A/B/C 상세.
