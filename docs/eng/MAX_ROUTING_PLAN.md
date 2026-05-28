# CC Max 라우팅 + Anthropic API 사용 최소화 플랜

**작성일**: 2026-05-28
**Wave**: v55-X2
**전제**:
- `feedback_no_extra_cost` — 추가 결제/구독 0원 유지
- Max 플랜 토큰만 사용 (CC scheduled-tasks)
- Anthropic API direct는 베타 출시 직후까지 0원 유지 (잔액 unfunded 상태 가정 — `support/chatbot.py:36-40` 주석 확인)
- 코드 변경 X (이 wave는 spec만)
- SoT: `ANTHROPIC_CALL_INVENTORY.md`

---

## 1. 3개 라우팅 패턴

### Pattern A — 사전생성 + 캐시 (CC Max 라우팅)

**개념**: 백엔드는 Anthropic API를 부르지 않고, 캐시에서 사전생성된 결과만 read.

```
[CC scheduled-task 03:00 KST]
  ↓ run: python scripts/precompute/<artifact>.py --target-date <tomorrow>
[CC Max session]
  ↓ (Max 토큰만 소비)
  ↓ LLM 호출 결과 → JSON/HTML
[저장 위치]
  state/precomputed/<artifact>/<YYYY-MM-DD>/<user_id_or_ticker>.json
  또는 DB 테이블 (e.g. artifacts 테이블에 직접 INSERT)
[백엔드 read path]
  routes/ai.py 또는 services/artifacts/*가 캐시 read만 → API 0
```

**전제 조건**:
- CC scheduled-task가 repo cwd `/Users/seanbae/dev/pivoxquant`에서 실행되어야 함 (`project_agent_inventory` cwd dormancy 룰)
- CC Max 윈도우 5시간 한계 — wave당 처리량 캡 필요 (사전생성을 batch 분할)
- CEO 노트북이 켜져 있어야 함 (Max는 로컬). 노트북 꺼지면 cron miss → 다음 wave에 backfill

**적용 대상** (Inventory §6 "즉시 사전생성 가능"):
- sector_regime (1회/일, 글로벌 단일 결과)
- morning_summary (1회/일, 시장 단위)
- weekly_memo (1회/주, user별)
- risk_board (1회/월, user별)
- year_end_letter (1회/연, user별)
- quarterly_self_report (1회/분기, user별)
- agent_worker 3 시나리오 (morning_briefing / evening_reflection / weekly_report)

**부분 사전생성** (top-N 종목만):
- swot / commentary / competitor / sector-trend / earnings_tone / news_scoring → 인기 종목 top-100 nightly precompute. Long-tail은 Pattern C.

**장점**: Anthropic API 0원. Max 토큰만 사용.
**단점**:
- 노트북 의존 (Mac 꺼지면 miss)
- user별 N×artifact 폭증 시 Max 5h 윈도우 초과
- 사전생성 누락 종목 cold-cache hit → Pattern C fallback 필요

---

### Pattern B — Async queue (CC Max worker polling)

**개념**: 백엔드는 LLM 작업을 큐(DB 테이블)에 push. CC scheduled-task (예: 15분마다)가 큐 polling → 처리 → 결과 백엔드에 write back.

```
[User request]
  → POST /api/ai/swot
  → 백엔드: 캐시 miss → llm_job_queue 테이블 INSERT (status='pending')
  → 즉시 202 Accepted 응답 + job_id
[Frontend]
  → SWR polling 또는 SSE listen on /api/ai/job/<job_id>/status
[CC scheduled-task every 15min]
  → SELECT * FROM llm_job_queue WHERE status='pending' LIMIT 50
  → Max 세션에서 LLM 호출
  → UPDATE llm_job_queue SET result=…, status='done'
[Frontend]
  → status=done → 결과 render
```

**전제 조건**:
- `llm_job_queue` 테이블 추가 (스키마: id / user_id / job_type / payload jsonb / status / result jsonb / created_at / processed_at)
- CC scheduled-task 빈도 ≥ user wait 인내 (15min latency)
- Frontend가 비동기 결과 대기 UI 지원

