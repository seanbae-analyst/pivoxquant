# PivoxQuant Launch Bundle — System Spec
**Date**: 2026-04-25
**Scope**: Tier 1+2+3+4 차별화 feature 시스템 설계 (visual design 제외)
**Legal frame**: 자본시장법 / 유사투자자문업 미신고 단계에서 안전한 범위 only

---

## 0. 법적 안전 패턴 (모든 feature 공통)

### 허용
- **관찰 (observation)** — "당신의 거래에서 X 패턴이 보입니다"
- **회고 (retrospective)** — "지난주 결과: ..."
- **통계 (statistics)** — "Quant CFO 그룹 평균: ..."
- **분류 (classification)** — "당신은 balanced 페르소나로 관찰됩니다"
- **paper trading 시뮬** — 실제 자금 미연동
- **고지 후 정보제공** — "이는 정보제공 목적이며 투자 권유가 아닙니다"

### 금지
- **명령형** — "X를 사세요/파세요", "should buy/sell"
- **직접 추천** — "X를 추천합니다", "recommend"
- **자문 (advisory)** — "당신은 X를 해야 합니다"
- **개별 종목 매매 가이드** — 특정 종목 buy/sell directive
- **확정적 미래 예측** — "X는 오를 것입니다"

### 모든 출력에 적용되는 scrub
- `services/legal/legal_filter.py` 의 89 regex 통과
- `services/legal/forbidden_terms.py` canonical 20개 단어 차단
- 모든 user-facing route 응답에 DisclaimerBanner

---

## TIER 1 — 출시일 (2주)

---

### Feature 1: Quant Composer (A)
**한 줄**: 40개 quant 모델을 유저가 on/off + 가중치 조정. Paper 백테스트 즉시.

#### Legal posture
- **위험**: 모델 추천 → 자문으로 해석될 수 있음
- **mitigation**:
  - "추천" 단어 절대 사용 금지 → "관찰", "관련", "참고"
  - 백테스트 결과는 **paper / 과거 데이터** 명시
  - "이는 과거 데이터 기반 시뮬레이션이며 미래 수익을 보장하지 않습니다" 고정 disclaimer
  - 모델 자체는 학술/공개 문헌 기반 (StatArb = Engle-Granger 1987 등) — 특허/독점 추천 아님
- **legal_filter pass**: 모든 모델 description 한글/영문 scrub 적용

#### Data model
```sql
ALTER TABLE investment_profiles ADD COLUMN enabled_quant_models JSON DEFAULT '[]';
ALTER TABLE investment_profiles ADD COLUMN model_weights JSON DEFAULT '{}';

-- 예시: enabled_quant_models = ["StatArb", "TSMOM", "FiftyTwoWeekHigh", ...]
-- 예시: model_weights = {"StatArb": 1.5, "TSMOM": 0.8, ...}  (default 1.0)
```

#### Service layer
**신규 파일**: `services/quant/composer.py`
- `apply_user_composition(user_id, base_score) -> float` — engine.py 호출 시 유저 model 선택 반영
- `validate_composition(enabled_models, weights)` — schema 검증, 빈 배열은 default
- `get_persona_preset(persona_code) -> dict` — 페르소나 → 모델 추천 매핑

**engine.py 수정** (~10줄): `quant_score` 계산 시 `enabled_quant_models` 필터링 + `model_weights` 곱

#### API
```
GET  /api/quant/models                 — 40 모델 목록 (description, category, default weight)
GET  /api/quant/composition            — 유저 현재 enabled + weights
PUT  /api/quant/composition            — body: {enabled, weights}
POST /api/quant/composition/backtest   — body: {enabled, weights, ticker, days}
                                         → paper 90일 결과 (Sharpe, return, drawdown)
POST /api/quant/composition/preset     — body: {persona} → 추천 preset 적용
```

#### Frontend (구조만)
- `/strategy` 페이지 신규
- 40 모델 카테고리 그리드 (Quant / Risk / Portfolio / Signal / AI / System 6 카테고리)
- 모델 카드: 이름 + 1줄 설명 + 학술 출처 + on/off + weight slider
- 우측 사이드바: 미니 백테스트 차트 + Sharpe + Max DD
- "Apply Persona Preset" 버튼

#### 공수: 4-6일

---

### Feature 2: Persona → Quant Auto-Apply (C)
**한 줄**: 페르소나 분류 결과 → 추천 모델 preset 자동 적용 (1-click).

