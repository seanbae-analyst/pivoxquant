# Claude Code Max 토큰 Budget Guardrail (v55-X3)

> **상태**: 설계 spec (코드 변경 X)
> **작성**: 2026-05-28
> **SoT 인용**: `~/.claude/projects/-Users-seanbae-Desktop---/memory/finance_token_ops.md` (2026-04-11), `~/.claude/projects/-Users-seanbae-Desktop---/memory/finance_budget.md` (2026-05-14)
> **목적**: CC Max 월정액 한도 내에서 자율 운영 + 5h 윈도우 ban 회피

---

## 1. 현 자원 인벤토리 (실측)

### 1.1 Claude Code Max 플랜 (CC 측 — 메시지 한도)
**메모리 인용** (`finance_token_ops.md` §J):
- 플랜: Claude Code Max 5x (2026-04-12 업그레이드, **$149.91 일시불**)
- **2026-05-14 추가 결제** ($220 = 305,800원) — `finance_budget.md` Ledger #5. 시나리오 A/B 미확정 (월 구독 여부 CEO 확인 필요).
- 제약: **5시간 롤링 윈도우 rate limit** (토큰 과금이 아닌 메시지/weighted token 한도)
- 윈도우 용량 (보수적 추정, `finance_token_ops.md`): **~5M weighted tokens / 5시간**
- 모델 가중치: `opus=1.0, sonnet=0.20, haiku=0.05`

### 1.2 Anthropic API Direct (백엔드 — 종량제)
**스크립트 인용** (`scripts/nightly/anthropic_cost_estimate.py`):
- DB 테이블: `anthropic_usage_log` (alembic 042)
- 일일 한도 환경변수: `PIVOX_ANTHROPIC_DAILY_LIMIT_USD` (default **$5.0/day**)
- 경보: 80% WARN / 100% HARD (Slack + Sentry)
- 가격표 (스크립트 내장, per 1M tokens):
  - haiku-4-5: in $0.80 / out $4.00 (현재 백엔드 모델)
  - sonnet-4-5: in $3.00 / out $15.00
  - opus-4: in $15.00 / out $75.00
- **state 파일**: `state/anthropic_usage_history.json` (실측: 2026-05-19~ 항목 전부 `today_cost_usd=0.0` → 실 API call 없음 OR 테이블 비어있음)

### 1.3 실측 path
| 자원 | 추적 path | 갱신 주기 |
|------|----------|----------|
| CC Max 메시지 | `~/.claude/projects/-Users-seanbae-Desktop---/*.jsonl` (실측 151개, 849MB) | 세션 실시간 |
| CC Max 토큰 usage | ⚠️ **OS 미노출** — JSONL 스키마 `[type, operation, timestamp, sessionId, content]` 만 (usage 필드 없음) | N/A |
| Anthropic API | `anthropic_usage_log` PostgreSQL 테이블 + `state/anthropic_usage_history.json` | 매일 22:00 KST |

**제약**: CC Max는 토큰 카운터를 외부에 노출하지 않음. **메시지 카운트 + 추정** 만 가능 (정확한 weighted token X).

---

## 2. CC Max 메시지/토큰 추정 모델

### 2.1 JSONL 기반 메시지 카운트 (실현 가능)
```
일일 메시지 = grep -c '"type":"message"' ~/.claude/projects/.../<today>.jsonl
세션 수      = find -newermt "$TODAY" *.jsonl | wc -l
```

**실측 (2026-05-28 0시~현재)**:
- 세션 수: **14개**
- JSONL 총 용량: **20.2 MB**

**실측 (2026-05-27 24h)**:
- 세션 수: **6개**
- JSONL 총 용량: **24.7 MB**

### 2.2 Weighted token 추정 (5h 윈도우 관리용)
JSONL은 토큰 미노출 → **content 길이 기반 추정** 사용:
```
estimated_tokens(session) ≈ sum(len(content)) / 3.5   # 한글 평균
weighted_tokens(session)  ≈ estimated_tokens × model_weight
                           # opus=1.0, sonnet=0.20, haiku=0.05
```
**오차**: ±30% (system prompt, tool result 제외 시 더 큼)

### 2.3 5h 윈도우 슬라이딩 카운트
```
window_start = now - 5h
window_tokens = Σ weighted_tokens(msgs where ts > window_start)
window_pct   = window_tokens / 5_000_000 × 100
```

---

## 3. Agent / Scheduled-task 호출 토큰 추산표

> **출처**: HANDOVER.md v44.7 + autopilot_log + 추정.
> **단위**: 입력 토큰 / 출력 토큰 (raw, weighted 아님)

