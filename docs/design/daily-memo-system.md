# Daily Morning Brief System — Design Document

**Status**: As-built audit + delta proposal (no code changes in this doc).
**Last updated**: 2026-04-27
**Owner**: 백엔드개발부
**Scope**: 자동 생성 시스템이 매일 아침 `TodayMemoHero` 에 새 메모를 공급하는 백엔드 파이프라인.

---

## 1. 시스템 개요

매일 KST 06:00 에 사용자별 개인화 Morning Brief 를 자동 발행하는 백엔드 파이프라인 ("User as CFO" 컨셉, Memory `product_concept_cfo.md`). Claude Haiku 가 자유 텍스트 한 줄(`insight`)만 생성, 시장/포지션/이벤트 섹션은 결정론적 조립. 결과는 `MorningBrief` 에 (user_id, brief_date) UNIQUE 로 immutable 저장. 프론트는 기존 `GET /api/brief/today` 호출.

**핵심 목표**: (1) 매일 새 메모 idempotent 제공, (2) 자본시장법 §6 회피 (관측 톤, BUY/SELL/HOLD 금지), (3) AI 실패 시 rule-based fallback 으로 always-on, (4) Pro+ 는 HTML 이메일 추가.

**Out of scope**: 다중 시간대, 실시간 스트리밍, 다국어, 챗봇 follow-up.

**현재 상태**: §3–§7 이미 구현 (routes/morning_brief.py, services/morning_brief_service.py, models/morning_brief.py, app.py:974). 본 문서는 (a) as-built 박제 + (b) §5/§9/§10 delta 제안.

---

## 2. 아키텍처

```
┌────────────────────────────────────────────────────────────────────────┐
│  APScheduler BackgroundScheduler (single Flask instance, opt-in)        │
│  Trigger: cron hour=6 minute=0  (timezone defaults to server local)     │
│           ↓                                                             │
│  app._scheduled_morning_briefs()                                        │
│           ↓                                                             │
│  services.morning_brief_service.run_daily_briefs()                      │
│           ↓                                                             │
│  for user in User.query(onboarding_completed=True):                     │
│      if !has_positions and !has_watchlist:  → skip                      │
│      generate_brief(user):                                              │
│          ├─ fetcher.get_enhanced_macro()      → market_summary          │
│          ├─ Position.query(user_id) + SignalCache → portfolio_changes   │
│          ├─ fmp_service.get_earnings_calendar(ticker, days_ahead=2)     │
│          │                                    → events                  │
│          ├─ ai_service.generate_brief_insight(...)  ← Claude Haiku      │
│          │   ├─ budget guard (AI_DAILY_LIMIT=100)                       │
│          │   └─ _is_compliant() regex filter (drop on fail)             │
│          ├─ kpi_dashboard_service.compute_kpis_for_user()               │
│          ├─ scrub_signal(content)            ← legal_filter             │
│          └─ DB upsert (UniqueConstraint user_id+brief_date)             │
│      if user.tier in {pro,premium,elite}:                               │
│          render_brief_email() → send_brief_email() (SendGrid|SMTP)      │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  Frontend (TodayMemoHero, hooks.useMorningBrief)                        │
│           ↓ GET /api/brief/today  (Cookie session)                      │
│  routes/morning_brief.py @api_auth @legal_scrub_response                │
│           ↓                                                             │
│  MorningBrief.query.filter_by(user_id=current_user.id, brief_date=today)│
│           ↓                                                             │
│  { ok, available, date, created_at, brief: {...content...} }            │
└────────────────────────────────────────────────────────────────────────┘
```

**Idempotency**: `(user_id, brief_date)` UNIQUE. 재실행 시 upsert. 같은 날 cron 이 두 번 트리거되어도 DB 행 1개만 유지.

**Deduplication of cost**: Claude Haiku 호출은 user 당 하루 1회 (insight 만). 그 외 데이터(매크로/포지션/이벤트/KPI)는 캐시 또는 free DB read.

---

## 3. DB 모델

**기존 (as-built — `models/morning_brief.py`)**

