# PivoxQuant 유료 티어 차별화 모델 로드맵

**작성일**: 2026-04-18
**작성**: 기획부 (Strategy Partner)
**목적**: Pro ₩9,900 / Premium ₩19,900 / Elite ₩99,900 티어에서 유저 지갑을 여는 차별화 모델 정의
**제약**: 100만원 예산 / 1인 창업자 / 구현 코드 작성 금지 (조사 + 문서만)

---

## Executive Summary

현재 16개 퀀트 모델 + 리스크/포트폴리오/행동/AI 스택은 "기능 풍부"하지만 **가격 정당화 스토리가 약하다**. 경쟁사 벤치마크 (Seeking Alpha $299/yr, SimplyWall.st $120/yr, Finbox, Trade Ideas, QuantPilot) 결과, 2026년 유료 전환의 핵심은 세 가지다:

1. **"개인화된 실행 루프"** — 단순 지표가 아니라 "나에게 지금 뭘 해야 하는지" 알려주는 에이전트
2. **대체 데이터 (Alternative Data)** — 공매도/외국인 수급/13F/Form 4/센티먼트 — 개인이 접근하기 어려운 데이터
3. **한국 시장 특화** — Toss/미래에셋이 못 하는 퀀트 깊이 + 영미권이 못 하는 KR 맥락

**Kill Criteria**: 3개월 내 Pro 전환율 2% 미달 시 → 가격 재조정 또는 무료 체험 연장으로 피벗.

---

## 1. TOP 15 차별화 모델 (유료 지갑 여는 것)

| # | 모델명 | 1줄 설명 | 차별화 (WHY 돈 낸다) | 난이도 | 데이터 | 티어 | 근거 |
|---|--------|----------|---------------------|--------|--------|------|------|
| 1 | **Kronos Regime Forecaster** | 금융 전용 Transformer로 레짐 전환 7일 전 예측 | TimeGPT/Chronos 대비 K-line 특화, 개인이 돌릴 수 없음 | XL | FMP OHLCV + KRX | Premium | Kronos 2026, Amazon Chronos-2 |
| 2 | **Foreign Flow Predictor (KR)** | 외국인 순매수 3일 선행 예측 + 섹터별 이탈 경보 | 토스/미래에셋도 raw 데이터만 제공, 예측은 없음 | L | KRX 투자자별 매매동향 + pyKRX | Pro | Barberis & Shleifer, KR institutional alpha |
| 3 | **Short Squeeze Radar** | 공매도 과열+대차잔고 급감+주가 하락 트리플 필터 | 한국 공매도 재개(2026) 이후 수요 폭증 | M | KRX 공매도 종합포털 | Premium | GameStop squeeze 2021, KR 2026 공매도 재개 |
| 4 | **Smart Money 13F Tracker** | Berkshire/Renaissance/Citadel 신규 편입 24h 알림 + 동조 매매 백테스트 | Seeking Alpha Pro 수준 기능을 가격 1/3에 | M | SEC EDGAR 13F (무료) | Pro | Finbox, whalewisdom 벤치마크 |
| 5 | **Insider Cluster Buy Alert** | Form 4 집단 매수 (30일 내 3명 이상) 실시간 알림 | 인사이더 매수 = 이후 6개월 초과수익 통계 유의 | S | SEC Form 4 API | Pro | Seyhun (1998), Cohen et al. (2012) |
| 6 | **Earnings Drift Edge (PEAD)** | 어닝 서프라이즈 후 60일 drift 확률+규모 예측 | 학계 검증 강함, 개인 투자자 접근 어려움 | M | FMP earnings + price | Premium | Bernard & Thomas (1989) PEAD anomaly |
| 7 | **Options Flow Heatmap** (US) | 비정상 콜/풋 매수 급증 = "Dark Pool" 이상 신호 | 개인은 Unusual Whales ($50/월) 대안 필요 | L | Polygon.io options (유료) | Elite | Unusual Whales 벤치마크 |
| 8 | **AI Portfolio Copilot** | 내 보유 종목 기준 일일 리밸런스 제안 + 세금 최적화 | "뭘 할지" 알려주는 게 핵심 — 2026 트렌드 | XL | 기존 스택 + OpenAI/Claude | Elite | QuantPilot 자연어 전략 트렌드 |
| 9 | **Macro Scenario Stress Test** | Fed 금리/유가/환율 3개 시나리오로 포트폴리오 손익 시뮬 | Bloomberg Terminal 기능 축소판 | L | FRED + 기존 리스크 모델 | Premium | Basel III stress testing |
| 10 | **Factor Attribution Report** | 수익률을 Value/Momentum/Quality/Size/Vol 5팩터로 분해 | "왜 내가 벌었나/잃었나"를 수치화 | M | FMP 재무제표 + 가격 | Premium | Fama-French 5-factor (2015) |
| 11 | **Sentiment Divergence Engine v2** | Reddit/X/뉴스 센티먼트 vs 가격 역행 시 알림 (StockGeist API) | 현재 SentimentDivergence 모델 업그레이드 | M | StockGeist or Adanos API | Pro | Tetlock (2007) media sentiment |
| 12 | **Index Event Calendar** | KOSPI200/S&P500 편입·편출 이벤트 30일 전 시그널 | 편입 前 평균 +8% 초과수익 (Russell rebalance) | S | KRX + Russell reconstitution | Pro | Chen et al. (2004) index effect |
| 13 | **Correlation Breakdown Alert** | 내 포트폴리오 상관구조 붕괴 감지 (2008/2020형 스트레스) | CorrelationRegime 업그레이드, 실시간화 | M | 기존 데이터 | Premium | Longin & Solnik (2001) |
| 14 | **Earnings Call AI Deep Dive** | CEO 톤+가이던스+Q&A 분석으로 매수/매도 시그널 | EarningsCallTone 업그레이드 (GPT-4급) | M | FMP transcripts + LLM | Premium | Larcker & Zakolyukina (2012) |
| 15 | **Personalized Alpha Discovery** | 내 과거 매매 패턴 학습 → 나에게 맞는 전략 추천 | Disposition effect 등 개인 편향 교정 | XL | 사용자 매매 로그 | Elite | Barber & Odean (2001) |