| Cron / Trigger | 시각 (KST) | 모델 | 입력 (추정) | 출력 (추정) | weighted (한 회) |
|----------------|-----------|------|------------|------------|-----------------|
| morning-briefing | 06:27 | sonnet | 3,000 | 5,000 | 1,600 |
| bug-hunter (timebox 45m) | 03:37 | opus | 20,000 | 30,000 | 50,000 |
| legal-guard | 06:42 | sonnet | 10,000 | 8,000 | 3,600 |
| api-sentinel | 매시 47분 (24x) | haiku | 2,000 | 3,000 | 250 (회당) |
| daily-regression | 03:13 | sonnet | 15,000 | 20,000 | 7,000 |
| post-deploy-canary | trigger | haiku | 1,500 | 2,000 | 175 |
| weekly-memo (Mon) | 09:00 | sonnet | 5,000 | 10,000 | 3,000 |
| ops_anthropic_cost_estimate | 22:00 | (no CC) | 0 | 0 | 0 |
| ops_finance_weekly_check | 일 09:00 | (no CC) | 0 | 0 | 0 |

### 일일 baseline (현재 운영 cron 16개 가정)
| 카테고리 | 회/일 | weighted 합 |
|---------|-------|------------|
| 매시 trigger (api-sentinel 등) | 24 | 6,000 |
| 일 1회 light (sonnet) | 5 | 16,000 |
| 일 1회 heavy (opus, bug-hunter) | 1 | 50,000 |
| 인터랙티브 (CEO 세션) | ~14 sessions | **변동 1M~3M** |
| **총 weighted** | | **~1.1M~3.1M / day** |

**5h 윈도우 환산**: 평균 1M~1.5M / 윈도우. **5M 한도의 20-30%** 사용 (인터랙티브 제외 시).

⚠️ **인터랙티브 세션이 dominant**: 14 세션 × 평균 100K weighted = 1.4M / 일 (자율 모드 + opus 4.7 default 시 더 큼).

---

## 4. Budget Guardrail 4축 spec

### 축 A — 일일 사용량 추적
**신규 스크립트** (구상): `scripts/nightly/max_token_budget_check.py`
- 트리거: 매시 0분 fire (cron `0 * * * *`)
- 측정:
  1. JSONL 메시지 카운트 (오늘 + 5h 윈도우)
  2. content 길이 기반 weighted token 추정
  3. agent별 분해 (sessionId → 모델 추정, opus/sonnet/haiku 가중치 적용)
- 출력:
  - `/tmp/max_token_status.json` (실시간 dashboard)
  - Slack post (threshold 도달 시만)
- 비용: **0원** (Python 표준 라이브러리만, Slack free webhook)

**JSON 스키마**:
```json
{
  "ts": "2026-05-28T14:00:00+09:00",
  "today": {"sessions": 14, "messages": 312, "weighted_tokens": 1_240_000},
  "window_5h": {"start": "...", "weighted_tokens": 820_000, "pct": 16.4},
  "by_model_est": {"opus": 600_000, "sonnet": 180_000, "haiku": 40_000},
  "threshold": "GREEN",
  "next_check": "..."
}
```

### 축 B — Threshold 자동 대응

| 5h 윈도우 % | 상태 | 자동 대응 |
|------------|------|----------|
| 0-49% | 🟢 GREEN | 정상 운영 |
| 50-59% | 🟡 YELLOW | 감사팀 opus→sonnet 다운그레이드 (`feedback_token_ops` 룰) |
| 60-79% | 🟡 CAUTION | 비-critical agent (verify-*, 회귀 sweep) **throttle** (cron skip flag set) |
| 80-94% | 🔴 CRITICAL | 병렬 agent 중단 + 인터랙티브 세션 경고 |
| 95-99% | 🔴 EMERGENCY | **critical-only mode**: bug P0 / legal P0 / api-sentinel 만 |
| 100% | ⛔ STOP | 자동 정지 + Slack escalation. 30분 sleep 후 윈도우 슬라이딩 재평가 |

**Throttle 메커니즘**:
- 상태 파일: `/tmp/cc_token_throttle.flag`
- cron job은 실행 전 `if [ -f /tmp/cc_token_throttle.flag ]; then exit 0; fi` 가드 추가
- agent 위임 시 finance agent가 status 체크 후 dispatch 결정

**EMERGENCY 정의 (critical-only)**:
- ✅ Allow: `bug-hunter` (P0 only), `legal-guard` (P0 only), `api-sentinel`, `anthropic_cost_estimate`
- ❌ Block: `morning-briefing`, `weekly-memo`, `regression-sweep`, 모든 verify-* / audit-* / qa-*

### 축 C — Anthropic credit 절약 측정