```python
class MorningBrief(db.Model):
    __tablename__ = "morning_briefs"
    id         = Integer  PK
    user_id    = Integer  FK(users.id)  NOT NULL  index
    brief_date = Date                   NOT NULL  index
    content    = JSON
    created_at = DateTime               NOT NULL  default=utcnow
    __table_args__ = (UniqueConstraint("user_id", "brief_date"),)
```

`content` JSON 스키마 (services 에서 생성):
```jsonc
{
  "kpis":              { "as_of": "...", "nav": ..., ... },
  "market_summary":    { "sp500": {...}, "nasdaq": {...}, "dow": {...},
                         "kospi": {...}, "kosdaq": {...}, "vix": {...} },
  "portfolio_changes": [ { "ticker", "name", "change_pct", "direction" } ],
  "events":            [ { "ticker", "name", "event_type", "date",
                            "description", "event_time" } ],
  "insight":           "AI-generated 1-line, ≤60 chars, compliance-filtered",
  "disclaimer":        "정보 제공 목적, 투자 판단은 본인 책임",
  "generated_at":      "2026-04-27T21:00:00Z"
}
```

**Delta 제안 (선택)**: 운영 가시성을 위해 다음 컬럼 추가를 검토 (Alembic 신규 revision, NULL-허용으로 backward compatible):
- `posture` ENUM('POSITIVE','NEGATIVE','NEUTRAL') NULLABLE — 현재 컨셉 문서가 요구하는 라벨 분류. 현재 `content.insight` 한 줄로만 있고 라벨이 없음. Hero UI 에서 색상/아이콘 분기를 위해 필요.
- `status` ENUM('GENERATED','FAILED','FALLBACK') NULLABLE — fallback 사용 여부 추적.
- `source_data_hash` VARCHAR(64) NULLABLE — 입력 변화 감지용. 향후 `/generate-now` 에서 입력 동일하면 noop.

세 컬럼 모두 nullable 로 추가하여 기존 row 영향 X. Alembic revision 1개. 모델 파일에는 새로운 컬럼 추가만 하면 됨 (기존 코드 수정 X, ORM 의 nullable default 가 None 보장).

**Index**: 기존 (user_id, brief_date) UNIQUE 로 충분. archive 쿼리(`brief_date >= cutoff`)도 brief_date index 활용.

---

## 4. Claude Prompt 템플릿

호출자: `ai_service.generate_brief_insight()` (services/morning_brief_service 가 호출). 모델: Claude Haiku 4.5 (비용 우선).

**System prompt** (법무 검수 필요 — ai_service.py 인라인. 본 문서가 canon):
```
You are a CFO-style portfolio observer for PivoxQuant.
Constraints (HARD):
- Neutral observational Korean. 과거형 사실 / 현재형 상태. NEVER 미래 예측.
- 금지어: 추천, 조언, 권고, 권유, 매수, 매도, 사세요, 파세요, 사라, 팔아,
  buy, sell, recommend, advice, advise, hold.
- NEVER assert price direction ("오를 것", "내릴 것", "오른다", "내린다").
- Exactly one Korean sentence ≤ 60 chars. No markdown/quotes.
- Cannot satisfy → output literal "FALLBACK" only.
Tone: 맥킨지 메모 / 골드만삭스 리서치 데스크. NOT a chatbot. One printed line/day.
```

**User prompt** (data injection): `[date] {YYYY-MM-DD KST}`, `[market] SPX/NDX/KOSPI/VIX 가격+%`, `[portfolio] N positions, up=k_up, down=k_down, top moves`, `[events] earnings/macro 일정` → "Generate the daily observation line."

**Output**: 단일 자유 텍스트 (60자 이하). JSON 스키마 강제 X (현재 단순 텍스트가 충분; 향후 §3 의 posture 컬럼 추가 시 JSON output 모드로 전환).

**Posture extraction (§3 delta)**: AI 출력 후 후처리에서 키워드 매칭으로 posture 분류.
- POSITIVE 시그널: "상승", "회복", "강세" + portfolio up_count > down_count
- NEGATIVE 시그널: "하락", "변동성 확대", "VIX 25↑" + portfolio down_count > up_count
- 그 외 → NEUTRAL
정확도 80% 이상이면 충분 — UI 가 색상 힌트로만 사용하고, 실제 본문은 `insight` 텍스트.

