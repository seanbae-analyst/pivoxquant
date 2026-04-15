# Tools 섹션 개선 계획
작성일: 2026-04-10

## 개요

Tools 드롭다운 하위 10개 페이지(Optimizer, Sector Rotation, Kelly Sizing, Backtest, Dividends, Tax, Earnings, News, Peers, Copy Trading) 전체를 코드 기반으로 분석한 결과다. 각 페이지의 현재 상태, 결함, 개선 방향을 정리한다.

---

## 공통 문제 (모든 페이지에 해당)

### 1. 디자인 시스템 불일치 — 심각도: HIGH
- Optimizer, Kelly, Tax, Copy Trading은 `text-slate-900` / 라이트 배경 컴포넌트 사용
- Sector Rotation, Backtest, Dividends, Earnings, News, Peers는 `text-white` / `text-zinc-*` 다크 테마
- 같은 `glass-surface` 클래스를 쓰지만 폰트 색이 완전히 달라 한 화면에서 두 테마가 공존함
- **개선**: 전 페이지 `text-[#F2F2F7]` / `text-[#8E8EA0]` 계열로 통일. 라이트 테마 컴포넌트(`bg-slate-50`, `border-slate-200`, `text-slate-900`) 제거

### 2. 페이지 진입점이 불명확 — 심각도: MEDIUM
- 어떤 페이지에서는 포트폴리오 보유 종목 기준, 어떤 페이지는 수동 검색 기준인지 유저가 알 수 없음
- 페이지 상단에 "이 페이지는 당신 포트폴리오 기반" vs "임의 종목 분석 가능" 구분이 없음
- **개선**: 각 페이지 헤더 아래에 컨텍스트 배지 추가 ("포트폴리오 연동" / "수동 입력")

### 3. 빈 상태(Empty State) 일관성 부재 — 심각도: MEDIUM
- 페이지마다 빈 상태 처리 방식이 다름 (어떤 곳은 아이콘+텍스트, 어떤 곳은 텍스트만)
- 행동 유도(CTA)가 없음. "포트폴리오에 종목을 추가하세요"라고만 하고 링크 없음

### 4. 면책 조항 처리 — 심각도: LOW
- Optimizer, Kelly, Backtest는 하단에 disclaimer 섹션 존재
- Dividends, Tax는 마지막 텍스트로만 처리
- Earnings, Peers에는 disclaimer 없음
- **개선**: 공통 `DisclaimerBanner` 컴포넌트로 통일 (Backtest 페이지에는 이미 존재)

---

## 페이지별 분석

---

### 1. Optimizer (`/optimizer`)

**현재 구성요소**
- 4개 메트릭 카드 (포지션 수, 현재 Sharpe, 예상 Sharpe 향상, 분산화 이득)
- Bar Chart: 현재 vs 최적 배분 비교
- Weight Comparison 테이블 (현재 % → 최적 %)
- Rebalancing Actions 목록
- Expected Improvements 카드
- About 섹션

**문제점**
1. **Top 5 고정 한계**: `sorted.slice(0, 5)` — 5개 이상 종목을 가진 유저는 나머지 종목의 최적화가 이뤄지지 않음. 유저에게도 "상위 5개만 분석됨"이라는 경고가 충분히 보이지 않음
2. **점수 의존 최적화의 한계 미노출**: 최적 배분이 score에만 의존하는데, score가 낮은 종목은 무조건 줄이라고 나옴. 유저가 score 의미를 모르면 잘못 해석 가능
3. **Rebalancing Actions에 실행 버튼 없음**: "Buy $X" 액션 카드가 있지만 클릭 시 아무것도 안 됨. Autotrade 또는 Buy 모달과 연결되어야 함
4. **Chart 범례 없음**: 파란 바 두 개가 있는데 Chart 아래 범례가 있긴 하지만 Bar chart 내부에 레이블이 없어 바 위에 hover해야만 구분 가능
5. **디자인 불일치**: `text-slate-900`, `border-slate-200` — 라이트 테마 잔재

**개선 방향**
- Top N 분석 (기본값 5, 파워유저는 전체)을 드롭다운으로 선택 가능하게
- Rebalancing Action 카드에 "Buy on Autotrade" 또는 "Quick Buy" 버튼 연결
- Score 설명 tooltip 추가 (score가 뭔지 모르는 초보 유저를 위해)
- 다크 테마 통일

