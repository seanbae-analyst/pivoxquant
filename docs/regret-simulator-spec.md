# Counterfactual Simulator (후회 시뮬레이터) — PRD + Technical Spec

> **Document Owner**: Head of Product
> **Date**: 2026-04-14
> **Sprint**: 1-day (8 hours)
> **Status**: Draft v1 → Engineering Handoff Ready
> **Codename**: `regret-simulator` (내부) / "후회 시뮬레이터" (공개 X) → **"What-If 시뮬레이터"** (공개 명칭)

---

## 0. Naming Decision

**내부 코드명**: `regret-simulator` (팀 내부 직관적)
**공개 노출 명칭**: **"What-If 시뮬레이터"** / **"만약에 샀다면"**
**이유**:
- "후회"는 부정적 감정 → 바이럴 초반엔 재밌지만 장기 브랜드 훼손
- "후회 유발"을 숨기지는 않되, 제품 UI는 중립적 "시뮬레이션 도구"로 포지셔닝
- 자본시장법 관점에서도 "후회"라는 감정 유도 단어는 회피가 안전

---

## 1. Problem Statement

### Who
- **Primary**: 20–30대 MZ 투자자 (미장 입문 1–3년차), 월 가처분 소득 30–100만원
- **Secondary**: 투자 관심은 있으나 미시작한 "예비 유저" (가장 바이럴에 강함)
- **Edge**: "친구 말 듣고 샀으면 ㅠㅠ" 경험이 있는 모든 유저

### What (Pain)
1. **FOMO 불확실성**: "그때 샀으면 지금 얼마?" 계산을 매번 손으로 함 (현재가 × 수량 / 과거가 암산)
2. **교훈 부재**: 과거 투자 실수/성공이 데이터로 남지 않음 → 같은 실수 반복
3. **DCA vs Lump-sum 감 없음**: "매월 넣는 게 나아? 한 번에 지르는 게 나아?" 토론 끝없음
4. **바이럴 공유 욕구**: "이거 봐 ㄹㅇ 미쳤다" 스크린샷을 찍을 만한 포맷이 없음

### Why Now
- **경쟁사 공백**: Yahoo Finance `Compare` 기능이 있으나 한국어 X, DCA 시뮬 X, 공유 디자인 X
- **기존 PivoxQuant 자산 재활용 가능**: `data_fetcher.get_price_history()` (Alpaca + FMP 백본) 그대로 사용
- **SNS 바이럴 타이밍**: "엔비디아 10년 전에 샀으면" 밈이 2026년 상반기 X/인스타/유튜브쇼츠에서 지속 트렌딩
- **1일 스프린트 가능**: 신규 데이터/모델 불필요, 기존 퍼스트 파티 데이터 소스로 완결

### Evidence
- safe-features-brainstorm.md 상위 10개 중 **DCA 시뮬레이터 = Score 20.0 (최상위)**
- 유튜브 "월 10만원 S&P500 10년" 콘텐츠 누적 조회수 수백만 (수요 검증)
- Yahoo Finance Compare 월 방문 (글로벌) 1천만+ → 한국판 공백
- PivoxQuant qa_bug_log.md P1 이슈 다수 → **리텐션 전에 신규 획득 후크 필요**

---

## 2. Solution

### Core
**1분 안에 "과거에 샀다면 지금 얼마" 답을 시각적으로 보여주고, 스크린샷 한 장으로 카톡/X 공유되는 단일 페이지 도구.**

### 3 Primary User Scenarios

#### Scenario A — "코로나 폭락에 NVDA 샀으면?"
> 수진(28세, 마케터)은 친구가 "야 NVDA 코로나 때 샀으면 인생 역전" 하는 말을 듣고 PivoxQuant에서 시뮬레이션.
> 입력: `NVDA` / `2020-03-23` / `500만원` → 결과: **현재가치 ≈ 1.2억원 / 수익률 +2,300%**
> "와 미친다" 모먼트 카드 → 스크린샷 → 카톡방 공유 → 친구들이 링크 클릭 → 회원가입.

**Acceptance**:
- [ ] Given 2020-03-23에 NVDA 500만원 입력 When 계산 버튼 클릭 Then 3초 이내 결과 카드 표시
- [ ] Given 결과 화면 When "공유" 버튼 클릭 Then 워터마크 포함 OG 이미지 생성 + 카톡/X 링크 제공

#### Scenario B — "친구가 추천한 종목 안 샀으면?"
> 민호(26세, 직장인)는 2023년 1월 친구가 "TSLA 지금이야" 했을 때 안 샀음. 지금 계산해보니 다행.
> 입력: `TSLA` / `2023-01-05` / `300만원` → 결과: **현재가치 ≈ 280만원 / 수익률 -6.7%**
> "안 사길 잘했네 ㅋㅋ" 안도 카드 → 역시 공유 가치 존재.