**Compliance gate (post-generation, ALREADY IMPLEMENTED `_is_compliant()`)**:
1. `_FORBIDDEN_RE` 정규식 매칭 → 매칭되면 drop
2. `_is_compliant() == False` → `_rule_based_insight()` 사용
3. 모든 응답은 `scrub_signal()` 한 번 더 통과 (삼중 방어선)

**Daily budget guard (ALREADY IMPLEMENTED)**: `AI_DAILY_LIMIT = 100` calls/day (UTC 일자 경계). 초과시 모든 신규 brief 는 rule-based fallback. 월 ~$3 상한 (Haiku 단가 기준).

---

## 5. Cron 등록 전략

**현재 구현**: Option C (Flask-APScheduler 인-프로세스, BackgroundScheduler).
- `app.py:243` `_init_scheduler(app)` — `RUN_SCHEDULER` env var opt-in
- `app.py:974` `sched.add_job(_scheduled_morning_briefs, trigger='cron', hour=6, minute=0, id='morning_briefs')`

**문제점**:
- Railway 배포 시 instance N개 → scheduler 도 N번 실행 → 각 user 가 N개 brief 생성됨 (UniqueConstraint 가 막아주지만 commit race + duplicate Claude 호출 = 비용 N배).
- Timezone 명시 없음 — 서버 local time 에 의존. Railway 는 UTC 라서 cron 'hour=6' 은 UTC 06:00 = KST 15:00. **현재 의도대로 KST 06:00 에 안 돔.**

**Delta 제안 (P0 — 즉시 수정 필요)**:
1. `CronTrigger(hour=21, minute=0, timezone='UTC')` 또는 `timezone='Asia/Seoul'` 명시. 후자가 가독성 우위.
2. Railway 단일 worker 보장: `RUN_SCHEDULER=true` 를 1대 인스턴스에만 설정 + replicas=1 강제. 또는 DB advisory lock (PostgreSQL `pg_try_advisory_lock`) 으로 race 차단.

**대안 평가**:
- **Option A (Railway scheduled jobs)**: ✅ 단일 실행 보장. ❌ 별도 컨테이너 spin up = cold start ~30s, FMP/Claude 클라이언트 재초기화 비용.
- **Option B (GitHub Actions schedule)**: ✅ 무료, 단일 실행. ❌ Railway DB 에 외부 접근 — 보안 노출(DATABASE_URL 비밀 유출 위험), 네트워크 latency, prod DB 직접 쓰기 거버넌스 부적합.
- **Option C (현재, APScheduler)**: ✅ 동일 프로세스, Flask app context 자연스러움. ❌ 다중 인스턴스 race.

**추천**: Option C 유지 + DB advisory lock 추가 (1개 인스턴스만 실제 실행). 이유: Railway 추가 컨테이너 비용 0, app context 그대로, 25줄 추가로 race 차단. 코드 변경은 별도 PR.

---

## 6. 비용 추정

**Claude Haiku 4.5 단가** (2026-Q2 기준 가정): input $0.25/1M, output $1.25/1M tokens.

**1회 호출 토큰**:
- input: system prompt (~250) + user prompt (~400 with portfolio injection) ≈ 650 tokens
- output: ≤60자 한국어 ≈ 120 tokens
- 합계 ≈ 770 tokens / call

**월 비용 (22 영업일)**: 10명 ₩1, 100명 ₩10, 1,000명 ₩95, 10,000명 ₩951. 월 100만원 예산 대비 0.01% 미만 — **사실상 무시 가능**. AI_DAILY_LIMIT=100 가드는 유지 (버그/loop 안전망). Sonnet 4.6 (input $3/1M, output $15/1M) 업그레이드 시에도 1000명 월 ~₩2,000. 품질 부족 시 Sonnet 권장.

**부수 비용**:
- FMP earnings calendar: 캐시 + ticker당 1콜, 사용자당 max 10 ticker → 활성 1000명 = 10,000 콜/일 → FMP $29 Starter 한도 내. ⚠️ 사용자 5000명 돌파 시 plan upgrade 필요.
- SendGrid: 무료 100/일 → Pro 100명 임계. 그 이상은 SendGrid Essentials $19.95/월.

---

## 7. 실패/재시도 정책

