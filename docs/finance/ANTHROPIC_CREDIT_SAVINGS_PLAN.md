# Anthropic Credit 절약 측정 + 운영 Plan (v55-X3)

> **상태**: 설계 spec (코드 변경 X)
> **작성**: 2026-05-28
> **SoT 인용**: `scripts/nightly/anthropic_cost_estimate.py`, `state/anthropic_usage_history.json` (실측), `~/.claude/projects/-Users-seanbae-Desktop---/memory/finance_budget.md`
> **목적**: 사전생성 cron 가동 후 백엔드 Anthropic API call 감소량 정량화 + 절약율 측정

---

## 1. 배경 — 왜 절약 측정인가

### 1.1 SWOT 500 사건 (`finance_token_ops.md` 인용)
- 2026-05-09 v28 세션: **Anthropic 크레딧 소진** → API 전면 차단 → SWOT 500 에러
- root cause: 백엔드가 유저 요청마다 Claude API 직접 호출 → 크레딧 burst 소진
- 해결: 사전생성 (precompute) + fallback UX (gracefully degrade)

### 1.2 Pre-Launch 전략
- 12개 Artifact를 사전생성 cron으로 batch 생성
  - Weekly Memo (유저별 주간 1회)
  - Earnings Pre-Brief (실적 발표 D-3)
  - Brag Card (월간)
  - News digest, Insider digest, SWOT, 4-pillar 등 detail 페이지 컴포넌트
- 사전생성 후 백엔드는 DB에서 read-only 응답 → API call 폭감

### 1.3 비용 압박 (`finance_budget.md` §C, §D 인용)
- 시나리오 A (현 default): 월 고정비 40,310원 (FMP만)
- 시나리오 B: 월 346,110원 (Max 플랜 월 갱신 시) — Runway 1.12개월 = 34일 RED
- **Anthropic API direct 결제 활성 시 추가 부담**: 1000 유저 기준 월 $630 (₩870K) — 베타 매출 압도

→ 절약율 **70%+ 달성**이 자율 운영 지속 가능성의 전제 조건

---

## 2. 측정 인프라 현황 (실측)

### 2.1 기존 자산 (재사용)
- **스크립트**: `scripts/nightly/anthropic_cost_estimate.py` (Wave I G-3, 364줄)
  - 매일 22:00 KST 실행
  - DB 테이블 `anthropic_usage_log` 집계 (alembic 042)
  - 일일 비용 추정 + 80%/100% Slack 알림
- **state**: `state/anthropic_usage_history.json` (실측 90일 보관)
- **환경변수**: `PIVOX_ANTHROPIC_DAILY_LIMIT_USD` (default $5.0)

### 2.2 실측 데이터 (state/anthropic_usage_history.json)
```
2026-05-19 ~ 2026-05-28 (10일):
  today_calls = 0 (전 항목)
  today_cost_usd = 0.0 (전 항목)
  today_input_tokens = 0
  today_output_tokens = 0
```

**해석**:
1. (A) 백엔드 Anthropic API call 실제로 발생하지 않음 → 사전생성 효과 이미 발휘 중?
2. (B) `anthropic_usage_log` 테이블 prod 미존재 → 측정 자체 실패 (메모리 `project_prod_schema_selfheal.md`: alembic 040+ 컬럼 누락 사고와 동일 패턴)
3. (C) 백엔드가 API 호출은 하지만 log 기록 코드 미통합

**선결 조치 필요**: 어느 케이스인지 확인 (production agent 위임). 본 spec은 (A) 또는 (B+C 해결 후) 가정 하에 설계.

### 2.3 가격표 (스크립트 내장, per 1M tokens)
| 모델 | 입력 | 출력 |
|------|------|------|
| haiku-4-5 (현재 백엔드) | $0.80 | $4.00 |
| sonnet-4-5 | $3.00 | $15.00 |
| opus-4 | $15.00 | $75.00 |