**Acceptance**:
- [ ] 수익률 음수일 때에도 "손실" 이 아닌 **"대안 시나리오"** 프레이밍으로 표시 (e.g. "이 돈으로 다른 걸 했다면?")
- [ ] 부정 결과일 때 **자동 비교 카드**: "같은 돈 S&P500에 넣었다면" 제시

#### Scenario C — "월 50만원 DCA했으면?"
> 지은(32세, 프리랜서)은 "매월 50만원씩 SPY에 3년 DCA했으면 지금 얼마?" 궁금.
> 입력: `SPY` / `2023-04-14` / `월 50만원 반복` → 결과: **투자원금 1,800만원 / 현재가치 ≈ 2,350만원 / 수익률 +30.5%**
> 연도별 누적 성장 라인 차트 + 매월 매수 포인트 점 → "꾸준함의 힘" 카드.

**Acceptance**:
- [ ] `recurring: "monthly"` 옵션 선택 시 UI에 "매월 X일 자동 매수" 문구 표시
- [ ] 차트에 매수 시점 마커(dot) 오버레이
- [ ] 투자원금 vs 현재가치 이중 라인 (원금은 계단식, 가치는 연속)

### Out of Scope (의도적으로 제외)

| 제외 항목 | 이유 |
|----------|------|
| 세금 자동 반영 (양도세/배당세) | v2 이월 — 별도 "양도세 계산기"와 독립 유지 |
| 배당 재투자 (DRIP) | v1.5 이월 — 첫날은 가격 기반 단순 계산만 |
| 한국 주식 (KOSPI/KOSDAQ) | v1.1 이월 — KIS API 과거 시세 일별 쿼터 제약, Alpaca/FMP 우선 |
| 멀티 종목 포트폴리오 | v2 이월 — 1종목만, "포트폴리오 스트레스 테스트"와 혼동 방지 |
| 실시간 가격 | N/A — 전일 종가 기준으로 충분 (면책에 명시) |
| 인증 필요 | **없음** — 비로그인 바이럴 페이지 (획득 후크 핵심) |
| 결과 DB 저장 | v1에서 **저장 안 함** — URL 쿼리스트링 기반 재현 (`?t=NVDA&d=2020-03-23&a=5000000`) |
| 레버리지/옵션 시뮬 | 영구 제외 — 자본시장법 리스크 |

### Edge Cases

| 케이스 | 처리 |
|--------|------|
| 티커 존재하나 해당 날짜 이전 상장 | "YYYY-MM-DD 상장. 시작일을 조정하세요" 에러 + 상장일 자동 제안 |
| 티커 상장폐지 | 마지막 거래일 종가로 계산 + "YYYY에 상장폐지" 배너 |
| 시작일 = 주말/공휴일 | 다음 거래일 가격 사용 (조용히 처리, 툴팁으로 고지) |
| 시작일 > 오늘 | "미래 날짜는 입력 불가" 즉시 밸리데이션 |
| 투자금액 음수 / 0 / 1조 초과 | `1원 ~ 10억원` 범위 외 거부 |
| 잘못된 티커 | Alpaca/FMP 404 → "티커를 찾을 수 없습니다. 예: AAPL, NVDA, TSLA" |
| 분할/병합 (stock split) | 기존 `data_fetcher`가 adjusted close 사용 가정 — **사전 확인 필수** |
| recurring=monthly인데 기간 < 1개월 | 자동 lump-sum으로 fallback + 안내 메시지 |
| Alpaca/FMP 429 (rate limit) | 백엔드 TTL 캐시 (24h, 티커+시작일 키) → 동일 요청 재사용 |
| 배당 제외 | 면책에 "배당 재투자 미반영" 명시, v1.5에서 토글 추가 예정 |

---

## 3. UI/UX

### 3.1 Information Architecture

```
Route: /simulator/what-if  (비로그인 접근 가능)

┌────────────────────────────────────────────────────┐
│  [PivoxQuant Logo]                    [로그인/가입]│
├────────────────────────────────────────────────────┤
│                                                    │
│        "만약에 샀다면?"                             │
│   Step 1  종목 검색  [AAPL          🔍]           │
│   Step 2  시작일     [2020-03-23  📅]             │
│   Step 3  투자금액   [500만원       💰]            │
│   Step 4  [반복매수] ○ 한번에  ● 매월  ○ 매주     │
│                                                    │
│            [ 계산하기 ]  ← 큰 CTA                  │
│                                                    │
├────────────────────────────────────────────────────┤
│ (결과 영역 — 계산 전 숨김)                          │
│                                                    │
│  [ 공유용 결과 카드 — 1080x1080 OG 이미지 프레임 ] │
│                                                    │
│  AAPL · 2020-03-23에 500만원 투자했다면           │
│                                                    │
│   현재가치                수익률                   │
│   38,420,000 원            +668.4%                │
│                                                    │
│   [차트: normalized 가격 라인 + 매수 포인트]       │
│                                                    │
│   Milestones                                       │
│   · 2021-01 — 원금 2배 달성 🎯                     │
│   · 2023-06 — +300% 돌파 🔥                        │
│   · 2025-11 — 최고점 기록                          │
│                                                    │
│   [📸 이미지로 저장]  [💬 카톡]  [𝕏 X]  [🔗 링크]   │
├────────────────────────────────────────────────────┤
│  면책: 과거 수익률 ≠ 미래 수익률. 배당·세금 미반영. │
│  본 서비스는 계산 도구이며 투자 추천이 아닙니다.   │
├────────────────────────────────────────────────────┤
│  "이 결과 마음에 들었다면 PivoxQuant으로 포트폴리오  │
│   관리 시작하기" [무료 가입] ← 전환 CTA           │
└────────────────────────────────────────────────────┘
```