**현재 구현 (services/morning_brief_service.py)**:
- 매크로 fetch 실패 → `market_summary = {}` 로 진행, brief 생성 계속.
- 포지션/이벤트 fetch 실패 → 해당 섹션 skip, brief 생성 계속.
- AI insight 실패 (예외/budget/non-compliant) → `_rule_based_insight()` 사용.
- 사용자 단위 실패 → DB rollback + log + 다음 사용자 진행 (run_daily_briefs).

**Delta 제안**: AI 호출 retry 추가.
- `ai_service.generate_brief_insight()` 내부에서 3회 재시도 (1s/3s/9s exponential backoff).
- 5xx, timeout 만 재시도. 4xx (compliance reject 등) 는 즉시 fallback.
- 모든 재시도 실패 시 status='FALLBACK' 마크 (§3 의 status 컬럼).

**Static fallback 메모** (rule-based 가 부족할 때 — 예: 포지션도 없고 이벤트도 없는 dry day):
```
"오늘 06:00 KST 시점 관측. 포지션 N개 / 워치리스트 M개 추적 중.
 시장 일정 특이사항 없음."
```
법적 안전 검증: 동사 "관측" / "추적" / "없음" — 모두 관찰 톤. 추천/조언 단어 0. 미래 예측 0. 통과.

---

## 8. 법적 검토 (REQUIRED)

**자본시장법 §6 (투자자문업 등록)**:
- 위험: 개인화된 정보 제공이 "자문" 으로 해석될 가능성.
- 방어선 (현재 구현):
  1. `_FORBIDDEN_RE` 정규식 — 추천/조언/매수/매도/sell/buy 단어 차단.
  2. POSITIVE/NEGATIVE/NEUTRAL 라벨만 (§3 추가 시) — "관측" 톤. BUY/SELL/HOLD 사용 X (CLAUDE.md 명시 원칙).
  3. `scrub_signal()` 두번째 통과 (services.legal_filter).
  4. `disclaimer` 필드 항상 포함 ("정보 제공 목적, 투자 판단은 본인 책임").
  5. 프론트 `DisclaimerBanner` 가 brief 응답 옆에 항상 렌더 (mockup 명시).
- 정당성: "관측" / "Posture" 톤은 사실 보고 (예: "VIX 25 구간 관찰됨") 로, 이는 투자자문업이 아닌 정보제공업 (자본시장법 §9①㉓ "투자정보 제공") 영역. 단, 한국 금융감독원이 개별화된 의견을 자문으로 해석한 사례 있어 (2024 금감원 가이드라인) — **재검수 필요 영역**.

**미국 SEC**:
- Investment Advisers Act 1940 §202(a)(11) "investment adviser" 정의: regular advice for compensation. 메모 자체는 advice 가 아닌 observation 으로 포지셔닝.
- 단, U.S. 사용자에게 한국어로 발송하는 시점 → 미국 거주자 차단 (혹은 영문 면책 추가) 필요.
- Reg BI 적용 X (broker-dealer 가 아니므로). Form ADV 등록 X (no advice).

**재검수 필요 사항 (legal/compliance 부서 의뢰 — 현재 미흡)**:
1. Posture 라벨 "POSITIVE" 가 한국에서 "유리" 로 번역될 때 권유로 해석되지 않는지 — 라벨링 가이드 별도 문서 필요.
2. `disclaimer` 한 줄이 자본시장법 §50 (광고 시 표시사항) 7개 항목을 모두 만족하는지.
3. Pro+ 이메일 발송이 "전자적 투자조언" 으로 분류되는지 (e-mail = solicitation 가능성).
4. 1인 창업자가 직접 발송 시 "투자권유대행인" 등록 의무 면제 여부 확인 (자본시장법 §51).
5. KIS/Alpaca 브로커 데이터 가공 후 발송이 "투자정보의 가공" (자본시장법 §6②) 임을 표시광고법 §3 기만표시 방어선과 함께 검토.

→ **본 시스템은 legal 부서 사전 검수 통과 가정 하에 운영. 5건 재검수 항목은 launch 전 P0.**

---

## 9. 모니터링