---

## 2. 현재 16모델 업그레이드 (재활용 > 신규)

| 기존 모델 | 업그레이드 방향 | 효과 | 난이도 |
|-----------|----------------|------|--------|
| **MLSignal** | → LightGBM+XGBoost 스태킹 앙상블 | 논문상 정확도 +10~20%, 추론 30% 빠름 | M |
| **AdaptiveParams** | → Chronos-2 zero-shot regime detection | 3-Layer 위에 foundation model 결합 | L |
| **SentimentDivergence** | → StockGeist/Adanos API + 멀티소스 | Reddit+X+뉴스+Polymarket 통합 | S |
| **EarningsCallTone** | → Claude 3.5/GPT-4o 장문 컨텍스트 분석 | 단순 키워드 → Q&A 미묘한 회피 패턴 감지 | M |
| **VIXStrategy** | → VIX term structure + VVIX 통합 | 헤지 타이밍 정확도 상승 | S |
| **RegimeSwitching** | → HMM → EMAT (Multi-Aspect Attention) | 레짐 전환 선행성 개선 | L |
| **MomentumBreakout** | → Volume Profile + Options Flow 조합 | 가짜 돌파 필터링 | M |
| **AIRiskSummary** | → RAG (회사 공시 + 뉴스 + 실적) 컨텍스트 | 환각 감소, 최신 정보 반영 | M |

**원칙**: 신규 15개 중 TOP 5만 3개월 내 구현, 나머지는 기존 모델 업그레이드로 커버 (70-20-10 룰).

---

## 3. Elite ₩99,900 Anchor 티어 "Wow" 기능 (5개)

**앵커링 전략**: Elite는 전환율 1% 목표 아님. Pro/Premium을 싸 보이게 하는 프레이밍 도구.

1. **AI Portfolio Copilot (일일 브리핑)** — 매일 아침 8시 "오늘 해야 할 것 3가지" 개인화 리포트 (PDF+푸시)
2. **Personalized Alpha Discovery** — 내 매매 로그 기반 편향 교정 + 맞춤 전략 추천
3. **1:1 분기 전략 리뷰 콜 (30분)** — 창업자가 직접 (첫 50명 한정) → 피드백 수집 채널로도 작동
4. **Options Flow + Dark Pool Monitor (US)** — Unusual Whales 대체재
5. **Custom Factor Lab** — 유저가 SQL/자연어로 팩터 정의 → 백테스트 → 저장 (Finbox 스크리너 대체)

---

## 4. 데이터 소스 확장 우선순위