**구현 난이도**: 쉬움 (디자인 통일) / 보통 (실행 버튼 연결)

---

### 2. Sector Rotation (`/sector-rotation`)

**현재 구성요소**
- VIX 기반 레짐 감지 (Bull/Neutral/Bear) + 배지
- 4개 메트릭 카드 (VIX, 추천 Exposure, 조정 필요 섹터 수, 섹터 커버리지)
- Horizontal Bar Chart: 현재 vs 추천 배분
- Action Items 패널 (조정 필요 섹터 목록)
- Sector Allocation Detail 테이블 (라이브 가격 포함)

**문제점**
1. **섹터 타겟이 하드코딩**: `SECTOR_TARGETS` 배열이 코드에 고정. Bull/Neutral/Bear 비율이 가정치이며 근거가 유저에게 노출되지 않음
2. **Action Items에 실행 버튼 없음**: "Increase Technology" 카드에 클릭 시 아무것도 없음
3. **VIX 출처 불명**: `useVixStrategy()` 훅에서 VIX를 가져오는데, 실시간인지 지연 데이터인지 표시 없음
4. **레짐 히스토리 없음**: 현재 레짐만 보여주고, 최근 레짐 변화 이력(예: "2주 전부터 Bear") 없음
5. **섹터 ETF 연결 없음**: "Technology 늘려라"라고 할 때 QQQ, XLK 같은 ETF 제안이 없어 실행 불가

**개선 방향**
- 섹터별 대표 ETF 매핑 추가 (Technology → QQQ/XLK, Healthcare → XLV 등)
- Action Item에 "해당 ETF 보기" 링크 연결
- VIX 데이터 타임스탬프 노출
- 레짐 변화 히스토리 미니 타임라인 추가 (최근 4주)

**구현 난이도**: 쉬움 (ETF 매핑, 타임스탬프) / 보통 (레짐 히스토리)

---

### 3. Kelly Sizing (`/kelly`)

**현재 구성요소**
- 3개 메트릭 카드 (Kelly 최적 배분, 현재 배분, 편차)
- Risk Meter (게이지 바)
- Custom Calculator (Win Rate + R Ratio 입력 → Kelly % 결과)
- Position Sizing Table (종목별 Kelly %)
- About 섹션

**문제점**
1. **Win Rate를 Score로 대체**: `w = pos.score / 100`으로 win rate를 계산함. Score가 70이면 win rate 70%로 취급하는데, 이는 개념적으로 부정확. Score는 시그널 강도이지 실제 승률이 아님
2. **기본 R Ratio = 2.0 고정**: TP/SL이 없으면 자동으로 2.0 적용. 유저가 설정 안 했을 경우 "R = 2.0 기본값 사용됨" 경고 표시가 없음
3. **Risk Meter 가독성**: 게이지 바에 레이블이 작고, "over-allocated"가 왜 문제인지 설명이 없음
4. **Custom Calculator와 Position Table 분리**: 커스텀 계산기 결과가 아래 테이블과 연동되지 않음. 사용자가 파라미터 바꿔도 테이블 업데이트 안 됨
5. **디자인 불일치**: 라이트 테마 잔재 (`text-slate-900`)

**개선 방향**
- "Win Rate로 Score 사용 중" 인라인 경고 + score 해석 도움말
- TP/SL 미설정 종목에 "기본값 R=2.0 적용됨" 인디케이터 표시
- Custom Calculator의 파라미터를 Position Table에 일괄 적용하는 "테이블에 적용" 버튼
- 다크 테마 통일

**구현 난이도**: 쉬움

---

### 4. Backtest (`/backtest`)

**현재 구성요소**
- Ticker 입력 + Run 버튼
- DisclaimerBanner 컴포넌트 (이미 존재)
- 결과: 8개 메트릭 카드 (Total Return, Annual Return, Sharpe, Max Drawdown, Win Rate, Total Trades, Avg Win, Avg Loss)
- Equity Curve (Area Chart)
- Trade Summary 패널 (Win/Loss/Ratio/Profit Factor)