**현재 구현**:
- `run_daily_briefs()` 가 `summary` dict 반환 (attempted/success/emailed/failed/skipped/ai_usage). 로깅만 됨.
- Sentry: app.py 에 SDK 초기화 (Sentry 인지). exception 자동 캡처.

**Delta 제안**:
1. **Slack 알림** (이미 6 워크플로우 인프라 — Memory `project_ci_automation.md`):
   - 매일 KST 06:30 KST 에 `summary` 를 `#morning-brief-ops` Slack 채널로 post.
   - failure_rate ≥ 10% → @here 멘션, ≥ 30% → @channel.
2. **Sentry tag**: `morning_brief.failure` tag 로 실패만 별도 dashboard.
3. **메트릭 연동** (Memory `analytics_metrics.md` KPI):
   - `daily_brief_open_rate` = (`/api/brief/today` GET 200 with available=true) / generated_count
   - `daily_brief_email_open_rate` = SendGrid webhook 통합 시
   - 두 KPI 를 main analytics dashboard 에 노출.
4. **Alembic migration health**: 신규 컬럼 추가 후 prod DB 의 NULL ratio 모니터링 (전체 row 의 95% 이상이 status 채워지면 backfill 완료로 판단).

---

## 10. Rollback

**Feature flag (제안)**: `ENABLE_DAILY_BRIEF_GEN` env var.
- 미설정/false (기본): cron job 등록 자체를 skip (`if os.environ.get('ENABLE_DAILY_BRIEF_GEN','true').lower() != 'true': return`). API 는 그대로 동작 — 기존 row 가 있으면 반환, 없으면 `{available:false}`.
- true: 현재 로직 (cron 활성).

**실제 위치**: app.py `_init_scheduler` 내 `sched.add_job(_scheduled_morning_briefs, ...)` 호출 직전 가드. 변경량 3줄.

**Hot rollback 시나리오**:
1. AI 가 부적절한 출력 → `ENABLE_DAILY_BRIEF_GEN=false` → 다음 날 06:00 부터 새 brief 생성 중단. 기존 row 는 immutable 이므로 영향 X.
2. Claude API 장애 지속 → fallback 가 자동 동작하므로 별도 rollback 불요.
3. 비용 급증 → `AI_DAILY_LIMIT` 을 10 으로 낮춰 즉시 90% rule-based 전환. 코드 한 줄 또는 env var.

**DB rollback**: `morning_briefs` 테이블 drop 시에도 다른 기능 영향 X (FK 외래는 user_id 만, 역참조 없음). `posture` / `status` / `source_data_hash` 신규 컬럼은 nullable 이므로 drop 시 경고 없음.

---

## Appendix A — 기존 vs 제안 변경 요약 (구현은 별도 PR)

| 항목 | 현재 (as-built) | 제안 (delta) |
|---|---|---|
| Cron timezone | 서버 local (UTC 의도와 mismatch) | `timezone='Asia/Seoul'` 명시 |
| 다중 instance | UniqueConstraint 만 의존 | DB advisory lock 추가 |
| posture 라벨 | 없음 (insight 텍스트만) | `posture` 컬럼 추가 (POSITIVE/NEGATIVE/NEUTRAL) |
| status 추적 | 없음 | `status` 컬럼 추가 |
| AI retry | 1회 | 3회 + exponential backoff |
| Slack 알림 | 없음 | 일일 summary post |
| Feature flag | 없음 | `ENABLE_DAILY_BRIEF_GEN` |
| Legal 재검수 | 미흡 | §8 의 5개 항목 launch 전 P0 |

**총 코드 변경 추정**: ~120 lines 추가, 0 line 수정 (기존 코드 손대지 않음 원칙).

---

## Appendix B — 기존 frontend 계약 무변경 보증

`endpoints.ts`:
```ts
morningBriefToday:    "/api/brief/today",
morningBriefArchive:  "/api/brief/archive",
morningBriefGenerate: "/api/brief/generate-now",
```
세 endpoint URL + 응답 shape (`{ ok, available, date, created_at, brief: {...} }`) 완전 유지. `posture` 추가 시 `brief.posture` 필드만 신설 (frontend 가 사용 X 일 때 무영향). `TodayMemoHero` 가 사용하는 `brief.insight`, `brief.disclaimer` 그대로 보존.