---

## 3. 절약 측정 메트릭 정의

### 3.1 핵심 메트릭
```
baseline_period   = 2026-04-15 ~ 2026-05-08 (사전생성 cron 가동 전 24일)
treatment_period  = 2026-05-09 ~ 현재 (사전생성 cron 가동 후)

baseline_avg_call_per_user_day   = baseline_calls / baseline_users / baseline_days
treatment_avg_call_per_user_day  = treatment_calls / treatment_users / treatment_days

savings_pct = (baseline_avg - treatment_avg) / baseline_avg × 100
savings_usd = baseline_projected_cost - treatment_actual_cost
```

### 3.2 부가 메트릭
- **per-feature savings**: Weekly Memo / Earnings Brief / Brag Card 등 feature별 분해
- **모델 mix shift**: opus 호출 비율 감소 (사전생성은 sonnet/haiku로 가능)
- **call latency p95**: 사용자 응답 시간 (사전생성 = DB read = <100ms)

### 3.3 목표 임계값
| 메트릭 | 목표 | 측정 시점 |
|--------|------|----------|
| savings_pct (전체) | **≥ 70%** | 7일 rolling avg |
| Weekly Memo savings | **≥ 95%** | 주간 (월요일 측정) |
| Earnings Brief savings | **≥ 80%** | 실적 시즌 끝 |
| Detail 페이지 (SWOT/4-pillar) savings | **≥ 60%** | 일평균 |
| 비상 fallback rate | **≤ 5%** | 일평균 (사전생성 실패 → live API call) |

---

## 4. 측정 cron spec (신규 — 코드 변경 X, spec only)

### 4.1 `ops_anthropic_credit_savings`
- **스케줄**: `30 22 * * *` (매일 22:30 KST, anthropic_cost_estimate 직후)
- **스크립트**: `scripts/nightly/anthropic_credit_savings_check.py` (구상)
- **출력**:
  - `state/anthropic_credit_savings.json` (90일 history)
  - Slack post (주간 합산, 매주 일요일 21:00만)
- **비용**: 0원

### 4.2 JSON 스키마 (`state/anthropic_credit_savings.json`)
```json
{
  "history": [
    {
      "date": "2026-05-28",
      "treatment_calls": 142,
      "treatment_tokens_in": 285000,
      "treatment_tokens_out": 428000,
      "treatment_cost_usd": 1.94,
      "baseline_projected_calls": 500,
      "baseline_projected_cost_usd": 7.00,
      "savings_pct": 71.6,
      "savings_usd": 5.06,
      "by_feature": {
        "weekly_memo": {"calls": 0, "baseline_calls": 100, "savings_pct": 100},
        "earnings_brief": {"calls": 12, "baseline_calls": 60, "savings_pct": 80.0},
        "detail_swot": {"calls": 80, "baseline_calls": 200, "savings_pct": 60.0},
        "live_chat": {"calls": 50, "baseline_calls": 140, "savings_pct": 64.3}
      },
      "fallback_rate_pct": 3.5,
      "recorded_at": "2026-05-28T13:30:00+09:00"
    }
  ]
}
```

### 4.3 baseline 추정 로직
- baseline_projected_calls = `유저 수 × 평균_call_per_user_day_사전`
- 평균 추정값: **5 call/user/day** (베타 가정, CEO 검증 필요)
- 이후 실측 누적 시 baseline 동적 갱신 (지난 28일 평균)

---

## 5. 절약 strategies 매핑