#### Legal posture
- **위험**: 자동 적용 = 자문?
- **mitigation**:
  - **유저가 명시적으로 "Apply" 클릭해야 적용** (자동 침투 X)
  - "이 페르소나의 다른 유저가 자주 사용하는 모델 조합" 으로 표현 (관찰 사실, 추천 아님)
  - **paper backtest 결과만 표시** — 실제 거래 자동 X
  - 적용 후 "유저가 직접 조정 가능" 명시

#### Data
- 별도 테이블 불필요 — `services/quant/composer.py` 의 PRESET dict
```python
PERSONA_QUANT_PRESETS = {
    "beginner": {
        "enabled": ["MeanReversion", "MinVariance", "LedoitWolfShrinkage", "AnchoringBias"],
        "weights": {"MeanReversion": 1.0, "MinVariance": 1.5},
        "rationale": "변동성을 낮추는 보수적 조합"
    },
    "income": {...},
    "value": {...},
    "balanced": {...},  # 10 models
    "growth": {...},    # 14 models
    "quant": {...},     # 22 models (전체 quant + risk)
    "speculator": {...},# 12 models (high vol)
    "daytrader": {...}, # 8 models (intraday + breakout)
}
```

#### Service
- `services/quant/composer.py:get_persona_preset(persona_code) -> dict`
- `services/quant/composer.py:apply_persona_preset(user_id)` — 유저 profile 업데이트

#### API
- `POST /api/quant/composition/preset` — body: `{"persona": "quant"}`
- 응답: `{"applied": true, "enabled_count": 22, "rationale": "..."}`

#### Frontend
- Persona V2 카드 하단에 "Apply Quant CFO Preset (22 models)" 버튼
- 클릭 → 확인 모달 → /strategy 로 이동

#### 공수: 1-2일

---

### Feature 3: Persona Evolution Timeline (B)
**한 줄**: 9차원 페르소나 벡터의 시간에 따른 변화 시각화.

#### Legal posture
- **위험**: 낮음. 자기 데이터 시각화 only
- **mitigation**:
  - "관찰 변화" 라벨, "추천" / "조언" 단어 없음
  - 비교 대상은 페르소나 그룹 평균 (피어 통계, 익명)

#### Data model
**신규 테이블**: `persona_snapshots` (Layer 1과 통합)
```sql
CREATE TABLE persona_snapshots (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    computed_at TIMESTAMP NOT NULL,
    persona VARCHAR(20) NOT NULL,
    confidence INT NOT NULL,                -- 0..100
    features JSON NOT NULL,                 -- 9-dim {holding_period: 0.45, ...}
    present_mask JSON NOT NULL,             -- {holding_period: 1, ...}
    ranking JSON NOT NULL,                  -- [{persona, similarity}, ...]
    breakdown JSON,                         -- top contributors
    declared_persona VARCHAR(20),
    trade_count INT,
    window_days INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, computed_at)
);
CREATE INDEX idx_persona_snapshots_user_time ON persona_snapshots(user_id, computed_at DESC);
```

**migration**: `migrations/versions/015_persona_snapshots.py`

#### Service
**신규 파일**: `services/profile/persona_history.py`
- `take_snapshot(user_id, window_days=90, now=None) -> PersonaSnapshot`
- `get_history(user_id, window_days=90, days_back=365) -> list[PersonaSnapshot]`
- `compute_drift(snapshots) -> {distance, dominant_dim_changes, persona_transitions}`
- `detect_significant_drift(user_id) -> dict | None` — 4주 내 confidence/persona 큰 변화 감지

#### Cron job
**app.py 추가**:
```python
sched.add_job(
    _scheduled_persona_snapshots,
    trigger="cron",
    day_of_week="sun", hour=23, minute=0,
    timezone="Asia/Seoul",
    id="persona_snapshot_weekly",
    max_instances=1,
    coalesce=True,
)
```
- 일요일 23:00 KST 모든 active 유저 snapshot 저장
- `compute_persona_stats` 후에 실행 (group_benchmark 갱신 후)

#### API
```
GET /api/profile/persona-history?days=180   — 시간 시리즈 (snapshots 배열)
GET /api/profile/persona-drift              — 최근 drift 요약
```

#### Frontend
- `/profile` Section 04 하단에 timeline chart
- 시간축 X / persona 좌표 또는 confidence Y
- 9-dim 별 sparkline (small multiples)
- Drift alert 배지 (significant drift 감지 시)

#### 공수: 2-3일

---