### 3.2 Component Breakdown

| 컴포넌트 | 파일 경로 (제안) | 역할 |
|----------|------------------|------|
| `WhatIfPage` | `frontend/src/app/simulator/what-if/page.tsx` | 라우트 entry, SEO 메타, URL 쿼리 파싱 |
| `SimulatorForm` | `frontend/src/components/simulator/simulator-form.tsx` | 4-step 입력 폼 + 밸리데이션 |
| `TickerSearchInput` | `frontend/src/components/simulator/ticker-search-input.tsx` | 자동완성 (기존 `/api/stocks/search` 재활용) |
| `ResultCard` | `frontend/src/components/simulator/result-card.tsx` | 공유용 1080x1080 비율 카드 |
| `GrowthChart` | `frontend/src/components/simulator/growth-chart.tsx` | Recharts 기반 라인 + 매수 포인트 |
| `MilestoneList` | `frontend/src/components/simulator/milestone-list.tsx` | 2배/3배/최고점 등 이벤트 라벨 |
| `ShareBar` | `frontend/src/components/simulator/share-bar.tsx` | 4버튼 (이미지/카톡/X/링크) |
| `DisclaimerBanner` | 기존 재활용 | 면책 |

### 3.3 Design Principles

- **Sensible default**: 입력 필드 초기값 = `NVDA / 2020-03-23 / 500만원` (극적 결과 → WOW 효과)
- **Progressive disclosure**: 반복매수 토글 기본 OFF, 선택 시만 주기 노출
- **Error as conversation**: "2015-01-01 이전 데이터 없습니다 → 2015-02-01로 자동 조정할까요? [예/아니오]"
- **Mobile-first**: 스크린샷 공유는 모바일에서 90% 발생 → 1080x1080 정사각 카드
- **Micro-interactions**:
  - 숫자 카운트업 애니메이션 (0 → 38,420,000)
  - 수익률 +668% 는 `motion/react`로 0.8초에 걸쳐 증가
  - 차트 왼→오른 드로잉 (1.2초)
  - `prefers-reduced-motion` 존중

### 3.4 Viral Hooks ("와 미친다" 모먼트)

1. **동적 헤드라인**: 수익률 구간별 문구 자동 선택
   - > +1000%: "인생 역전 시나리오"
   - +500% ~ +1000%: "미친 수익률"
   - +100% ~ +500%: "2배 이상 달성"
   - +20% ~ +100%: "견조한 성장"
   - -10% ~ +20%: "박스권"
   - < -10%: "대안 시나리오"
   (모두 **추천/조언 언어 배제** — 결과 서술만)
2. **스크린샷 자동 워터마크**: 카드 우하단 `pivoxquant.com/what-if` 고정
3. **OG 이미지 서버 생성**: 공유 링크 클릭 시 X/카톡 썸네일에 결과 미리보기 노출 (`/api/og/what-if?t=NVDA&d=...`)
4. **비교 카드 (음수일 때)**: "같은 돈을 S&P500에 넣었다면 +45%" 자동 추가 → 재시도 유도
5. **"더 극적인 결과 보기"**: 홈페이지 하단 4개 큐레이션 프리셋
   - NVDA + 2020-03-23 코로나 바닥
   - AAPL + 2009-01-01 금융위기 후
   - TSLA + 2019-06-01 상승 직전
   - SPY + 2000-01-01 DCA 25년

### 3.5 Acceptance Criteria (Formal)

- [ ] Given 비로그인 유저 When `/simulator/what-if` 접속 Then 로그인 벽 없이 즉시 입력 가능
- [ ] Given 유효 입력 When 계산 클릭 Then 3초 이내 결과 카드 렌더 (TTI < 3s)
- [ ] Given 결과 표시됨 When URL 확인 Then 쿼리스트링에 `?t={ticker}&d={date}&a={amount}&r={recurring}` 포함
- [ ] Given 공유 URL 방문 When 페이지 로드 Then 입력값 자동 복원 + 결과 자동 계산
- [ ] Given 공유 URL When X/카톡에서 미리보기 Then OG 이미지에 결과 요약 노출
- [ ] Given 음수 수익률 When 결과 표시 Then S&P500 벤치마크 비교 자동 추가
- [ ] Given 모바일 viewport (375px) When 렌더 Then 1080x1080 카드가 2x 스케일로 onscreen 캡처 가능
- [ ] Given 에러 (잘못된 티커 등) When 발생 Then 해결책 제시 문구 표시 (에러 코드만 X)
- [ ] Given recurring=monthly + 기간 1개월 미만 When 계산 Then lump-sum으로 자동 전환 + 안내
- [ ] Given 면책 배너 When 페이지 로드 Then 결과 카드 바로 아래 필수 노출 (접기 불가)