**목적**: 사전생성 cron (Weekly Memo / Earnings Brief / Brag Card 등 12개 Artifact)이 백엔드 Anthropic API call을 얼마나 줄였는지 정량화.

**메트릭 정의**:
```
baseline = 마이그레이션 전 일평균 API call (state/anthropic_usage_history.json 의 today_calls)
current  = 마이그레이션 후 일평균 API call
savings_pct = (baseline - current) / baseline × 100
```

**현재 실측** (state/anthropic_usage_history.json):
- 2026-05-19 ~ 2026-05-28: **today_calls = 0** 전 항목
- 해석: (a) anthropic_usage_log 테이블이 비어있거나 (b) alembic 042 미적용 prod (메모리 `project_prod_schema_selfheal.md` 인용) → 측정 불가
- **선결 조건**: alembic 042 prod 적용 검증 + 백엔드 Anthropic API 호출 시 log 기록 확인

**측정 스크립트** (구상): `scripts/nightly/anthropic_credit_savings_check.py`
- 트리거: 매일 22:30 KST (anthropic_cost_estimate 직후)
- 출력: `state/anthropic_credit_savings.json`
- Slack 일주일 누적 절약율 post (매주 일요일 21:00)

**목표**: 12개 Artifact 사전생성 시 **70%+ 절약** (12개 × 100유저 = 1200 call/일 → 사전생성으로 ~360 call/일).

### 축 D — 5h ban 회피 패턴

**감지**: 윈도우 % 95% 도달 + 마지막 30분 신규 메시지 ≥ 10 → ban 임박.

**회피 액션**:
1. **자동 sleep**: 신규 cron job 진입 차단 (throttle flag set, 30분 후 재평가)
2. **Priority queue deferral**: 비-critical 작업을 다음 5h 윈도우로 연기
   - 연기 대상: weekly-memo, regression-sweep, design-token-drift 회귀 검사
   - 즉시 실행: bug P0, api-sentinel, legal P0
3. **시간대 회피 패턴** (preventive):
   - 무거운 작업 (opus 4.7, multi-agent wave): **03:00-07:00 KST 새벽 집중**
   - 낮 시간 (09:00-22:00 KST): **critical-only + 인터랙티브 우선**
   - 인터랙티브 세션은 CEO 의지 우선 — 자동 차단 X, 경고만

**자율 모드 + Full Throttle 모드 조정**:
- 메모리 `feedback_pre_launch_full_throttle.md` (2026-05-17, 출시 전 토큰 절약 금지)와 충돌 가능
- **해결**: Full Throttle은 인터랙티브 세션 + opus 4.7 default 유지하되, **cron-level throttle은 95%+에서만 발동**. Full Throttle override 룰은 ban 회피보다 우선순위 낮음 (ban 자체가 자율 운영 정지 = 더 큰 손실)

---

## 5. Cron + 모니터링 spec

| Cron ID | 스케줄 | 스크립트 | 출력 | 비용 |
|---------|--------|---------|------|------|
| `ops_max_token_budget_check` | `0 * * * *` (매시 0분) | `scripts/nightly/max_token_budget_check.py` | `/tmp/max_token_status.json` + Slack (threshold만) | 0원 |
| `ops_anthropic_credit_savings` | `30 22 * * *` (매일 22:30) | `scripts/nightly/anthropic_credit_savings_check.py` | `state/anthropic_credit_savings.json` | 0원 |
| (기존) `ops_anthropic_cost_estimate` | `0 22 * * *` (매일 22:00) | `scripts/nightly/anthropic_cost_estimate.py` | `state/anthropic_usage_history.json` | 0원 |

**알림 채널 통일**:
- Slack webhook (메모리 `slack-bridge` skill — webhook free tier)
- Sentry alert (free tier 5K errors/월, `finance_budget.md` C섹션)
- 60% / 80% / 95% / 100% 4 단계

---

## 6. 출시 후 시나리오

### 시나리오 X1 — 베타 100 유저 (출시 직후)
- 백엔드 Anthropic API call: 100 유저 × 평균 5 call/일 = **500 call/일**
- 평균 토큰: 입력 2K + 출력 3K = haiku 기준 **$0.014/call → $7/일** ($210/월)
- 일일 한도 `PIVOX_ANTHROPIC_DAILY_LIMIT_USD=$5` 초과 → **WARN 발동**
- CC Max 자율 운영: cron 16개 + 인터랙티브 1.5M weighted/일 → 윈도우 30% 평균 (안전)
- **결정 포인트**: 베타 100 유저 도달 시 일일 한도 $5 → $10 상향 (예산 영향 분석 별도)