### Feature 4: Layer 1 — PersonaSnapshot Persistence (이미 Feature 3에 포함)
- 위 Feature 3 의 `persona_snapshots` 테이블 + cron 으로 충족됨

---

### Feature 5: AI Trader Twin (Twin)
**한 줄**: 유저 페르소나 기반 paper portfolio 를 AI 가 운영. 매주 누적 비교.

#### Legal posture
- **위험**: 가장 민감. AI 가 "거래" → 자동매매 위반 우려
- **mitigation (강력)**:
  - **paper portfolio only** — 실제 자금 절대 X
  - **유저 자금과 100% 격리** — 별도 테이블, 별도 가상 잔고
  - **AI 결정은 유저에게 전송 안 됨** — "Twin 의 다음 매수" 라고 알리는 것조차 advisory 위험. 대신 **사후 공개** ("Twin 이 어제 X 매수했음")
  - 모든 응답에 "Twin 은 paper 시뮬이며 실제 매매 권유 아닙니다" 고정 disclaimer
  - "Twin 처럼 거래" 같은 1-click apply 절대 X (출시 후 법무 검토 후 결정)
  - **observational frame**: "당신의 페르소나 그대로 paper 거래한 결과" — 자기 분석 도구로 포지셔닝

#### Data model
```sql
CREATE TABLE ai_twin_portfolios (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    initialized_at TIMESTAMP NOT NULL,
    starting_cash NUMERIC(20, 4) NOT NULL DEFAULT 10000.00,  -- $10K paper
    current_cash NUMERIC(20, 4) NOT NULL,
    persona_at_init VARCHAR(20) NOT NULL,
    last_decision_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE ai_twin_positions (
    id BIGSERIAL PRIMARY KEY,
    twin_id INT REFERENCES ai_twin_portfolios(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    shares NUMERIC(20, 4) NOT NULL,
    avg_cost NUMERIC(20, 4) NOT NULL,
    opened_at TIMESTAMP NOT NULL,
    UNIQUE(twin_id, ticker)
);

CREATE TABLE ai_twin_trades (
    id BIGSERIAL PRIMARY KEY,
    twin_id INT REFERENCES ai_twin_portfolios(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    side VARCHAR(4) NOT NULL,  -- 'BUY' | 'SELL' (페이퍼 only, 라벨이지 directive 아님)
    shares NUMERIC(20, 4) NOT NULL,
    price NUMERIC(20, 4) NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    rationale TEXT,            -- 어떤 모델/시그널이 발동했는지
    composite_score NUMERIC(5, 2),
    pnl_at_close NUMERIC(20, 4)  -- close 시 충전
);

CREATE TABLE ai_twin_weekly_reports (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    week_ending DATE NOT NULL,
    user_return_pct NUMERIC(8, 4),
    twin_return_pct NUMERIC(8, 4),
    diff_pct NUMERIC(8, 4),
    user_trades_count INT,
    twin_trades_count INT,
    rationale_summary TEXT,
    UNIQUE(user_id, week_ending)
);
```

#### Service
**신규 파일**: `services/twin/`
- `twin_runner.py:run_twin_decisions(user_id, now=None)` — 매일 페르소나 기반 paper 거래 결정
- `twin_runner.py:_score_universe(persona, candidates)` — engine 의 quant_models 그대로 사용
- `twin_runner.py:_position_sizing(persona, signal, cash)` — Kelly 일부 / equal weight
- `twin_runner.py:_close_check(positions)` — TP/SL/holding period 점검
- `twin_reporter.py:generate_weekly_report(user_id, week_ending)` — paper P&L vs user P&L

#### Cron
```python
# 매일 16:30 KST (장 마감 후) - twin 의사결정
sched.add_job(_scheduled_twin_decisions, trigger="cron", hour=16, minute=30, timezone="Asia/Seoul", id="twin_daily")

# 일요일 21:00 KST - 주간 리포트
sched.add_job(_scheduled_twin_weekly, trigger="cron", day_of_week="sun", hour=21, timezone="Asia/Seoul", id="twin_weekly_report")
```

#### API
```
POST /api/twin/initialize           — paper $10K 시작 (1회만)
GET  /api/twin/portfolio            — 현재 paper 포지션 + cash
GET  /api/twin/trades?days=30       — Twin 의 paper 거래 이력 (사후 공개)
GET  /api/twin/weekly-reports?n=12  — 최근 12주 비교
GET  /api/twin/comparison           — 누적 비교 (user vs twin since inception)
```