---

## 4. 기술 스펙

### 4.1 Backend — 신규 엔드포인트

**Route**: `POST /api/simulate/counterfactual` (또는 `GET` with query for shareable URL)
**Blueprint**: `routes/simulate_bp.py` (신규 생성)
**Auth**: 불필요 (비로그인 허용)
**Rate limit**: 30/min per IP (security.py 재활용)

#### Request Schema
```json
{
  "ticker": "NVDA",
  "start_date": "2020-03-23",
  "amount": 5000000,
  "recurring": "monthly"   // "monthly" | "weekly" | null
}
```

#### Response Schema
```json
{
  "success": true,
  "input": {
    "ticker": "NVDA",
    "start_date": "2020-03-23",
    "amount": 5000000,
    "recurring": "monthly"
  },
  "result": {
    "invested_total": 5000000,
    "end_value": 38420000,
    "profit_loss": 33420000,
    "return_pct": 668.4,
    "annualized_return_pct": 58.2,
    "duration_days": 1483,
    "shares_total": 128.5,
    "first_buy_price": 38.92,
    "last_price": 298.99,
    "last_price_date": "2026-04-13"
  },
  "chart_data": [
    {"date": "2020-03-23", "price": 38.92, "invested": 5000000, "value": 5000000, "buy_point": true},
    {"date": "2020-04-23", "price": 45.10, "invested": 5000000, "value": 5793000, "buy_point": false},
    // ... 일별 또는 주별 샘플링
  ],
  "milestones": [
    {"date": "2021-01-12", "label": "원금 2배 달성", "type": "multiplier", "value": 2},
    {"date": "2023-06-03", "label": "+300% 돌파", "type": "threshold", "value": 300},
    {"date": "2025-11-09", "label": "역대 최고가 도달", "type": "ath", "value": null}
  ],
  "benchmark": {   // 음수 수익률일 때만 포함
    "ticker": "SPY",
    "end_value": 7250000,
    "return_pct": 45.0
  },
  "disclaimers": [
    "과거 수익률이 미래 수익률을 보장하지 않습니다",
    "배당금 재투자는 반영되지 않습니다",
    "세금/수수료는 반영되지 않습니다",
    "본 서비스는 정보 제공 도구이며 투자 추천이 아닙니다"
  ]
}
```

#### Error Response
```json
{
  "success": false,
  "error_code": "TICKER_NOT_FOUND" | "DATE_BEFORE_LISTING" | "DATE_IN_FUTURE" | "AMOUNT_OUT_OF_RANGE" | "DATA_UNAVAILABLE",
  "message": "티커를 찾을 수 없습니다. 예: AAPL, NVDA, TSLA",
  "suggestion": {  // optional
    "field": "start_date",
    "value": "2015-02-01",
    "reason": "2015-02-01 상장일 이후 날짜를 사용하세요"
  }
}
```

### 4.2 Backend — 시뮬레이션 로직 (의사코드)

```python
# services/counterfactual_service.py (신규)

def simulate(ticker, start_date, amount, recurring=None):
    # 1. 밸리데이션
    validate_ticker(ticker)
    validate_date_range(start_date)          # 오늘 이전, 1990년 이후
    validate_amount(amount)                  # 1원 ~ 10억원

    # 2. 가격 히스토리 가져오기 (기존 재활용)
    prices = data_fetcher.get_price_history(
        ticker=ticker,
        start=start_date,
        end=today(),
        adjusted=True    # split/dividend 보정된 종가
    )
    if not prices or prices[0].date > start_date + 5days:
        raise DateBeforeListingError(suggestion=prices[0].date)

    # 3. 매수 시나리오 생성
    if recurring is None:
        buys = [Buy(date=start_date, amount=amount)]
    elif recurring == "monthly":
        buys = generate_monthly_buys(start_date, today(), amount)
    elif recurring == "weekly":
        buys = generate_weekly_buys(start_date, today(), amount)

    # 4. 매 거래일별 포트폴리오 가치 계산
    shares_held = 0
    invested_total = 0
    chart_data = []
    for day in prices:
        # 오늘이 매수일이면 사기
        if any(b.date == day.date for b in buys):
            buy = next(b for b in buys if b.date == day.date)
            shares_bought = buy.amount / day.price
            shares_held += shares_bought
            invested_total += buy.amount
            buy_point = True
        else:
            buy_point = False

        current_value = shares_held * day.price
        chart_data.append({
            "date": day.date,
            "price": day.price,
            "invested": invested_total,
            "value": current_value,
            "buy_point": buy_point
        })

    # 5. 요약 통계
    end_value = chart_data[-1].value
    return_pct = (end_value - invested_total) / invested_total * 100
    annualized = cagr(invested_total, end_value, duration_years)

    # 6. 마일스톤 추출
    milestones = extract_milestones(chart_data, invested_total)
    # - 원금 2/3/5/10배 최초 도달일
    # - +100/200/500/1000% 최초 돌파일
    # - 최대 낙폭 시점
    # - 기간 중 최고가 시점

    # 7. 벤치마크 (음수 수익률일 때만)
    benchmark = None
    if return_pct < 0:
        benchmark = simulate_spy_equivalent(start_date, buys)

    # 8. 샘플링 (너무 많으면 응답 무거움)
    if len(chart_data) > 500:
        chart_data = downsample_to(chart_data, 500)

    return {
        "result": {...},
        "chart_data": chart_data,
        "milestones": milestones,
        "benchmark": benchmark,
        "disclaimers": [...]
    }
```