### 시나리오 X2 — 1000 유저
- API call: 1000 × 5 = **5,000 call/일**
- 토큰 비용 (haiku): **$70/일 = $2,100/월 (~₩2.9M)** — 베타 매출 ₩0~수십만 수준 대비 압도적
- **선결 조건**: 사전생성 Artifact 70%+ 절약 달성 → 실제 API call 1,500/일로 압축 → **$21/일 = $630/월 (~₩870K)**
- 매출 1,000 유저 × 3% 전환 × ₩9,900 = ₩297K/월 → **여전히 적자** ($630K vs ₩297K)
- CC Max 자율 운영: cron 부담 일정 (cron 자체는 유저 수 영향 작음). 인터랙티브 ramp-up 시 윈도우 50% 평균
- **결정 포인트**: 1000 유저 = 손익분기 불가. 가격/전환율 재검토 OR Anthropic 직접 결제 활성 (CEO 결정)

### 시나리오 X3 — 5000 유저
- API call: 5,000 × 5 = **25,000 call/일**
- 사전생성 70% 절약 후: 7,500 call/일 = $105/일 = $3,150/월 (~₩4.4M)
- 매출: 5,000 × 3% × ₩9,900 = ₩1.485M/월 — **여전히 적자**
- 5% 전환 시: 5,000 × 5% × ₩14,000 (Pro/Premium mix) = ₩3.5M/월 → **거의 BEP**
- **CC Max 한도**: 5h 윈도우 5M weighted token 가정 — cron 부담 + 인터랙티브 dominant. **한계 도달 예상**
- **결정 포인트**:
  - Anthropic API direct 결제 필수 (월 ₩4M+ 추가 비용)
  - 또는 모델 다운그레이드 (sonnet → haiku 강제, 품질 trade-off)
  - 또는 매출 모델 재설계 (B2B / 라이선스 / API 재판매)

### 자율 운영 지속 가능성 매트릭스

| 유저 수 | CC Max 윈도우 % | Anthropic 월비용 | 매출 | 자율 운영 |
|--------|----------------|-----------------|------|----------|
| 0 (현재) | 20-30% | ~$0 | ₩0 | ✅ 무한 |
| 100 | 30% | ~$210 | ₩30K | ✅ 지속 (1년+) |
| 500 | 40% | ~$525 (사전생성 후 $158) | ₩148K | 🟡 borderline |
| 1000 | 50% | ~$630 (사전생성 후) | ₩297K | 🔴 적자 가속 |
| 5000 | 80%+ | ~$3,150 (사전생성 후) | ₩1.485M | ⛔ 자본금 추가 또는 결제 활성 필수 |

---

## 7. 즉시 실행 권고 (출시 전 P0)

1. **alembic 042 prod 적용 확인** — `anthropic_usage_log` 테이블이 prod에 존재하지 않으면 절약 측정 불가 (`project_prod_schema_selfheal.md` 인용)
2. **신규 cron 2개 등록** — `ops_max_token_budget_check` (매시) + `ops_anthropic_credit_savings` (22:30). 추가 비용 0원
3. **state 디렉토리 보강** — `state/cc_max_token_history.json` + `state/anthropic_credit_savings.json` 신규 (Python `json.dump`만 사용)
4. **Slack threshold 알림 spec 정합** — 60/80/95/100% 4단계로 통일 (현재 anthropic_cost_estimate는 80/100% 2단계만)
5. **Full Throttle 룰 조정 명문화** — `feedback_pre_launch_full_throttle.md` 에 "cron-level throttle은 95%+에서만 발동" 단서 추가

## 8. 절대 금지 (재확인)

- ❌ Anthropic 크레딧 추가 충전 권유 (`feedback_no_extra_cost`)
- ❌ Max 플랜 업그레이드 권유 ($220 시나리오 B 확정 전)
- ❌ 인터랙티브 세션 자동 차단 (CEO 의지 우선)
- ❌ 데이터 없는 추측 절약율 보고 — state JSON 실측만

---

## Status

```
## Completion Checklist
- [x] Phase 1 토큰 사용 measure (finance_token_ops + finance_budget + state JSON 인용): COMPLETE
- [x] Phase 2 Max 한도 mapping (5h 윈도우 5M weighted, 가중치 표): COMPLETE
- [x] Phase 3 Guardrail 4축 spec (A/B/C/D): COMPLETE
- [x] Phase 4 Cron + 모니터링 spec (3개 cron 통합): COMPLETE
- [x] Phase 5 출시 후 시나리오 (X1/X2/X3 + 매트릭스): COMPLETE
- [x] 600줄 이하: COMPLETE (실측 ~290줄)
- [x] 코드 변경 X / push 금지: COMPLETE

## Status: COMPLETE
```