#### Frontend
- `/twin` 페이지 신규
- "이번 주 당신 +2.1% / Twin +3.4%" 헤더
- 누적 그래프 (user vs twin)
- Twin 의 paper trade history
- 모든 출력에 "Twin 은 paper 시뮬, 매매 권유 아님" disclaimer

#### 공수: 1주

---

### Feature 6: Pre-Trade Friction (I)
**한 줄**: 유저가 거래 직전 2분 대기 + 이유 강제 작성. 감정거래 차단.

#### Legal posture
- **위험**: 매우 낮음. 유저가 자기 거래에 추가하는 step
- **mitigation**:
  - 우리는 "2분 기다리세요" 가 아니라 **"거래 결정에 reflection 시간 확보"** 표현
  - 모든 거래 데이터는 broker (Alpaca paper or KIS read-only) 에 그대로 전달
  - 우리가 거래를 막거나 권유하지 않음 — 단지 입력 UX 추가

#### Data model
```sql
CREATE TABLE pre_trade_reflections (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    intended_ticker VARCHAR(20) NOT NULL,
    intended_side VARCHAR(4),  -- BUY/SELL (유저가 입력, 라벨)
    intended_shares NUMERIC(20, 4),
    rationale TEXT,             -- 유저가 적은 이유 (필수)
    devil_advocate_seen TEXT,   -- AI Devil's Advocate 표시된 우려 (R 와 연동)
    cooldown_started_at TIMESTAMP NOT NULL,
    cooldown_ends_at TIMESTAMP NOT NULL,  -- +2 분
    proceeded_at TIMESTAMP,     -- 실제 거래 진행 시점
    cancelled_at TIMESTAMP,     -- 취소 시점
    UNIQUE(user_id, intended_ticker, cooldown_started_at)
);
```

#### Service
- `services/pre_trade/friction.py:start_cooldown(user_id, ticker, side, shares, rationale)` — 2분 timer
- `services/pre_trade/friction.py:check_status(reflection_id) -> 'pending' | 'ready' | 'expired'`
- `services/pre_trade/friction.py:proceed(reflection_id)` — 2분 지났으면 거래 실행
- 시장 환경 트리거 (FOMC ±30분 / 대량 변동 / VIX > 30) → cooldown 자동 5-10분 연장

#### API
```
POST /api/pre-trade/start    — body: {ticker, side, shares, rationale}
                                → 401 if rationale 미작성
                                → 200 with reflection_id + cooldown_ends_at
GET  /api/pre-trade/<id>     — 상태 + 남은 시간
POST /api/pre-trade/<id>/proceed   — 거래 진행 (cooldown 끝난 후만)
POST /api/pre-trade/<id>/cancel    — 취소
```

#### Frontend (구조)
- 모든 매수/매도 UI 가 직접 거래 X → `/api/pre-trade/start` 호출
- 모달: 이유 입력 + 2분 카운트다운 + Devil's Advocate 우려 표시 + Cancel/Proceed
- 본인 의지 강제

#### 공수: 2-3일

---

### Feature 7: Weekly Behavioral Score (N)
**한 줄**: 주간 1~100점 행동 점수. Activity Ring 스타일.

#### Legal posture
- **위험**: 낮음. 자기 통계 시각화
- **mitigation**:
  - 점수는 **회고적 (last week)** only — 미래 예측 X
  - "더 잘하려면 X 하세요" 같은 권유 X — 단지 점수 + 분해
  - 페르소나 그룹 평균 비교 (peer 통계, 추천 아님)

#### Score 구성 (5 sub-scores, 각 0-100, 가중 평균)
1. **Holding discipline** — 보유기간 페르소나 평균과 비교
2. **Loss-cut speed** — 손절 평균 일수 (낮을수록 점수 ↑)
3. **Position sizing** — 단일 포지션 자본 비중 (낮을수록 점수 ↑)
4. **FOMO frequency** — 큰 변동 후 매수 빈도 (낮을수록 점수 ↑)
5. **Reflection rate** — Pre-Trade rationale 작성률 + 평균 길이

#### Data model
```sql
CREATE TABLE behavioral_scores (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    week_ending DATE NOT NULL,
    overall_score NUMERIC(5, 2) NOT NULL,
    sub_scores JSON NOT NULL,  -- {holding: 75, loss_cut: 60, sizing: 90, fomo: 45, reflection: 100}
    persona_avg JSON,          -- 같은 페르소나 그룹 평균 (피어 비교용)
    notes TEXT,                -- 관찰 노트 (observational only)
    UNIQUE(user_id, week_ending)
);
```