### 4.3 Backend — 캐싱 전략

- **Key**: `counterfactual:{ticker}:{start_date}:{amount}:{recurring}`
- **TTL**: 24시간 (일봉 종가 기준이므로 장 마감 후만 갱신)
- **Storage**: 기존 `services/cache.py` (Redis or in-memory fallback) 재활용
- **목적**: Alpaca/FMP rate limit 회피 + 바이럴 확산 시 동일 링크 N만 회 요청 대응

### 4.4 Backend — OG 이미지 서버

**Route**: `GET /api/og/what-if?t=NVDA&d=2020-03-23&a=5000000&r=monthly`
**응답**: `image/png` 1200x630 (X/카톡/페이스북 표준)
**구현 옵션**:
- **Option A (권장)**: Next.js App Router의 `opengraph-image.tsx` (`@vercel/og`) — 프론트엔드에서 처리, 백엔드 부담 X
- **Option B**: Flask + Pillow — 복잡, 스프린트 범위 초과
- **결정**: **Option A** 채택 — 1일 스프린트에 적합

**파일**: `frontend/src/app/simulator/what-if/opengraph-image.tsx`

### 4.5 Frontend — 라우트 + 상태

```
/simulator/what-if                          # 메인 시뮬레이터
/simulator/what-if?t=NVDA&d=2020-03-23&a=5000000&r=monthly   # 공유 URL
```

**상태 관리**: URL 쿼리스트링이 single source of truth
- 폼 submit → URL 업데이트 (`router.push` with shallow) → useEffect로 API 호출
- 페이지 재진입 시 쿼리스트링에서 폼 복원 + 자동 계산
- **DB 저장 없음** (v1)

**API 클라이언트**: `lib/endpoints.ts`에 추가
```ts
export const SIMULATE_COUNTERFACTUAL = `${API_BASE}/api/simulate/counterfactual`;
```

**SWR 훅**: `lib/hooks.ts`에 추가
```ts
export function useCounterfactual(params) {
  const { data, error, isLoading } = useSWR(
    params ? [SIMULATE_COUNTERFACTUAL, params] : null,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 86400000 }
  );
  return { data, error, isLoading };
}
```

### 4.6 Frontend — Share 구현

| 채널 | 구현 |
|------|------|
| **이미지 저장** | `html-to-image` 라이브러리로 결과 카드 DOM → PNG 다운로드 |
| **카톡** | `https://accounts.kakao.com/login` 없이 **링크 공유 API** — `Kakao.Share.sendDefault()` 또는 단순 URL copy → "카톡에 붙여넣기" 안내 (Kakao JS SDK 초기 세팅 부담 → **v1은 URL 복사 only** 권장) |
| **X (Twitter)** | `https://twitter.com/intent/tweet?text={encoded}&url={shareUrl}` |
| **URL 복사** | `navigator.clipboard.writeText(shareUrl)` + 토스트 "복사됨" |

**v1 스코프 제안**: URL 복사 + X + 이미지 저장 3개만. 카톡 공유는 v1.1 (SDK 세팅 0.5일 필요).

### 4.7 Chart Library

- **Recharts** (이미 PivoxQuant에서 사용 중) 또는 **Chart.js**
- 기존 프로젝트 chart 의존성 확인 후 통일 (현재 `lightweight-charts` 제거됨 per CLAUDE.md → Recharts가 남은 것으로 추정)
- 요구사항:
  - Line chart (2줄: 투자원금 계단식, 포트폴리오 가치 연속)
  - `buy_point: true`인 점에 Dot 마커
  - Milestone 시점에 ReferenceLine + 라벨
  - 툴팁에 `날짜 / 투자원금 / 가치 / 수익률`