**문제점**
1. **전략 선택이 없음**: 백테스트가 어떤 전략(MA 크로스오버인지, PivoxQuant 자체 시그널인지)으로 돌아가는지 명시되지 않음. 유저 입장에서 블랙박스
2. **기간 선택이 없음**: `result.period`는 표시되지만 유저가 기간을 선택할 수 없음 (1년/3년/5년/전체)
3. **벤치마크 비교 없음**: S&P500 대비 알파를 보여주지 않음. 단독 수익률만 보여줘서 맥락이 없음
4. **결과 히스토리가 없음**: 여러 번 실행해도 마지막 결과만 남음. 여러 종목 비교 불가
5. **Equity Curve에 드로다운 구간 표시 없음**: 언제 Max Drawdown이 발생했는지 시각화 없음

**개선 방향**
- 기간 선택 버튼 추가 (1Y / 3Y / 5Y / Max) — 백엔드 API가 이미 기간 파라미터를 지원하는지 확인 필요
- 전략 설명 tooltip 또는 info 배너 추가
- 마지막 3개 결과 비교 테이블 (Backtest History)
- S&P500 벤치마크 라인 Equity Curve에 오버레이

**구현 난이도**: 쉬움 (기간 버튼, 히스토리) / 어려움 (벤치마크 오버레이 — 별도 API 필요)

---

### 5. Dividends (`/dividends`)

**현재 구성요소**
- 4개 메트릭 카드 (연간 배당 USD/KRW, 포트폴리오 수익률, 월 수입, 배당 종목 수)
- Monthly Dividend Projection Bar Chart
- Position Dividend Table (종목별 배당 금액)

**문제점**
1. **섹터 평균 yield 하드코딩**: `US_SECTOR_YIELDS` 고정값 사용. 실제 배당 데이터 없이 추정만 함. Technology = 0.5%로 고정인데 AAPL과 MSFT의 실제 배당은 다름
2. **월별 예측이 수식적으로 분배됨**: `base * qBoost` 방식으로 분기별 부스팅. 실제 배당 지급 월을 반영하지 않음
3. **배당 성장률(Dividend Growth) 없음**: 5년 후 배당 수입이 얼마가 될지 예측 기능 없음
4. **"배당 재투자" 시나리오 없음**: DRIP 계산기가 없어 복리 효과 추정 불가
5. **빈 state가 `max-w-6xl` 밖에 있음**: `div className="mx-auto max-w-6xl"` 안에 컨텐츠가 있는데 empty state가 밖에 있어 레이아웃 불일치

**개선 방향**
- FMP API에서 실제 배당 yield 가져오기 (이미 fmp_service.py 존재)
- 배당 캘린더 뷰 추가 (어느 달에 어떤 종목이 배당을 주는지)
- DRIP 시뮬레이터 추가 (재투자 시 10년 후 예측)
- 레이아웃 정리 (`max-w-6xl` 래퍼 제거 또는 전체 통일)

**구현 난이도**: 보통 (실제 배당 데이터, 배당 캘린더) / 어려움 (DRIP 시뮬레이터)

---

### 6. Tax (`/tax`)

**현재 구성요소**
- 거주자 선택 토글 (Korean / US)
- 세금 규칙 설명 배너
- 3개 메트릭 카드 (미실현 수익, 예상 세금, 세후 순이익)
- Per-Position Breakdown 테이블
- "What if I sell now?" 섹션

**문제점**
1. **단기/장기 구분 없음 (한국 거주자)**: 미국주식은 보유 기간에 따라 한국 세금 계산이 달라지지 않지만, 미국 거주자의 경우 단기/장기 구분이 있음. 현재 코드는 모든 미국 거주자 포지션을 `long_term_rate`로 처리. `short_term_rate`가 상수에 정의되어 있지만 실제로 사용되지 않음
2. **보유 기간 데이터 없음**: Position에 `held_since` 또는 `purchase_date` 필드가 없어서 단기/장기 구분 불가
3. **Tax-Loss Harvesting 제안 없음**: 손실 포지션이 있으면 "이 종목을 매도하면 세금 절감 $X" 계산이 없음
4. **절세 전략 조언 없음**: 손실을 수익과 상계(netting)하는 전략 제안이 없음
5. **KRW/USD 표기 혼재**: Cost Basis, Current Value 컬럼이 항상 USD로 표시되는데 한국 거주자 선택 시 KRW로 보여줘야 일관성이 있음

**개선 방향**
- Tax-Loss Harvesting 섹션 추가: 손실 포지션 리스트와 수익 상계 시 절세액 계산
- 단기/장기 판단을 위한 보유기간 표시 (Position 데이터에 의존)
- 연말 절세 타이밍 알림 배너 (12월에 특히 강조)
- 한국 거주자 모드에서 KRW 우선 표시