#### Service
**신규 파일**: `services/behavior/scorer.py`
- `compute_weekly_score(user_id, week_ending) -> dict`
- `_holding_discipline_subscore(...)`, `_loss_cut_subscore(...)`, etc.
- `_observational_note(scores) -> str` — "이번 주 sizing 90/100 (지난주 75) — 관찰됨"

#### Cron
```python
sched.add_job(
    _scheduled_behavioral_scores,
    trigger="cron",
    day_of_week="sun", hour=22, minute=0,
    timezone="Asia/Seoul",
    id="behavioral_score_weekly",
)
```

#### API
```
GET /api/behavior/score             — 최근 점수
GET /api/behavior/score?weeks=12    — 최근 12주 시리즈
GET /api/behavior/breakdown         — 5 sub-score 상세
```

#### Frontend
- `/profile` Section 05 (신규) "이번 주 행동 점수"
- Ring chart (5 sub-score) + overall + 페르소나 평균 대비
- 12주 trend line

#### 공수: 2일

---

## TIER 1 합계
- 공수: ~16-20일 (병렬 가능 시 7-10일)
- 신규 테이블: 7개
- 신규 cron: 4개
- 신규 service 모듈: 5개

---

## TIER 2 — 출시 +1달 (간략)

### Feature 8: Outcome Attribution (factor decomposition)
- **legal**: 회고 only ("당신의 손실은 X% 시장 / Y% 행동편향" — 사후 분석)
- **data**: `outcome_attributions` 테이블 (trade_id, market_beta_pct, sector_pct, timing_pct, behavioral_pct)
- **service**: Fama-French 3-factor + behavioral disposition 계산
- **cron**: 매주 일요일 22:30 KST

### Feature 9: Layer 2 — BehaviorEvent stream
- **legal**: 익명 통계, 본인 데이터 본인 조회
- **data**: `behavior_events` (user_id, ts, event_type, target, metadata)
- **frontend SDK**: `lib/track.ts` — 모든 의미 클릭 비동기 전송

### Feature 10: Drift Alert (자동)
- **legal**: 관찰 alert ("4주 사이 turnover +121% 관찰됨")
- **service**: `services/profile/persona_history.py:detect_significant_drift`
- **trigger**: weekly cron 후 alert 생성
- **delivery**: in-app + email

### Feature 11: Decision Archive (1년 전 오늘)
- **legal**: 본인 거래 회고
- **data**: 기존 TradeHistory 활용, "1년 전 오늘 your trade + outcome" 매일 빌드
- **cron**: 매일 06:00 KST

### Feature 12: Strategy Save/Share/Copy
- **legal**: 페이지에 면책 + paper backtest result. "복제" 는 유저가 자발적 클릭
- **data**: `strategies` (id, owner_id, name, slug, enabled_models, weights, is_public, copies_count)
- **service**: fork → 자동 paper backtest, 결과 명확 표시

---

## TIER 3 — 출시 +2달 (간략)

### Feature 13: Watch Party (live earnings)
- **legal**: 라이브 commentary, 추천 아님. 모든 출력 scrub.
- **infra**: WebSocket + Redis pubsub + Anthropic streaming
- **data**: `watch_party_events`, `watch_party_chats`

### Feature 14: Tax Intelligence (KR)
- **legal**: 세금 시뮬레이터. 세무사 검토 후 출시. "세무 자문 아님" 고정 disclaimer.
- **data**: `tax_simulations` (한국 양도세 22%, 250만원 공제, 배당세, 종합소득)
- **service**: `services/tax/kr_calculator.py`

### Feature 15: Smart Money Map
- **legal**: 공시 데이터 가공 (KIND 외국인/기관 + SEC 13F). 정보제공만.
- **data**: `institutional_flows` (date, ticker, foreign_net, institutional_net, retail_net)
- **source**: KIND CSV / SEC 13F XBRL parser
- **cron**: 매일 17:00 KST (한국 마감 후), 분기 13F 자동 fetch

### Feature 16: KR 섹터 로테이션
- **legal**: 통계 시각화
- **data**: `sector_rotation_snapshots` (date, sector, momentum_rank, flow_rank)
- **service**: 한국 8 섹터 momentum + 외인 자금 흐름

### Feature 17: Dual-Listed Arb
- **legal**: 정보 제공 (가격 차 + 환율 + 보수율)
- **data**: `dual_listings` (kr_ticker, us_ticker, ratio_normal, current_ratio)
- **examples**: KODEX미국S&P500 ↔ SPY, BABA ↔ 9988.HK