| 데이터 | 비용 (월) | 티어 상승 효과 | 우선순위 |
|--------|-----------|---------------|---------|
| **pyKRX (무료)** — 외국인/기관 수급, 공매도 | $0 | ★★★★★ | P0 |
| **SEC EDGAR (무료)** — 13F, Form 4 | $0 | ★★★★★ | P0 |
| **FRED (무료)** — 매크로 지표 | $0 | ★★★★ | P0 |
| **StockGeist API** — 멀티소스 센티먼트 | $99~ | ★★★★ | P1 |
| **Polygon.io Options** — 옵션 플로우 | $199~ | ★★★ | P2 (Elite용) |
| **Tiingo / EODHD** — 글로벌 fundamentals | $30~ | ★★★ | P1 |
| **Benzinga Newswire** — 속보+AI 태깅 | $177~ | ★★ | P3 |
| **X API Basic** — 실시간 트윗 | $100 | ★★ | P3 (StockGeist 우선) |

**핵심 인사이트**: **무료 P0 3종 (pyKRX + SEC EDGAR + FRED)** 만으로 TOP 15 중 7개 모델 구현 가능. 유료 API는 Premium 전환 10건 달성 후 투입.

---

## 5. 티어 매트릭스 (최종 제안)

| | **Free** | **Pro ₩9,900** | **Premium ₩19,900** | **Elite ₩99,900** |
|---|----------|-----------------|-----------------------|---------------------|
| 퀀트 모델 | 3개 (기본) | **16개 전체** | + PEAD, Factor Attribution, Earnings Call AI | + AI Copilot, Personalized Alpha |
| 알림 | 일 3회 | **무제한 + 외국인/인사이더** | + 13F 24h 알림 + 공매도 과열 | + 옵션 플로우 + 1:1 리뷰 |
| 백테스트 | 1년 | **5년** | 20년 + Factor Lab (제한) | 20년 + Custom Factor Lab |
| AI | 주 3회 | 일 10회 | 무제한 + Deep Dive | 무제한 + Copilot 브리핑 |
| 데이터 | 지연 | **실시간 KR/US** | + 13F/Form 4/공매도 | + 옵션/다크풀 (US) |
| 포트폴리오 수 | 1개 | 3개 | 10개 | 무제한 + 세금 최적화 |

**가격 앵커 심리학**: Elite가 10배 비싸 보여야 Premium이 "합리적"으로 보임. Pro는 스타터, Premium이 타겟, Elite는 프레이밍.

---

## 6. 구현 로드맵 (3 / 6 / 12개월)

### 3개월 (MVP → Paid Launch)
**목표**: Pro/Premium 론칭, 유료 전환 시작
- [M1] pyKRX + SEC EDGAR 무료 3종 통합 (P0 데이터)
- [M1] **Foreign Flow Predictor (KR)** + **Smart Money 13F Tracker** + **Insider Cluster Buy** (3개 핵심 모델)
- [M2] MLSignal → LightGBM+XGBoost 앙상블 업그레이드
- [M2] **Short Squeeze Radar** (공매도 재개 타이밍)
- [M3] **Factor Attribution Report** + 티어 과금 인프라 (Stripe/토스페이)

**예산**: API $0, LLM 토큰 ~$200/월, 기회비용 (시간) = 핵심
**Kill 기준**: 월 유료 전환 10건 미달 시 모델 재조정

### 6개월 (Differentiation)
**목표**: Premium 차별화, Elite 테스트
- [M4] **Kronos/Chronos-2 통합** (AdaptiveParams 대체)
- [M4] **Earnings Drift Edge (PEAD)**
- [M5] **Sentiment Divergence v2** (StockGeist $99/월 투입 — 전환 100건 조건)
- [M5] **Earnings Call AI Deep Dive** (Claude API 연동)
- [M6] **Elite 베타 론칭**: AI Portfolio Copilot + 1:1 리뷰 콜 (50명 한정)

**투자**: StockGeist $99, LLM ~$500/월 → ARR 5천만원 목표 시 감당 가능

### 12개월 (Moat 구축)
**목표**: 철수 어려운 해자 형성
- [M7-9] **Personalized Alpha Discovery** (1년치 매매 로그 축적 후)
- [M10-11] **Options Flow + Dark Pool** (Elite 독점, Polygon.io $199/월)
- [M10-11] **Custom Factor Lab** (Finbox 대체)
- [M12] **한국 세금 최적화 엔진** (양도세/배당세 절세) — Toss가 못 하는 영역