### 4.8 SEO (바이럴 확산용)

- `metadata`: 동적 (쿼리스트링 기반)
  - title: `"NVDA를 2020-03-23에 500만원 샀다면 | PivoxQuant What-If"`
  - description: `"현재가치 38,420,000원 (+668.4%). 직접 계산해보세요."`
- JSON-LD: `WebApplication` 스키마
- 사전 렌더 정적 프리셋 페이지 3–5개 (SEO 키워드: "엔비디아 과거 수익률", "애플 10년 전 샀으면")
  - `/simulator/what-if/preset/nvda-covid-crash`
  - `/simulator/what-if/preset/aapl-2010`

---

## 5. 합법성 (자본시장법 / 저작권)

### 5.1 언어 규칙

| 금지 | 대체 |
|------|------|
| "추천", "매수하세요", "이 종목은 유망합니다" | "과거 결과를 보여줍니다", "계산 결과" |
| "BUY", "SELL", "HOLD" 라벨 | 단순 수치 (가격, 수익률)만 |
| "AI Coach가 분석했습니다" | (AI 미사용, 순수 계산만) |
| "지금이 매수 타이밍" | "과거의 가상 매수 시점입니다" |
| "후회하지 마세요" (감정 유도) | "결과를 확인해보세요" |

### 5.2 면책문 (필수, 결과 카드 바로 아래)

```
⚠️ 본 시뮬레이터는 과거 공개 시세 데이터를 기반으로 한 계산 도구입니다.
• 과거 수익률이 미래 수익률을 보장하지 않습니다
• 배당금 재투자, 세금, 거래 수수료는 반영되지 않습니다
• 본 서비스는 투자 추천 또는 조언이 아니며, 특정 종목의 매수/매도를 권유하지 않습니다
• 모든 투자 결정과 책임은 이용자 본인에게 있습니다
```

### 5.3 저작권

- 가격 데이터 출처: **Alpaca Markets** (약관상 표시/계산 목적 허용) + **FMP** ($29 Starter 티어, 상업적 사용 허용)
- 결과 차트/이미지: PivoxQuant 자체 렌더 → 저작권 PivoxQuant 보유
- 하단 크레딧: "Market data: Alpaca & FMP" 표기

### 5.4 포지셔닝 (자본시장법 회피)

- **투자자문업 미해당 근거**: 단순 과거 가격 계산기 (= 복리 계산기, DCA 시뮬레이터와 동일 범주)
- **유사투자자문업 미해당 근거**: 불특정 다수에게 "특정 종목 매수"를 권유하지 않음 — 유저가 직접 티커를 입력
- **안전 비교 대상**: Yahoo Finance `Compare`, Investing.com `Historical Simulator`, Portfolio Visualizer `Backtest` — 모두 한국 유저에게 동일 기능 제공 중 (법적 이슈 전무)

### 5.5 법무부 사전 검토 필요 사항 (1일 스프린트 전)

- [ ] 면책문 한글+영문 최종안 승인
- [ ] "추천/조언" 단어 grep 체크 (모든 UI 문구)
- [ ] 하단 크레딧 표기 승인 (Alpaca, FMP 약관)

---

## 6. Success Metrics

### Primary (핵심 지표)
- **D1 바이럴 계수**: 공유 URL에서 신규 방문 유저 수 / 최초 계산 유저 수 (목표 ≥ 0.5)
- **비로그인 → 가입 전환율**: 시뮬레이터 사용 후 회원가입까지 (목표 ≥ 3%, 첫 달)
- **공유 버튼 클릭률**: 결과 본 유저 중 (목표 ≥ 20%)

### Secondary (보조 지표)
- Shareable URL 방문 세션 비율 (쿼리스트링 있음)
- 평균 세션 체류 시간 (목표 ≥ 60초)
- OG 이미지 노출 수 (Vercel Analytics)
- 반복 매수 옵션 사용률 (DCA 교육 효과)
- 모바일 vs 데스크톱 비율 (예상 모바일 70%)

### Failure Signal (이 지표가 이러면 실패)
- D7 공유율 < 5% → 바이럴 가설 실패, 피쳐 깊이 추가 필요
- 에러율 > 10% → 데이터 파이프라인 이슈
- 가입 전환 < 1% → CTA 재설계 필요
- 법적 컴플레인 1건이라도 발생 → 즉시 문구/포지셔닝 수정

### PostHog 이벤트 (구현 필수)
- `simulator_opened`
- `simulator_calculated` (props: ticker, duration_days, recurring, return_pct_bucket)
- `simulator_share_clicked` (props: channel)
- `simulator_share_url_visited`
- `simulator_signup_from_cta`
- `simulator_error` (props: error_code)

---

## 7. Dependencies