**구현 난이도**: 쉬움 (Tax-Loss Harvesting 계산은 프론트에서 가능) / 보통 (보유 기간 데이터 필요)

---

### 7. Earnings (`/earnings`)

**현재 구성요소**
- 3개 메트릭 카드 (Upcoming 수, Next Report 날짜, BUY 등급 수)
- 주별 그룹화 타임라인 (This Week / Next Week / Upcoming / Past)
- 각 행: 날짜 배지 + Ticker + Score 바 + Signal 배지

**문제점**
1. **포트폴리오 종목만 표시**: 유저가 보유하지 않은 관심 종목의 실적 일정을 볼 수 없음. Watchlist 연동 없음
2. **예상 EPS/컨센서스 없음**: 날짜와 신호만 있고 컨센서스 EPS, 전분기 EPS, 예상 성장률이 없음
3. **발표 시간(Before/After Market) 없음**: 어떤 종목이 장전에 발표하는지, 장후에 발표하는지 없음
4. **과거 실적 히스토리 없음**: Past 그룹이 있지만 실제 발표된 EPS 결과(실제 vs 예상) 표시 없음
5. **필터 없음**: BUY 종목만 보기, 특정 주 보기 등 필터 기능 없음

**개선 방향**
- Watchlist 종목도 포함하는 옵션 추가
- 발표 시간 (BMO/AMC) 배지 추가
- 예상 EPS / 전분기 EPS 컬럼 추가
- Past 섹션에 실제 발표 결과 표시 (Beat/Miss/In-line 배지)

**구현 난이도**: 보통 (FMP API에서 earnings 데이터 확장 필요)

---

### 8. News (`/news`)

**현재 구성요소**
- 탭 필터 (All + 보유 종목 5개)
- 뉴스 카드 (제목, 요약, 출처, 날짜, 감성 배지)

**문제점**
1. **5개 종목 하드코딩**: `portfolio?.positions?.slice(0, 5)` — 6개 이상 보유 시 5개 이상 종목 뉴스를 볼 수 없음. 왜 5개인지 유저에게 설명 없음
2. **섹터 뉴스 없음**: 개별 종목 뉴스만 있고 "Technology 섹터 전반 뉴스"를 볼 수 없음
3. **마켓 뉴스 없음**: FOMC, 금리, 매크로 뉴스가 없음. 이미 Market 페이지에는 뉴스 섹션이 있는데 Tools > News는 더 좁은 범위
4. **뉴스 북마크/저장 없음**: 중요한 뉴스를 저장하는 기능 없음
5. **검색 없음**: 특정 종목이나 키워드로 뉴스를 검색할 수 없음
6. **뉴스 카드 이미지 없음**: 모든 뉴스가 텍스트 카드로만 표시되어 스캔하기 어려움

**개선 방향**
- 5개 제한 해제 + 보유 종목 전체 탭 제공
- Macro 탭 추가 (Fed, Rates, Economy 등)
- 검색창 추가 (포트폴리오 이외 종목도 검색 가능)
- 뉴스 카드에 소스별 파비콘 또는 섬네일 추가

**구현 난이도**: 쉬움 (제한 해제, 검색) / 보통 (매크로 뉴스 탭)

---

### 9. Peers (`/peers`)

**현재 구성요소**
- Ticker 검색 입력 + Compare 버튼
- 비교 테이블 (Ticker, Name, Price, Market Cap, P/E, Revenue Growth, Margin)

**문제점**
1. **시각화가 전혀 없음**: 텍스트 테이블만 있음. 가장 중요한 개선 필요 영역. P/E가 경쟁사 중 어디에 위치하는지 바 차트나 도트 플롯이 없음
2. **지표가 7개뿐**: P/E, Revenue Growth, Profit Margin 외에 P/S, EV/EBITDA, Debt/Equity, ROE, ROA 등이 없음
3. **내 포트폴리오 종목 자동 제안 없음**: 수동으로 티커를 입력해야 함. 포트폴리오 보유 종목 탭이 없음
4. **역사적 비교 없음**: 현재 스냅샷만 보여주고 6개월 전 대비 P/E 변화 같은 트렌드 없음
5. **컬럼 정렬 없음**: 테이블 헤더 클릭으로 정렬 불가