---

## 7. 리스크 & 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| 투자자문업 규제 저촉 | 중 | 치명 | "정보 제공" 프레이밍 유지, 변호사 검토 (이미 LAWYER_CONSULTATION_PACKAGE) |
| 데이터 소스 API 단절 | 중 | 높음 | 무료 3종(KRX/SEC/FRED) 우선, 유료 API 의존도 최소화 |
| LLM 비용 폭증 | 중 | 중 | Claude Haiku / GPT-4o-mini 활용, 캐싱 적극 |
| 경쟁사 모방 | 높음 | 중 | 한국 시장 특화 + 1인 속도로 해자 구축 |
| Elite 전환 0건 | 높음 | 낮음 | 앵커 역할만 해도 OK, 3개월 후 가격 재조정 |

---

## 8. Recommendation (최종)

**Do Now (3개월)**:
1. **P0 무료 데이터 3종 통합** (pyKRX + SEC EDGAR + FRED) — 리소스 대비 효과 최고
2. **TOP 5 모델 우선 구현**: Foreign Flow / Smart Money 13F / Insider Cluster / Short Squeeze / Factor Attribution
3. **MLSignal LightGBM 앙상블 업그레이드** (기존 자산 활용)

**Don't Do (지금)**:
- Options/Dark Pool (유료 API 부담)
- Custom Factor Lab (개발 XL, 수요 검증 前)
- Kronos 통합 (ROI 미검증)

**기회비용 선언**: 위 3개에 집중 = 신규 UI 개편, 마케팅 자동화, 모바일 앱은 보류.

**성공 지표 (3개월)**:
- Pro 전환율 2%+ (DAU 기준)
- Premium 전환율 0.5%+
- MRR ₩500,000+ (50명 × Pro 평균)
- Elite 베타 대기자 10명+

---

**참고 문헌 / 벤치마크**:
- Seeking Alpha Premium ($269/yr), SimplyWall.st ($120/yr), Finbox, Trade Ideas, Unusual Whales
- Amazon Chronos-2 (2025-10), TimeGPT, Kronos (2026)
- Cohen et al. (2012) insider trades alpha, Bernard & Thomas (1989) PEAD
- Fama-French 5-factor (2015), Longin & Solnik (2001) correlation breakdown
- KRX Data Marketplace, SEC EDGAR, StockGeist, Adanos

---

# 3. Elite 재검토 (v2) — CEO 피드백 반영

**작성일**: 2026-04-18
**트리거**: CEO 피드백 — "Elite ₩99,900 너무 비싸다. AI Copilot/Personalized Alpha는 ChatGPT Plus ₩29,000 + Custom GPT로 복제 가능."
**판단**: 정확한 지적. Wow 기능 5개 중 **AI Copilot + Personalized Alpha = ChatGPT 방어 불가**. 진짜 해자는 3개 — 옵션플로우, 1:1 콜, Factor Lab.

## 3.1 Situation Analysis

- **Current State**: Elite ₩99,900 (Premium 대비 5배). Wow 기능 5개 중 2개가 ChatGPT Plus + 복붙으로 대체 가능.
- **Target State**: 유저가 "ChatGPT로는 못 하는 것"만 남긴 앵커 티어. MRR 목표 50만원 ≒ Pro 50명 or Premium 25명 or Elite 5명.
- **Gap**: Elite 전환 0명 시나리오 높음. 앵커링 효과도 **신뢰 잃으면 오히려 역효과** (Premium까지 과가격으로 의심).

## 3.2 Options Analysis (ICE Scoring)

| Option | Pros | Cons | Impact | Confidence | Ease | ICE |
|--------|------|------|--------|------------|------|-----|
| **A. Elite ₩49,900** (5배→2.5배) | 앵커 유지, 심리적 장벽↓, 구현 변화 없음 | AI Copilot 방어 여전히 약함, Premium과 격차 좁아 차별 애매 | 6 | 7 | 9 | **378** |
| **B. Elite 삭제, Premium ₩29,900** | 3티어→2티어 단순화, 운영 부담↓, ChatGPT 비교 무의미 (Premium은 데이터/한국특화로 승부) | 앵커 소실 → Pro ₩9,900가 "최상위"로 보여 가격 인상 여력 상실, 1:1 콜/옵션플로우 수익화 경로 잃음 | 5 | 8 | 10 | **400** |
| **C. Elite ₩39,900 + KIS/키움 자동매매 번들** | "ChatGPT가 못 하는 실행" 명확, 법 리스크 전제 해결 시 Wow 최강 | 투자자문업/일임업 규제, 법 검토 6개월+, 1인 창업자 운영 부담 극대, Kill criteria 쉬움 | 9 | 3 | 2 | **54** |