### 기술 의존성
- ✅ `data_fetcher.get_price_history()` (기존) — Alpaca adjusted close 확인 필요
- ✅ `services/cache.py` (기존)
- ✅ `security.py` (기존 rate limit)
- ⚠️ `html-to-image` npm 패키지 (신규 추가, < 10KB)
- ⚠️ `@vercel/og` (Next.js App Router에 내장, 확인 필요)
- ❓ Recharts vs Chart.js — 프로젝트 현황 조사 필수 (30분)

### 디자인 의존성
- ✅ 기존 `--sp-*` 색상 토큰 재활용 (purple/blue/pink gradient)
- ⚠️ 신규: 결과 카드 1080x1080 레이아웃 (디자인부 와이어프레임 1h)
- ⚠️ 신규: OG 이미지 1200x630 레이아웃

### 법무 의존성
- ⚠️ 면책문 한글+영문 — 법무부 사전 승인
- ⚠️ "후회" → "What-If" 네이밍 최종 확정

### 데이터 의존성
- ⚠️ Alpaca historical 데이터 범위 (티커별 상장일 메타 필요)
- ⚠️ FMP 백업 경로 동작 확인 (2026-04-14 현재 402 에러 이슈 있음 per CLAUDE.md)

### 외부 의존성 (스프린트 외)
- CEO의 Google/Kakao OAuth 설정 (시뮬레이터는 비로그인이라 직접 의존 X, 하지만 "가입 CTA" 클릭 후 경로에 필요)

---

## 8. User Stories

### 초보 투자자 (미시작)
> 주식 시작할까 말까 고민하는 대학생으로서,
> "내가 1년 전에 100만원을 S&P500에 넣었다면 얼마일까"를 알고 싶다,
> 왜냐하면 실제 돈을 넣기 전에 감을 잡고 싶기 때문이다.

### MZ 투자자 (초/중급)
> 미장 3년차 직장인으로서,
> "코로나 폭락에 NVDA 샀으면 지금 얼마"를 계산해 친구에게 공유하고 싶다,
> 왜냐하면 친구와의 수다 + 나의 다음 투자 교훈으로 쓰고 싶기 때문이다.

### DCA 전도사 (파워)
> 월 50만원 SPY DCA 하는 3년차 투자자로서,
> "내가 한 방에 넣었으면 vs 나눠 넣은 지금"을 비교하고 싶다,
> 왜냐하면 내 전략이 맞았는지 검증하고, 블로그에 글을 쓰기 위해서이다.

### 바이럴 공유자
> X/인스타에서 "주식" 콘텐츠 만드는 크리에이터로서,
> "엔비디아 10년 전 샀으면 ㄹㅇ 미친" 짤을 만들고 싶다,
> 왜냐하면 내 팔로워에게 교육적이면서 화제성 있는 콘텐츠가 필요하기 때문이다.

---

## 9. 1일 스프린트 시간표 (8 hours)

### Pre-Sprint (전날 or 오전 7:00–9:00, 2h) — **선결 조건**
- [ ] **CEO**: 법무부 에이전트에 면책문 한글+영문 최종 검토 요청 (15분)
- [ ] **CEO**: 네이밍 확정 ("What-If" / "만약에 샀다면")
- [ ] **Eng**: `data_fetcher.get_price_history()` adjusted close 옵션 확인 (15분)
- [ ] **Eng**: Recharts 프로젝트 내 존재 여부 확인 (10분)
- [ ] **Eng**: FMP 402 에러가 historical price에 영향 있는지 확인 (30분)
- [ ] **Design**: 결과 카드 1080x1080 와이어프레임 1개 (1h, Figma or Whimsical)

### AM Block — Backend (09:00–13:00, 4h)

| 시간 | 작업 | 산출물 |
|------|------|--------|
| 09:00–09:30 | `routes/simulate_bp.py` 스캐폴딩 + app.py 등록 | 엔드포인트 hello world 응답 |
| 09:30–10:30 | `services/counterfactual_service.py` 코어 시뮬 로직 | lump-sum 시뮬 동작 |
| 10:30–11:00 | `recurring` (monthly/weekly) 분기 처리 | DCA 시뮬 동작 |
| 11:00–11:30 | Milestone 추출 로직 (2배/3배/ATH/MaxDD) | 마일스톤 JSON 반환 |
| 11:30–12:00 | 벤치마크 비교 (SPY) — 음수 수익률일 때만 | 조건부 benchmark 필드 |
| 12:00–12:30 | 에러 핸들링 + 밸리데이션 (7가지 edge case) | 400/404 에러 응답 |
| 12:30–13:00 | TTL 캐싱 적용 + 단위 테스트 (3 시나리오) | pytest pass |

### PM Block — Frontend (14:00–18:00, 4h)