### Feature 18: Custom Persona Builder
- **legal**: 본인 정의 자기 분류
- **data**: `investment_profiles.custom_persona_centroid` (JSON 9-dim)
- **service**: classify_persona_multi 가 custom centroid 우선 사용

---

## TIER 4 — 출시 +3달 (간략)

### Feature 19: Layer 3 — Adaptive Centroid (k-means)
- **legal**: 학술 클러스터링, 익명 집계
- **service**: `services/profile/centroid_learner.py:relearn_centroids(min_users=200)`
- **cron**: 월 1회. before/after diff 리포트.

### Feature 20: Voice Co-Pilot
- **legal**: 본인 voice memo + AI 정리. 추천 X.
- **infra**: Whisper API → Claude 정리 → Decision Archive 저장

### Feature 21: Founder Mode (CEO 공개)
- **legal**: CEO 자기 portfolio 공개는 합법 (본인 동의). 유사투자자문업 신고 후 제한 있을 수 있음.
- **data**: `User.is_founder_mode` flag, public read-only views

### Feature 22: Simulation Onboarding
- **legal**: 가상 시나리오. "2008년 9월, 당신은?" 답변으로 페르소나 추출.
- **data**: `onboarding_scenarios`, `onboarding_responses`

### Feature 23: AI Devil's Advocate
- **legal**: 우려 사항 나열 (조언 아님). "이런 위험이 관찰됩니다."
- **service**: Pre-Trade 와 통합. Claude prompt: "5가지 위험 요인만 나열. 권유 금지."

### Feature 24: Persona Mentor Match
- **legal**: 사회기능 — 자본시장법 위험 (사람 간 자문). **출시 전 법무 검토 필수**
- **scope**: 메시징은 익명 + 시그널 직접 전달 X
- **data**: `mentor_matches` (mentor_id, mentee_id, persona, status)
- **출시 보류 옵션** — 법적 명확성 확보 후

---

## 실행 순서 (출시 까지 2주 내)

### Week 1 (Day 1-7)
- Day 1: PersonaSnapshot 테이블 + cron + history API (Feature 3+4)
- Day 2: Quant Composer DB + composer.py (Feature 1)
- Day 3: Quant Composer engine 통합 + backtest API (Feature 1)
- Day 4: Persona preset (Feature 2) + Pre-Trade Friction (Feature 6)
- Day 5: Behavioral Score (Feature 7)
- Day 6: AI Twin DB + runner (Feature 5)
- Day 7: AI Twin weekly report + 통합 테스트

### Week 2 (Day 8-14)
- Day 8-10: Frontend 7 features 통합 (visual 미세조정 제외)
- Day 11: 법적 검토 round — disclaimer / scrub / forbidden terms
- Day 12: Pytest + 통합 시나리오 테스트
- Day 13: Railway / Vercel 배포 + 첫 dogfood
- Day 14: 버그 fix + 출시

---

## Build 동시병렬 전략

backend-dev + frontend-dev + qa 동시 wave:
- Wave 1: Feature 1, 3, 4 (DB + service)
- Wave 2: Feature 2, 5, 6, 7 (DB + service)
- Wave 3: Frontend 통합 (모든 feature)
- Wave 4: Tier 2 시작 (백그라운드)

---

## Risk Register

| Feature | 법적 risk | mitigation 강도 |
|---|---|---|
| Quant Composer | 추천 해석 | strong (paper only + disclaimer + 학술 출처) |
| Persona → Quant | 자동 적용 = 자문 | strong (유저 명시 클릭 필수) |
| Persona Evolution | 데이터 시각화 | low (관찰 only) |
| AI Twin | 자동매매 위반 | very high → mitigation: paper 격리 + 사후 공개 only |
| Pre-Trade Friction | UX 추가 | very low |
| Behavioral Score | 회고 통계 | low |
| Outcome Attribution | 회고 분석 | low |
| Watch Party | live commentary | medium → scrub + disclaimer 강화 |
| Tax Intelligence | 세무 자문 | medium → 세무사 검토 + disclaimer |
| Smart Money Map | 공시 데이터 가공 | low |
| Mentor Match | 사람 간 자문 | **very high → 법무 검토 후 결정** |

---

## 다음 액션
1. 이 spec 검토 후 우선순위 확정
2. backend-dev + frontend-dev agent 들 wave 1 동시 launch
3. 매일 진척 보고
4. 2주 내 Tier 1 완성 후 Tier 2 진입