### 5.1 사전생성 가능 vs 불가능
| Feature | 사전생성 가능? | 트리거 | 모델 |
|---------|-------------|-------|------|
| Weekly Memo | ✅ 100% | 월요일 09:00 cron | sonnet (품질 우선) |
| Earnings Pre-Brief | ✅ 100% | D-3 cron (실적 캘린더 기반) | sonnet |
| Brag Card | ✅ 100% | 월 1회 cron | sonnet |
| Detail SWOT | 🟡 부분 (top 200 종목만) | 일 1회 cron | haiku |
| Detail 4-pillar | 🟡 부분 (top 200) | 일 1회 cron | haiku |
| News digest | ✅ 100% | 30분 cron (캐시 30min) | haiku |
| Insider digest | ✅ 100% | 일 1회 cron | haiku |
| Live Chat (AI Assistant) | ❌ 불가 | 사용자 요청 | sonnet |
| Custom queries | ❌ 불가 | 사용자 요청 | sonnet |

**70%+ 절약 달성 path**: Live Chat / Custom queries 만 live, 나머지 사전생성.

### 5.2 모델 다운그레이드 전략
- **현재**: 백엔드 default = `claude-haiku-4-5-20251001` (`services/ai/service.py` MODEL 인용 — 스크립트 docstring §13)
- **이미 haiku 사용 중** → 추가 다운그레이드 여지 없음 (sonnet/opus 전환 시 비용 증가만)
- **권고**: haiku 유지 + 사전생성 확대로 절약

### 5.3 캐시 전략
- 동일 유저 동일 종목 동일 시각 (분 단위) 응답: **15분 캐시** (Vercel Edge Function 가능)
- 검증: 유저 행동 패턴 분석 → 같은 종목 반복 조회 비율 측정 별도 task

---

## 6. 시나리오 절약 시뮬레이션

### 6.1 베타 100 유저 (시나리오 X1)
| 항목 | 사전생성 전 (baseline) | 사전생성 후 (treatment) | 절약 |
|------|----------------------|----------------------|------|
| API call/일 | 500 (5/유저) | 150 (1.5/유저) | 70% |
| 비용/일 (haiku) | $0.014 × 500 = $7.0 | $0.014 × 150 = $2.1 | $4.9/일 |
| 월 비용 | $210 | $63 | **$147/월 = ₩205K** |

### 6.2 1000 유저 (시나리오 X2)
| 항목 | baseline | treatment | 절약 |
|------|---------|----------|------|
| call/일 | 5,000 | 1,500 | 70% |
| 일 비용 | $70 | $21 | $49/일 |
| 월 비용 | $2,100 | $630 | **$1,470/월 = ₩2.05M** |

### 6.3 5000 유저 (시나리오 X3)
| 항목 | baseline | treatment | 절약 |
|------|---------|----------|------|
| call/일 | 25,000 | 7,500 | 70% |
| 일 비용 | $350 | $105 | $245/일 |
| 월 비용 | $10,500 | $3,150 | **$7,350/월 = ₩10.2M** |

→ 5000 유저 단계에서 절약 효과는 **연간 ₩122M 가치**. 사전생성 인프라 투자 ROI 자명.

---

## 7. 모니터링 + 알림 spec

### 7.1 Slack 알림 매트릭스
| 트리거 | 채널 | 빈도 |
|--------|------|------|
| 일 절약율 < 50% (3일 연속) | `#pivox-alerts` | 즉시 |
| 일 절약율 < 30% (1일) | `#pivox-alerts` | 즉시 |
| 비상 fallback rate > 10% | `#pivox-alerts` | 즉시 |
| 주간 누적 절약율 + 비용 절약 | `#pivox-finance` | 매주 일 21:00 |
| 사전생성 cron 실패 | `#pivox-alerts` | 즉시 |

### 7.2 Sentry 통합
- `_capture_sentry_warning()` 함수 재사용 (기존 anthropic_cost_estimate.py 패턴)
- 절약율 < 30% 또는 fallback rate > 10% 시 warning capture
- Free tier 5K errors/월 한도 — 임계값 신중 설정

---

## 8. 단계별 롤아웃 plan