| 시간 | 작업 | 산출물 |
|------|------|--------|
| 14:00–14:30 | `/simulator/what-if/page.tsx` 라우트 + SEO 메타 | 빈 페이지 렌더 |
| 14:30–15:30 | `SimulatorForm` 4-step 입력 + `TickerSearchInput` | 폼 submit 동작 |
| 15:30–16:00 | `useCounterfactual` SWR 훅 + URL 쿼리 동기화 | API 호출 + 상태 관리 |
| 16:00–16:45 | `ResultCard` + 카운트업 애니메이션 | 결과 표시 |
| 16:45–17:15 | `GrowthChart` (Recharts) + 매수 포인트 + Milestone 라인 | 차트 렌더 |
| 17:15–17:45 | `ShareBar` (URL 복사 + X 공유 + 이미지 저장) | 공유 3채널 동작 |
| 17:45–18:00 | OG 이미지 (`opengraph-image.tsx` via `@vercel/og`) | SNS 미리보기 |

### Post-Sprint (18:00–19:00, 1h) — **검증**
- [ ] 3개 시나리오 수동 QA (NVDA/TSLA/SPY DCA)
- [ ] 모바일 반응형 375px/414px 확인
- [ ] 면책 배너 노출 확인
- [ ] 에러 케이스 5개 수동 테스트 (잘못된 티커, 미래 날짜 등)
- [ ] PostHog 이벤트 6개 fire 확인
- [ ] Lighthouse 퍼포먼스 점수 ≥ 85
- [ ] 카톡/X/문자에서 공유 URL 미리보기 확인

### Deferred (다음 스프린트)
- Kakao JS SDK 연동 (카톡 공유 버튼)
- 한국 주식 (KIS) 지원
- 배당 재투자 토글
- 프리셋 5개 (SEO 랜딩)
- Paper Trading 모드 연계 ("이 결과대로 가상 계좌에 반영")

---

## 10. Go/No-Go Criteria (스프린트 종료 시)

### Go (출시)
- [ ] 3개 시나리오 모두 정상 동작
- [ ] 면책 배너 노출
- [ ] 공유 URL 쿼리스트링 왕복 동작
- [ ] 모바일 UI 깨짐 없음
- [ ] 에러 응답에 해결책 제시 문구 존재
- [ ] Lighthouse ≥ 85

### No-Go (출시 보류)
- 데이터 정확도 이슈 (adjusted close 안 됐거나, 특정 티커 계산 오류)
- 면책 누락
- "추천/조언" 단어 1개라도 노출
- 계산 응답 > 5초
- 결과 카드가 스크린샷 시 일부 잘림

### Rollback Plan
- 라우트 자체를 Feature Flag로 off (`NEXT_PUBLIC_ENABLE_WHATIF=false`)
- 백엔드 엔드포인트는 404 반환
- 피해 범위: 미배포 페이지 → 유저 영향 0

---

## 11. Post-Launch (v1 출시 후 2주 관찰)

### Week 1
- 공유 URL 방문 비율 측정
- 상위 10개 인기 티커 로그 수집 → 프리셋 SEO 페이지 제작
- 에러율 모니터링

### Week 2
- 전환율 계산 (시뮬레이터 → 가입)
- A/B 테스트:
  - CTA 문구 ("무료 가입" vs "내 포트폴리오 만들기")
  - 결과 카드 배치 (중앙 vs 우측 고정)
- v1.1 기능 우선순위 결정

---

## 12. Summary (한 장)

| 항목 | 내용 |
|------|------|
| 제품 한 줄 | "당신이 X년 전에 Y주식에 Z만원 넣었으면 지금 W원" — 1분 계산 + 1장 공유 |
| 타겟 | 20–30대 MZ 미장 투자자 + 예비 유저 (바이럴) |
| 핵심 가치 | 과거 시나리오 시각화 + 스크린샷 공유 + 무료 획득 후크 |
| 차별화 | 한국어 + 모바일 공유 카드 + DCA 시뮬 + 네거티브 자동 비교 |
| 범위 | 1종목, 미국 주식, 비로그인, 가격 기반만 |
| 1일 스프린트 | Backend 4h + Frontend 4h + QA 1h |
| 의존성 | 기존 `data_fetcher` + Recharts + @vercel/og + 법무부 사전 검토 |
| 법적 포지션 | "단순 계산기" — 자본시장법 회피, DCA 시뮬레이터와 동일 범주 |
| 주요 지표 | D1 바이럴 0.5 / 전환 3% / 공유률 20% |
| 리스크 | FMP 402 에러 영향 가능성 (사전 확인 필수), Kakao 공유 v1.1로 deferred |

---

**프로덕트부 판단**: 이 스펙은 1일 스프린트로 완결 가능하며, safe-features-brainstorm.md의 Score 20.0 DCA 시뮬레이터를 **바이럴 획득 후크 전용**으로 재설계한 것입니다. PivoxQuant 코어 대시보드의 P0 버그(Portfolio/Search/Watchlist)와 독립된 신규 라우트라서 기존 UX 회복 작업과 병렬 진행 가능합니다. CEO 승인 시 다음 엔지니어링 에이전트에 구현 위임 권장.

> 최종 서명: Head of Product — 2026-04-14