**기회비용 계산**: C안은 법무 리뷰 + 증권사 API 제휴 + 주문 감사로그 등 최소 3개월 풀타임 소요. 현재 P0 버그 17개 해결이 우선 — 시급 환산 시 C안은 **MVP 출시 자체를 지연시킴**.

## 3.3 ChatGPT Plus (₩29,000) 직접 비교표

| 항목 | ChatGPT Plus + Custom GPT | PivoxQuant Premium ₩19,900 |
|------|--------------------------|---------------------------|
| **월 가격** | ₩29,000 | ₩19,900 (**더 쌈**) |
| **실시간 가격 데이터** | 없음 (유저가 복붙) | FMP + Alpaca 실시간 연동 |
| **한국 시장 (KRX)** | 뉴스 일반 지식만 | pyKRX 외국인/기관 수급, 공매도 |
| **자동 스캔/알림** | 없음 (대화형) | 매일 시그널, 푸시 알림 |
| **13F / Form 4** | 웹검색 제한적 | SEC EDGAR 구조화 |
| **백테스트** | 코드 생성만, 실행 불가 | 원클릭 백테스트 + Sharpe/Sortino |
| **브로커 연동** | 없음 | Alpaca paper, KIS read-only |
| **법적 면책/컴플라이언스** | 일반 AI 면책 | 자본시장법 용어 정제 (시그널=POSITIVE 등) |
| **환각 리스크** | 높음 (가짜 재무제표 생성) | 검증된 API 데이터만 |

**"왜 ChatGPT 있는데 우리에게 내는가" (10문장)**:
1. ChatGPT는 실시간 가격을 모른다 — 유저가 매번 복붙해야 한다.
2. KRX 외국인 수급/공매도 잔고는 ChatGPT가 접근 불가한 데이터다.
3. 매일 아침 시그널 스캔은 대화형 AI로 안 된다 — 자동화된 파이프라인이 필요하다.
4. ChatGPT는 숫자 환각을 일으킨다 — 재무제표·PER을 거짓 생성한 사례가 반복 보고된다.
5. 백테스트는 코드 실행 환경 + 거래비용 모델 + 정답 벤치마크가 있어야 한다.
6. Alpaca/KIS 브로커 연동은 API 키·OAuth·감사로그가 필요하다.
7. "시그널 라벨 = POSITIVE/NEGATIVE" 같은 자본시장법 대응은 범용 AI가 안 한다.
8. 13F/Form 4 구조화 파싱과 알림은 데이터 엔지니어링 작업이지 프롬프트 작업이 아니다.
9. 시간당 비용 — 유저가 ChatGPT에 프롬프트 10번 붙여넣는 시간 > 월 ₩19,900의 한계가치.
10. 한국어 + 한국 세제 + KIS/Alpaca 이중 시장 운영은 범용 LLM이 커버 못 한다.

## 3.4 AI Copilot / Personalized Alpha 재포지셔닝

**판단**: **Elite 전용 유지는 방어 불가 → 포지셔닝 전환**.

- **AI Copilot (일일 브리핑)**: Premium으로 **내리되**, "ChatGPT와 다른 점"을 기능 설명에서 명시 — 실시간 가격·내 포트폴리오·한국 시장 연동 자동 브리핑. 즉, AI가 아니라 **자동화 파이프라인**을 판다.
- **Personalized Alpha Discovery**: 사용자 매매 로그 기반이므로 ChatGPT가 접근 불가 → **Premium 유지**. 단 마케팅 카피에서 "AI 전략 추천"이 아니라 "당신의 손절 습관 교정"으로 재포지션 (Disposition Effect 교정).
- **Elite 잔존 3개 기능만 남김**: 옵션플로우(데이터 비용 해자), 1:1 창업자 콜(인간 해자), Custom Factor Lab(툴 해자).

## 3.5 최종 티어 매트릭스 (확정안 = Option A 변형)