**적용 대상**:
- 실시간성 필요 X, latency 5-30분 허용되는 호출:
  - SWOT/commentary/competitor (사용자가 "분석 중..." 메시지 보고 기다림)
  - earnings_tone (24h cache 있으므로 첫 user만 wait)

**장점**: Max 토큰만 사용. 사전생성보다 유연 (사용자 실제 요청한 것만).
**단점**:
- latency 5-30분 (실시간 X)
- 큐 backlog 누적 시 user wait 늘어남
- 노트북 꺼지면 큐 stuck → Pattern C fallback 또는 SLA 위반 알림

---

### Pattern C — Anthropic API direct (최소 사용)

**개념**: 실시간 필수 호출만 Anthropic API direct. 베타 출시 후 API balance 충전 시 활성.

**적용 대상**:
- `chat_stream` (SSE 인터랙티브, 토큰 stream 필수)
- `support_chatbot` (FAQ miss 시 fallback, 대화)
- `journal_companion` (AGENT_ENABLED=1 시. 현재 0)
- `risk_summary` (user portfolio 즉시 분석 — Pattern B로도 가능하나 latency 민감)
- `coaching` (Pattern A 가능하나 portfolio 변동성 큰 user 즉시성 요구)

**현 상태**: `ANTHROPIC_API_KEY` 미설정 또는 잔액 0 → 코드 fallback (Inventory §5):
- 모든 generate_* → None
- chat → "AI 기능이 비활성화" 메시지
- support → FAQ만 (LLM disabled)
- coaching → 503

**장점**: 실시간성 보존, 사용자 경험 정상.
**단점**: 비용 발생 (월 $30-50 추정 Inventory §4). `feedback_no_extra_cost` 위반 가능성.

→ **결정 보류**: 베타 출시 후 가입자 trajectory 보고 결정.

---

## 2. 사전생성 가능 매트릭스 (Inventory §6 재정리)

| 호출처 | Pattern | 우선순위 | 노트 |
|---|---|---|---|
| sector_regime | **A** | P0 | nightly 1회. 6h cache 이미 존재 → 캐시 채우기만 |
| morning_summary | **A** | P0 | 시장 단위 1회/일. user-agnostic |
| weekly_memo (`run_weekly`) | **A** | P0 | 토요일 03:00에 일요일분 사전생성. user별 N |
| risk_board (`run_monthly`) | **A** | P1 | 월 1회. 월말 03:00 사전생성 |
| year_end_letter | **A** | P2 | 연 1회. 12월 30일 사전생성 |
| quarterly_self_report | **A** | P1 | 분기말 03:00 사전생성 |
| self_audit | **A** | P1 | user trigger 가능하므로 부분 (자주 사용 user는 nightly) |
| dd_checklist | **A** | P1 | weekly batch (홀딩 ticker 일괄) |
| earnings_prebrief (run_scan_digest) | **A** | P0 | 이미 15min cron. 호출당 1 LLM. 사전스캔만 CC Max로 이전 |
| agent_worker 3 시나리오 | **A** | P0 | 이미 worker 분리 — invoke_agent 경로만 CC Max routing |
| sector-trend (11 sectors) | **A** | P1 | 11 섹터 nightly. user 요청은 캐시 read |
| earnings_tone | **A** (top-N) + **C** (long-tail) | P1 | 24h cache. 인기 ticker top-100만 precompute |
| swot/commentary/competitor | **A** (top-N) + **B** (long-tail) | P2 | 모든 ticker precompute 불가능 → top-N + B 큐 |
| news_scoring (`_score_news_with_ai`) | **A** (top-N) + **C** | P2 | 10min cache. 인기 ticker 사전. 그 외 keyword fallback (이미 코드에 있음) |
| **chat_stream** | **C** | — | 인터랙티브 (사전생성/큐 불가) |
| **support_chatbot** (FAQ miss) | **C** | — | 인터랙티브 |
| **journal_companion** | **C** | — | AGENT_ENABLED=0 (현재 dormant) |
| **risk_summary** (user-specific) | **B** 또는 **C** | — | latency 30s 허용되면 B |
| **coaching** (user-specific) | **A** (nightly) 또는 **B** | — | A로 충분할 가능성. UX 결정 필요 |