**개선 방향**
- 주요 지표별 수평 바 차트 비교 (레이더 차트 또는 플로팅 바)
- 컬럼 정렬 기능 (클릭 시 오름/내림차순)
- 포트폴리오 보유 종목 퀵 버튼 (수동 입력 없이)
- P/S, EV/EBITDA 컬럼 추가

**구현 난이도**: 쉬움 (정렬, 퀵 버튼) / 보통 (시각화 차트)

---

### 10. Copy Trading (`/copy-trading`)

**현재 구성요소**
- "Coming Soon" 배너
- 필터 (All / High Return / Low Risk / Most Followed)
- 트레이더 리더보드 테이블 (목 데이터 8명)
- Follow 버튼 (토글만 됨, 실제 기능 없음)
- 4개 통계 카드

**문제점**
1. **목 데이터 100%**: 실제 연동 없음. 모든 트레이더가 하드코딩된 가상 인물
2. **Follow 버튼이 아무 기능도 안 함**: 클릭해도 상태만 토글되고 아무 것도 저장되지 않음
3. **트레이더 상세 페이지 없음**: 리더보드 행을 클릭해도 전략 포트폴리오, 실적 차트를 볼 수 없음
4. **"Coming Soon" 배너가 있으면서 목 데이터를 보여주는 건 어색함**: 유저가 혼란스러울 수 있음 — 기능이 있는 건지 없는 건지 불명확
5. **product_features.md에서 Phase 3 기능으로 정의됨**: 현재 구현 단계에서 우선순위가 낮음

**개선 방향 (Phase 3 전까지 최소 처리)**
- 목 데이터를 완전히 제거하거나, 명확히 "이것은 예시입니다" 표시
- 또는 Coming Soon 페이지로만 교체 (빈 상태 + 대기자 명단 이메일 수집)
- Phase 3에서 실제 구현 시: 실제 유저 수익률 API, 팔로우 시 알림, 트레이더 상세 페이지

**구현 난이도**: 쉬움 (Coming Soon 전용 페이지로 교체)

---

## 우선순위 매트릭스

| 페이지 | 현재 완성도 | 개선 영향도 | 우선순위 |
|--------|------------|------------|---------|
| Backtest | 70% | 높음 (자주 쓰이는 기능) | P1 |
| News | 60% | 높음 (매일 사용) | P1 |
| Peers | 50% | 높음 (종목 분석 필수) | P1 |
| Tax | 65% | 중간 (절세 관심 높음) | P2 |
| Dividends | 60% | 중간 (배당 투자자) | P2 |
| Earnings | 70% | 중간 (시즌 때 높음) | P2 |
| Optimizer | 75% | 중간 (실행 연결 시 높아짐) | P2 |
| Sector Rotation | 75% | 중간 | P2 |
| Kelly | 70% | 낮음 (파워유저 전용) | P3 |
| Copy Trading | 20% | 낮음 (Phase 3) | P3 |

---

## P1 즉시 실행 개선 작업 (쉬움, 높은 영향도)

### A. 디자인 통일 (모든 페이지)
- Optimizer, Kelly, Tax, Copy Trading의 라이트 테마 클래스를 다크 테마로 변환
- `text-slate-900` → `text-[#F2F2F7]`
- `text-slate-400` → `text-[#8E8EA0]`
- `border-slate-200` → `border-white/[0.08]`
- `bg-slate-50` → `bg-white/[0.04]`

### B. Backtest 기간 선택 버튼 추가
- "1Y / 3Y / 5Y / Max" 버튼 추가
- 백엔드 `/api/backtest/{symbol}?period=1y` 형식으로 파라미터 전달 (백엔드 확인 필요)

### C. News 5개 제한 해제
- `slice(0, 5)` 제거 또는 "더 보기" 버튼으로 전체 탭 노출

### D. Peers 컬럼 정렬
- `useState`로 sortKey + sortDir 관리
- 테이블 헤더 클릭 핸들러 추가

### E. Copy Trading 정리
- 목 데이터 명확화 또는 Coming Soon 전용 페이지로 교체

---

## 산출물 파일 위치
- 분석 기반 파일: `/frontend/src/app/(dashboard)/[page]/page.tsx` (10개)
- 레이아웃 (Tools 그룹 정의): `/frontend/src/app/(dashboard)/layout.tsx`
- 디자인 시스템 참조: `/Users/seanbae/.claude/projects/-Users-seanbae-Desktop---/memory/design_system.md`