| | **Free** | **Pro ₩9,900** | **Premium ₩19,900** | **Elite ₩49,900** |
|---|---|---|---|---|
| 시그널 스캔 | 일 5개 | 무제한 | 무제한 + AI Copilot 일일브리핑 | 무제한 + 옵션플로우 |
| 한국 시장 (KRX) | 지수만 | Foreign Flow, 공매도 | + Short Squeeze Radar | 전체 |
| 13F / Form 4 | 없음 | Smart Money Tracker | + Insider Cluster | 전체 |
| 백테스트 | 월 3회 | 월 30회 | 무제한 + Factor Attribution | 무제한 + **Custom Factor Lab** |
| AI Copilot | 없음 | 주간 | **일일 브리핑** | 일일 + 맞춤 |
| Personalized Alpha | 없음 | 없음 | **✅** | ✅ |
| 옵션플로우 (US) | 없음 | 없음 | 없음 | **✅ Unusual Whales 대체** |
| 1:1 분기 콜 (30분) | 없음 | 없음 | 없음 | **✅ 창업자 직접** |
| 앵커 효과 (Pro/Premium 대비) | — | 1x | 2x | **5x** |

**왜 ₩49,900인가**: Seeking Alpha Premium ($299/yr ≈ 월33,000) + Unusual Whales ($50/월 ≈ ₩71,000) 합산 = 월 ₩104,000. 우리는 절반 이하인 ₩49,900로 "둘 다 포함 + 한국 특화 + 1:1 콜" 프레임.

## 3.6 권장안 + 근거 3문장

**권장**: **Option A (Elite ₩49,900) + AI Copilot/Personalized Alpha를 Premium으로 하향**.

1. Option B(Elite 삭제)는 ICE 최고지만 1:1 콜·옵션플로우의 수익화 경로와 가격 앵커를 동시에 잃어 MRR 50만원 도달 속도가 느려진다 — 5명 × 49,900 = 249,500원이 Premium 25명보다 획득 난이도가 낮다.
2. Option C(자동매매 번들)는 투자자문업/일임업 규제로 법 검토 6개월 + 창업자 시간 붕괴 = 현재 P0 버그 17개 해결을 지연시키는 명백한 악수다.
3. AI 기능의 ChatGPT 방어는 "AI"가 아니라 "자동화 파이프라인 + 실시간 데이터 + 한국 특화"로 카피를 재작성하면 방어 가능하며, Premium 하향 시 오히려 Premium 지갑 여는 핵심 훅이 된다.

## 3.7 가격 A/B 테스트 계획

**설계**: Pricing 페이지에서 랜덤 50/50 분할, 세션 쿠키 고정. 전환 = "결제 페이지 진입" (Stripe 미연결 상태에서 이메일 웨이팅리스트 수집으로 대체).

| 테스트 | Arm A | Arm B | 성공 지표 | 샘플 최소 |
|--------|-------|-------|-----------|-----------|
| **T1: Elite 가격** | ₩49,900 | ₩39,900 | Elite 클릭률, 전체 Premium 전환율 (앵커효과) | 각 500 방문 |
| **T2: Premium 가격** | ₩19,900 | ₩24,900 | 결제진입률, LTV 추정 | 각 800 방문 |
| **T3: AI Copilot 포지셔닝 카피** | "AI 일일 브리핑" | "ChatGPT가 못 하는 자동 파이프라인" | 기능 페이지 체류·스크롤 | 각 400 방문 |

**판단 규칙**: Bayesian A/B (베타 prior Beta(1,1)), 95% 확률 우위 달성 시 조기 종료. 샘플 미달 시 최소 2주 수집 후 재평가. 유료 유저 30명 이전에는 **가격 확정 금지** (표본 부족 = 가짜 신호).

**Kill Criteria (v2)**:
- 90일 내 Elite 전환 0명 & Premium 전환 10명 미만 → **Option B(Elite 삭제)로 피벗**.
- 180일 내 MRR ₩300,000 미달 → 가격·티어 전면 재설계 (월 → 연 할인, 평생 라이선스 등 실험).

---

**재검토 결론**: Elite는 "AI"를 팔지 않는다. **"데이터 해자 + 인간 해자 + 툴 해자"** 3개만 남긴 ₩49,900 앵커로 재포지셔닝. AI 기능은 Premium으로 내려 지갑 여는 훅으로 전환. ChatGPT Plus 비교는 가격(₩19,900 < ₩29,000)으로 이기고, 차별화는 "자동화 파이프라인 + 실시간 데이터 + 한국 특화"로 이긴다.