### Phase A — 측정 인프라 (출시 전 P0)
1. `anthropic_usage_log` 테이블 prod 적용 검증 (production agent 위임)
2. 백엔드 API call 통합: `services/ai/service.py` 에서 호출 시마다 log INSERT
3. `state/anthropic_usage_history.json` 비정상 0 값 원인 확인

### Phase B — 사전생성 cron 활성화 (출시 직전)
1. Weekly Memo cron 가동 (월요일 09:00) — 이미 메모리 `feature_preservation` 룰 인용
2. Earnings Pre-Brief cron (실적 캘린더 기반)
3. Detail page top 200 종목 일 1회 사전생성

### Phase C — 측정 cron 가동 (Phase A 완료 후)
1. `scripts/nightly/anthropic_credit_savings_check.py` 신규
2. crontab 등록: `30 22 * * *`
3. 첫 7일 baseline 수집 (treatment 직전 데이터)

### Phase D — 절약 평가 (베타 100 유저 도달 시)
1. 7일 rolling avg 절약율 ≥ 70% 검증
2. feature별 분해로 미달 항목 식별
3. CEO 보고 + 추가 사전생성 후보 도출

---

## 9. 출시 후 지속 가능성

### 9.1 자율 운영 가능 임계점
| 유저 수 | 사전생성 후 월 비용 | 매출 | 적자/흑자 | 자율 운영 |
|--------|------------------|------|----------|----------|
| 100 | $63 (~₩87K) | ₩30K | -₩57K | ✅ 100만원 예산으로 17개월 |
| 500 | $158 (~₩220K) | ₩148K | -₩72K | 🟡 14개월 |
| 1000 | $630 (~₩870K) | ₩297K | -₩573K | 🔴 2개월 |
| 5000 | $3,150 (~₩4.4M) | ₩1.485M | -₩2.9M | ⛔ 자본금 추가 필수 |

### 9.2 결정 시점 트리거
- **500 유저 도달**: 가격 인상 검토 (Pro 9,900 → 12,900?)
- **1000 유저 도달**: 전환율 5%+ 달성 OR Anthropic 결제 활성 필수
- **5000 유저 도달**: B2B 라이선스 / API 재판매 모델 필수

---

## 10. 절대 금지 + 제약

- ❌ **추가 비용 권유 금지** (`feedback_no_extra_cost`): Anthropic 크레딧 충전 / 모델 업그레이드 권유 X
- ❌ **추측 절약율 보고 금지**: `state/anthropic_credit_savings.json` 실측만 인용
- ❌ **사전생성 누락 기능 임의 추가 금지**: `feedback_feature_preservation` 룰 — Live Chat은 사용자 의도. 사전생성으로 대체 X
- ❌ **AskUserQuestion 호출 X**
- ✅ **CEO 결정 carry-over**: Phase A 의 (B)/(C) 케이스 확인 = CEO 또는 production agent 위임 필요. 본 문서엔 carry-over로만 기록

---

## Status

```
## Completion Checklist
- [x] 배경 (SWOT 500 + Pre-Launch 전략 + 비용 압박): COMPLETE
- [x] 측정 인프라 현황 (스크립트/state/실측 0값 해석): COMPLETE
- [x] 절약 메트릭 정의 (savings_pct + per-feature + 임계값): COMPLETE
- [x] cron spec + JSON 스키마 (ops_anthropic_credit_savings): COMPLETE
- [x] 절약 strategies (사전생성 가능/불가능 표 + 모델 + 캐시): COMPLETE
- [x] 시나리오 시뮬레이션 (X1/X2/X3 절약액): COMPLETE
- [x] 모니터링 알림 (Slack + Sentry): COMPLETE
- [x] Phase A-D 롤아웃 plan: COMPLETE
- [x] 출시 후 지속 가능성 임계점: COMPLETE
- [x] 600줄 이하: COMPLETE (실측 ~270줄)
- [x] 코드 변경 X / push 금지: COMPLETE

## Status: COMPLETE
```