---

## 3. Phase 마이그레이션 플랜 (코드 변경 spec만 — 실제 구현은 v55-X4)

### Phase 1 — sector_regime + morning_summary (단순 user-agnostic) — 추정 4h

**변경 범위**:
- 신규 `scripts/precompute/sector_regime.py` — CC Max session에서 `AISectorRotation.analyze()` 호출 → `state/precomputed/sector_regime/<YYYY-MM-DD>.json` 저장
- 신규 `scripts/precompute/morning_summary.py` — 동상
- `services/ai/models.py:AISectorRotation.analyze()` — `_get_cache()` 앞에 file cache check 추가 (precomputed 파일이 있으면 그것 read, 없으면 기존 in-memory cache, 그것도 없으면 API call)
- `services/ai/service.py:generate_morning_summary()` — 동상
- CC scheduled-task 등록: 매일 03:00 KST, `python scripts/precompute/sector_regime.py && python scripts/precompute/morning_summary.py`

**검증**:
- pytest 추가: precompute output JSON schema 검증
- 통합: `ANTHROPIC_API_KEY=""` 환경에서 routes/ai.py 응답이 precomputed 파일에서 와야 함

### Phase 2 — weekly_memo / risk_board / quarterly_self / year_end / agent_worker 시나리오 — 추정 12h

**변경 범위**:
- 각 service의 `run_weekly()/run_monthly()` 내부에서 Anthropic 호출 직전, env `MAX_PRECOMPUTED_DIR` 체크 → 파일 있으면 read, 없으면 fallback
- 신규 `scripts/precompute/weekly_memo_all_users.py` — 모든 active user 순회, `WeeklyMemoService().generate_for_user(uid, target_date=...)` 결과를 파일로 dump
- 동일 패턴 5개
- CC scheduled-task: 토요일 03:00 (일요일분), 매월 말일 03:00 (월간), 분기말, 연말

**Max 5h 윈도우 분할**:
- 100 user × weekly_memo = ~100 LLM calls × 평균 5s = 500s (8min) → 단일 wave OK
- 1000 user → 5000s = 83min → 단일 wave 위험 → batch 분할 (300/wave)

### Phase 3 — top-N 종목 사전생성 (swot/commentary/sector-trend/earnings_tone) — 추정 16h

**변경 범위**:
- 신규 `services/precompute/top_tickers.py` — DB에서 daily volume + user holdings top-100 산정
- 신규 `scripts/precompute/swot_top_100.py` 등
- `services/ai/service.py:generate_swot()` 등 — file cache check 우선
- CC scheduled-task: 매일 02:00 KST

### Phase 4 — Pattern B 큐 (long-tail swot/commentary) — 추정 16h

**변경 범위**:
- 신규 alembic migration: `llm_job_queue` 테이블
- 신규 `routes/ai.py` 비동기 분기: 캐시 miss → 큐 INSERT + 202 응답 + job_id
- 신규 `GET /api/ai/job/<job_id>` polling endpoint
- 신규 `scripts/llm_queue_worker.py` — CC scheduled-task가 15min마다 실행
- Frontend `useSWR` polling 또는 SSE listener
- 결정 필요: latency UX 수용 가능한지 (CEO 결정 보류)

### Phase 5 — Pattern C 최소화 (실시간 필수 호출 잔류) — 출시 후 결정

**변경 범위** (현 시점 코드 변경 X):
- chat / support / journal_companion / coaching → Anthropic API direct 유지
- `ANTHROPIC_API_KEY` 충전 여부는 베타 trajectory 기반 CEO 결정
- 만약 충전 미진행: 출시 시 chat/coaching feature 비활성 표기 (소프트 비활성, 코드 fallback 이미 있음)

---

## 4. 마이그레이션 시 절약 추정

Inventory §4 trajectory 기준 **~2,400 calls/day → 월 $30-50**.

| Phase 완료 시 | 잔여 Anthropic API 호출 | 절약 |
|---|---|---|
| Phase 1 | ~2,300/day (sector_regime + morning_summary 제외 — 원래 cache 잘 작동 → 절약 미미, but 안정성↑) | ~$1/월 |
| Phase 2 | ~1,900/day (artifact cron LLM 7개 제거) | ~$5/월 |
| Phase 3 | ~700/day (top-100 ticker precompute, news_scoring 등) | ~$30/월 |
| Phase 4 | ~200/day (long-tail 큐화. chat/support만 잔류) | ~$45/월 |
| Phase 5 | (chat/support 정책 결정) | — |

**Phase 1-3 완료만으로 월 $36/$50 절약 (~72%)**. Phase 4는 latency UX 결정 필요.

---

## 5. 즉시 가능 (CEO 결정 X) vs 보류

### 즉시 가능 (코드 spec만 — v55-X4 구현)
- Phase 1 (sector_regime + morning_summary precompute)
- Phase 2 (weekly_memo / risk_board / year_end / quarterly_self / self_audit / dd_checklist / agent_worker 3 시나리오 precompute)
- Phase 3 (top-N swot/commentary/sector_trend/earnings_tone/news_scoring precompute)

→ 모두 file-cache layer 추가 + CC scheduled-task wiring. 백엔드는 cache miss 시 기존 코드 path 그대로 (방어).

### 보류 (CEO/product 결정 필요)
- Phase 4 (LLM job queue): latency 5-15min UX 수용 가능 여부. SWOT/commentary는 가능하나 risk_summary/coaching은 즉시성 요구 가능.
- Phase 5 (chat/support API direct 활성): Anthropic API balance 충전 시점. `feedback_no_extra_cost` 와 충돌 가능 (월 $1-5 잔여).
- AGENT_ENABLED=1 활성 (journal_companion): 변호사 Q-S 시리즈 잔류 (`legal_question_queue`).

---

## 6. 리스크 + 회귀 게이트

| 리스크 | 대응 |
|---|---|
| CC Max 윈도우 5h 초과 (1000+ user) | Phase 2 구현 시 batch 분할 (300 user/wave). carry-over 파일에 진척 기록 |
| 노트북 꺼져 precompute miss | 매일 06:00 KST 검증 cron: precomputed 디렉토리 mtime 확인 → 24h 이상 stale → Slack alert |
| precomputed JSON schema 회귀 | pytest fixture에 모든 precompute output schema 검증 |
| Anthropic API direct fallback이 silently 503 | routes/ai.py 에 last_error 이미 surface (`ai.service.py:205`). frontend가 사용자에게 "AI 기능 일시 비활성" 표기 |
| `feedback_thorough_fixes` — 한 곳 캐시 추가 시 비슷한 다른 호출처 누락 | Phase별 PR에서 grep으로 동일 모듈의 모든 `messages.create` 호출 수 변화 확인 (`tests/test_anthropic_call_count.py` 신규 — 회귀 게이트) |
| `feedback_no_busywork` — LLM 호출 0회 12 artifact는 마이그레이션 대상 아님 | Inventory §3 명시 — 건들지 않음 |

---

## 7. 결정 carry-over (CEO 검토 필요)

1. **Phase 4 큐 latency UX**: SWOT 분석 5-15min wait 수용? (답변에 따라 Phase 4 진행/보류)
2. **Phase 5 Anthropic API balance 충전**: 출시 후 어느 단계에서? (chat / support_chatbot LLM fallback 활성 시점)
3. **AGENT_ENABLED**: journal_companion 출시 시점 — 변호사 Q-S4 (영문 §49 비대칭) 답변 후 결정.
4. **노트북 의존 리스크**: 만약 CEO가 출시 후 외출/여행 빈도 ↑ → CC Max precompute miss 빈번. 그 시점에 GitHub Actions free tier로 일부 이전 검토 (`feedback_no_extra_cost` 호환 — Actions free tier 2,000 min/월).

위 4개는 carry-over 만, 본 wave에서 결정 X.
