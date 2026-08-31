# PivoxQuant 15팩터 퀀트 모델 — 쉽게 풀어쓴 설명서

> 대상: 개발자가 아닌 본인(창업자)과 고객이 "우리 제품이 뭘 하는지" 이해할 수 있도록 작성.
> 최종 업데이트: 2026-04-17

---

## ⚠️ 법적 고지 (가장 먼저 읽을 것)

PivoxQuant는 **투자자문업체가 아닙니다.**
이 문서에 나오는 모든 점수, 시그널, 분석은 **정보 제공 목적**입니다.
"POSITIVE / NEGATIVE / NEUTRAL" 시그널은 **매수/매도 추천이 아닙니다.**
투자 결정은 본인이 직접 내리셔야 하며, 모든 손익은 본인 책임입니다.

---

## Part 1. 정말 쉬운 설명 (3줄 요약)

### Q. "15팩터가 뭐에요?"

A. 주식 하나를 볼 때 **15가지 기준으로 점수를 매기는 것**입니다.
예를 들어 사람을 뽑을 때 학력, 경력, 성격, 자격증, 건강, 커뮤니케이션 능력 등 여러 기준으로 보는 것처럼, 우리도 주식을 볼 때 딱 하나(주가)만 보지 않고 **15가지 각도**에서 점수를 매깁니다.

### 비유: 이력서 점수 매기기

사람을 뽑을 때 이력서를 본다고 생각해 봅시다.

| 사람 뽑을 때 | 주식 볼 때 (PivoxQuant) |
|---|---|
| 학력 (얼마나 배웠나) | P/E (얼마나 싸게 사는 거냐) |
| 경력 (일 얼마나 했나) | Revenue Growth (매출이 얼마나 커졌나) |
| 성격 (안정적인가) | Beta (시장 출렁임에 얼마나 흔들리는가) |
| 최근 퍼포먼스 | Momentum (최근 주가 흐름) |
| 건강 | Debt/Equity (빚은 안 많은가) |
| ... | ... (총 15가지) |

이 15가지 점수를 **가중평균**으로 합쳐서 **0~100점짜리 PivoxScore**를 만듭니다.

### 예시 — 한 줄 요약

> **삼성전자 PivoxScore: 7.2/10**
> "PER(가성비) 양호, 최근 주가 흐름은 강함, 부채비율은 보통. 단 반도체 업황 사이클 주의."

### 우리가 실제로 하는 일

- **하는 것**: "이 종목을 보면 15가지 지표가 이렇게 나옵니다" 라고 **정보를 보여드리는 것**
- **안 하는 것**: "이거 사세요 / 파세요" 같은 **투자 추천**

---

## Part 2. 전체 엔진 흐름도

```
[1] 시장 데이터 수집
     ├─ KIS 한국투자증권 API (한국 주식)
     ├─ Alpaca API (미국 주식 가격 + 거래량)
     └─ FMP API (재무제표, 밸류에이션 지표)
              ↓
[2] engine.py  ← 4개 영역에서 점수 계산
     ├─ Technical (50%): RSI, MACD, 볼린저, MA, ADX, OBV, MFI, Ichimoku, CCI, Williams%R, Stochastic, Aroon
     ├─ Fundamental (30%): P/E, Revenue Growth, Profit Margin, Debt/Equity, Beta, Forward P/E, EPS
     ├─ News Sentiment (3~20%): 뉴스 키워드 기반 (RSS, LLM 없음 → 비용 0)
     └─ Quant (37~50%): 아래 quant_models.py 통합
              ↓
[3] quant_models.py  ← 고급 퀀트 모델 모음
     ├─ MeanReversion (평균회귀)
     ├─ MomentumBreakout (돌파)
     ├─ VolatilityRegime (변동성 국면)
     ├─ RegimeSwitching (Bull/Bear/Transition 감지)
     ├─ MLSignal (머신러닝 앙상블)
     ├─ DualMomentum, TSMOM, DonchianBreakout 등
              ↓
[4] AdaptiveParams  ← 3-Layer로 "지금 시장 분위기"에 맞게 조정
     ├─ Layer 1: ATR (이 종목 자체의 변동성)
     ├─ Layer 2: Regime Matrix (추세 국면 × 변동성 국면)
     └─ Layer 3: ML Confidence (모델 신뢰도)
              ↓
[5] 시그널 + 가중치 조합
     ├─ ETF vs 한국주식 vs 대형주 vs 소형주 → 가중치 다르게 적용
     ├─ VIX 높으면 매수 기준 강화
     └─ 52주 고가 근접 시 모멘텀 보너스
              ↓
[6] Claude AI 자연어 해석
     └─ "이 점수가 왜 이렇게 나왔는가"를 한국어로 설명
              ↓
[7] 유저 화면에 표시 (POSITIVE / NEGATIVE / NEUTRAL)
```

각 단계 요약:

1. **데이터 수집**: 3개 외부 소스에서 실제 시세/재무/뉴스를 끌어옵니다.
2. **engine.py**: 4개 영역(Technical/Fundamental/News/Quant) 각각 0~100점을 계산합니다.
3. **quant_models.py**: 대학/월가에서 쓰는 고급 통계 모델로 추가 점수를 만듭니다.
4. **AdaptiveParams**: "지금 상승장인지 하락장인지"에 따라 점수 기준을 자동으로 조정합니다.
5. **가중치 조합**: 종목 종류(ETF/한국/대형/소형)에 따라 가중치가 다릅니다.
6. **AI 해석**: 숫자를 사람이 읽을 수 있는 한국어로 풀어냅니다.
7. **표시**: 유저는 최종적으로 PivoxScore + 한 문단 설명 + 시그널 라벨을 봅니다.

---

## Part 3. 15팩터 상세 (실제 코드 기준)

> 실제 `engine.py`의 `_technical()`, `_fundamental()` 함수와 `quant_models.py`에서 추출했습니다.
> 가중치는 **engine.py L143-165**의 실제 값 기준입니다 (종목 타입별로 달라짐).

### 🟦 Technical (기술적 지표) — 전체 점수의 22~50%

---

#### Factor 1. RSI (상대강도지수)

- **쉬운 설명**: "최근 주가가 너무 많이 올랐나, 너무 많이 떨어졌나" 온도계.
- **왜 쓰는가**: 30 이하면 과매도(싸게 산다), 70 이상이면 과매수(비싸다). 많이 떨어진 종목이 튀어오를 가능성을 본다.
- **계산**: 최근 14일간 상승일 평균 / (상승 평균 + 하락 평균) × 100
- **우리 로직**:
  - RSI < 30 + 200일선 위 → +20점 (상승추세 중 과매도 → 반등 기대 큼)
  - RSI > 70 → -20점 (과열)
- **예시**: 삼성전자 RSI = 28, 주가가 200일선 위 → 강한 반등 시그널 +20점
- **가중치**: Technical 점수의 약 20%

#### Factor 2. MACD (이동평균 수렴/발산)

- **쉬운 설명**: "단기 흐름이 장기 흐름을 뚫고 위로 갔냐 아래로 꺾였냐" 방향지시등.
- **왜 쓰는가**: 골든크로스(위로 뚫음)는 상승 신호, 데드크로스(아래로 꺾임)는 하락 신호. 월가에서 50년 넘게 쓰는 고전.
- **계산**: 12일 EMA - 26일 EMA, 그리고 그 9일 EMA(signal line)와 비교
- **우리 로직**:
  - 골든크로스 발생 → +18점
  - 데드크로스 발생 → -18점
- **예시**: AAPL이 3개월 조정 후 MACD 골든크로스 → +18점
- **가중치**: Technical 점수의 약 18%

#### Factor 3. Bollinger Bands (볼린저 밴드)

- **쉬운 설명**: "주가가 평소 움직임 범위에서 얼마나 벗어났나" 고무줄.
- **왜 쓰는가**: 아래 밴드 터치 = 통계적으로 싸다 (평균 회귀 기대). 위 밴드 터치 = 통계적으로 비싸다.
- **계산**: 20일 이동평균 ± 2 표준편차
- **우리 로직**:
  - 하단 밴드 근접 + 상승추세 → +18점
  - 상단 밴드 근접 → -15점
- **예시**: 카카오 볼린저 하단 터치 → +18점
- **가중치**: Technical 점수의 약 15%

#### Factor 4. Moving Average Cross (이동평균선 정배열)

- **쉬운 설명**: "50일 평균선이 200일 평균선 위에 있나" 장기 트렌드 방향.
- **왜 쓰는가**: 정배열(50 > 200)은 중장기 상승추세. 역배열은 하락추세.
- **계산**: MA50 vs MA200 비교
- **우리 로직**: 정배열 +18, 역배열 -18, 50MA 위 +5
- **예시**: NVDA 50일선이 200일선 위 + 현재가가 50일선 위 → +23점
- **가중치**: Technical 점수의 약 15%

#### Factor 5. Volume (거래량 분석)

- **쉬운 설명**: "평소보다 사람들이 많이 샀나/팔았나".
- **왜 쓰는가**: 기관투자자가 움직이면 거래량이 급증. 상승 + 거래량 급증은 진짜 돌파. 상승인데 거래량 없으면 가짜 돌파.
- **계산**: 현재 거래량 vs 20일 평균 거래량
- **우리 로직**:
  - 거래량 1.5배 + 상승 → +12점 (기관 매수 추정)
  - 거래량 1.5배 + 하락 → -12점 (기관 매도 추정)
- **예시**: 삼성전자 하루 거래량 2배 + 2% 상승 → +12점
- **가중치**: Technical 점수의 약 12%

#### Factor 6. Advanced Indicators (고급 기술 지표 묶음)

- **포함 지표**: ADX(추세 강도), OBV(자금 흐름), Stochastic, Ichimoku(구름), CCI, MFI, Williams%R, Aroon, Keltner
- **쉬운 설명**: 위 5개로 안 잡히는 미세한 신호를 보완.
- **왜 쓰는가**: 단일 지표는 실수하지만, 여러 지표가 같은 방향이면 신뢰도가 올라감 (Ensemble).
- **예시 일부**:
  - ADX > 40 + 상승추세 → +8점 (추세 강함)
  - Ichimoku 구름 위 → +6점
  - MFI < 20 → +8점 (자금 유입)
- **가중치**: Technical 점수의 약 20% (합산)

---

### 🟩 Fundamental (재무제표) — 전체 점수의 5~32%

---

#### Factor 7. P/E Ratio (주가수익비율)

- **쉬운 설명**: "이 회사 주식 1주 사려면, 이 회사가 1년에 버는 순이익의 몇 배를 내는지".
- **왜 쓰는가**: PER 낮을수록 "싸게 산다"는 의미. Warren Buffett이 제일 먼저 보는 지표.
- **계산**: 주가 / 주당순이익(EPS)
- **우리 로직**:
  - PER < 12 → +22점 (명확한 저평가)
  - PER < 20 → +12점 (적정)
  - PER > 50 → -18점 (고평가)
- **예시**: 삼성전자 PER 15 → "15년치 순이익만큼 주고 사는 셈" → +12점
- **가중치**: Fundamental 점수의 약 25%

#### Factor 8. Revenue Growth (매출 성장률)

- **쉬운 설명**: "작년보다 매출이 얼마나 커졌나".
- **왜 쓰는가**: 매출이 커진다 = 회사가 성장 중. 매출이 줄면 사업 자체가 위축.
- **계산**: (올해 매출 - 작년 매출) / 작년 매출
- **우리 로직**:
  - 25% 이상 성장 → +20점
  - 10~25% → +10점
  - 음수 (역성장) → -15점
- **예시**: NVDA 매출 +50% → +20점 (강한 모멘텀)
- **가중치**: Fundamental 점수의 약 20%

#### Factor 9. Profit Margin (순이익률)

- **쉬운 설명**: "매출 100원 중 순이익이 몇 원인지".
- **왜 쓰는가**: 같은 매출이라도 이익률 높으면 돈 잘 버는 회사. 해자(moat)가 있다는 뜻.
- **계산**: 순이익 / 매출
- **우리 로직**:
  - 20% 이상 → +15점 (excellent moat)
  - 10~20% → +7점
  - 음수(적자) → -18점
- **예시**: Apple 순이익률 25% → +15점
- **가중치**: Fundamental 점수의 약 15%

#### Factor 10. Debt/Equity (부채비율 = 레버리지)

- **쉬운 설명**: "이 회사가 자기 돈 대비 빚이 얼마나 많나".
- **왜 쓰는가**: 빚 많으면 금리 오를 때 위험. 빚 적으면 불황에도 살아남음.
- **계산**: 총부채 / 자기자본 × 100
- **우리 로직**:
  - D/E < 30% → +10점 (탄탄)
  - D/E > 200% → -12점 (고위험)
- **예시**: 삼성전자 D/E 28% → +10점 (요새다운 재무구조)
- **가중치**: Fundamental 점수의 약 10%

#### Factor 11. Beta + Forward P/E + EPS (리스크/기대치 묶음)

- **쉬운 설명**: "시장 흔들릴 때 얼마나 같이 흔들리나(Beta), 앞으로 실적이 늘어날지(Forward P/E), 지금 흑자인지(EPS)".
- **왜 쓰는가**:
  - Beta > 2 = 시장보다 2배 흔들림 → 고위험
  - Forward P/E < Trailing P/E = 내년 실적 개선 기대
  - EPS 음수 = 적자 기업
- **우리 로직**:
  - Beta > 2.0 → -5점
  - Forward P/E가 Trailing P/E보다 20% 낮음 → +8점
  - EPS 흑자 + 흑자 마진 → +3점 (bonus)
- **예시**: TSLA Beta 2.3 + Forward PE 낮음 → Beta -5, Forward +8 → 종합 +3
- **가중치**: Fundamental 점수의 약 15%

---

### 🟧 News Sentiment (뉴스 감성) — 전체 점수의 3%

---

#### Factor 12. News Keyword Sentiment

- **쉬운 설명**: "최근 뉴스가 긍정적이냐 부정적이냐"를 **키워드로** 판별.
- **왜 쓰는가**: 실적 발표, 규제 이슈, CEO 리스크 등 재무제표에 안 잡히는 이슈 감지.
- **계산**: RSS 뉴스 피드를 긁어서 긍정 키워드(surge, beat, approved) vs 부정 키워드(lawsuit, miss, probe) 카운트. **LLM을 쓰지 않아 비용 0**.
- **우리 로직**: 0~100점 환산
- **예시**: "Apple beats earnings, record iPhone sales" → 긍정 키워드 2개 → +점수
- **가중치**: 전체의 3% (뉴스 노이즈 많아서 낮게)

---

### 🟪 Quant Models (고급 퀀트) — 전체 점수의 37~50%

---

#### Factor 13. MeanReversion + MomentumBreakout

- **쉬운 설명**: 두 가지 정반대 전략을 동시에 돌림.
  - Mean Reversion: "너무 떨어진 건 다시 올라올 것"
  - Momentum Breakout: "오르는 말에 올라타라"
- **왜 쓰는가**: 시장 국면마다 맞는 전략이 다름. 횡보장엔 평균회귀, 추세장엔 돌파.
- **계산**:
  - MeanReversion: z-score = (현재가 - 20일 평균) / 20일 표준편차
  - MomentumBreakout: 20일 최고가 돌파 + 거래량 확인
- **예시**: AAPL z-score -2.1 (평균 대비 2.1 표준편차 아래) → MeanReversion 매수 시그널
- **가중치**: Quant 점수의 약 20%

#### Factor 14. Regime Detection (VolatilityRegime + RegimeSwitching)

- **쉬운 설명**: "지금 시장이 어떤 국면인지" 자동 감지.
  - VolatilityRegime: LOW_VOL / NORMAL / HIGH_VOL / CRISIS
  - RegimeSwitching: BULL / MILD_BULL / TRANSITION / MILD_BEAR / BEAR
- **왜 쓰는가**: 같은 시그널이라도 국면에 따라 의미가 다름. Bull장의 RSI 30과 Bear장의 RSI 30은 달라야 함.
- **계산**:
  - Vol: 연율화 변동성 (std × √252)
  - Trend: Markov Regime Switching 모델 또는 20일 수익률 분류
- **예시**: VIX 35 + S&P 3개월 -8% → (BEAR, HIGH_VOL) → "생존 모드" 적용
- **가중치**: Quant 점수의 약 30% (가장 중요)

#### Factor 15. ML Ensemble + 52-Week High + VIX + Cross-Asset

- **쉬운 설명**: 머신러닝 모델 + 매크로 요인 보정
  - MLSignal: 여러 모델(RF, Logistic, XGB) 합의
  - FiftyTwoWeekHigh: 52주 최고가 근접 시 모멘텀 보너스
  - VIXStrategy: 공포지수 높으면 매수 기준 강화
  - CrossAssetMomentum: 달러/금/채권 등 매크로 환경
- **왜 쓰는가**: 개별 종목 분석으로 안 잡히는 거시적 흐름 보정.
- **우리 로직**:
  - 52주 고가 5% 이내 + 거래량 확인 → 점수 1.1배
  - VIX > 30 → 매수 기준 5점 상향
- **예시**: 삼성전자가 52주 고가 97% 지점 + 거래량 증가 → composite × 1.1
- **가중치**: Quant 점수의 약 50%

---

### 종합 가중치 (engine.py L143-165 실제 코드)

| 종목 타입 | Technical | Fundamental | News | Quant | Buy 기준 |
|---|---|---|---|---|---|
| **ETF** | 50% | 5% | 3% | 42% | 65점 |
| **한국 주식** | 28% | 32% | 3% | 37% | 63점 |
| **미국 대형주 (100B+)** | 22% | 25% | 3% | 50% | 68점 |
| **미국 소형주 (<10B)** | 25% | 22% | 3% | 50% | 70점 |
| **기타 미국** | 22% | 25% | 3% | 50% | 68점 |

→ 한국주식은 Fundamental 비중이 크고, ETF는 Technical 위주, 미국 대형주는 Quant 모델 비중이 가장 큼.

---

## Part 4. AdaptiveParams + AI 해석

### AdaptiveParams — 3-Layer 시스템 (quant_models.py L1100~1400)

고정된 가중치/임계값은 "시장이 변하면 망합니다". 그래서 **자동으로 조정**합니다.

#### Layer 1: ATR (이 종목 자체의 변동성)

- ATR = 14일 평균 True Range = "이 종목이 하루에 평균 얼마나 움직이는가"
- **왜 쓰는가**: 삼성전자(하루 1%)와 TSLA(하루 4%)에 같은 손절선(-3%)을 쓰면 안 됨.
- **효과**: 종목별로 TP/SL/Trailing 스탑 폭을 **ATR × 배수**로 자동 설정.

#### Layer 2: Regime Matrix (시장 국면 × 변동성)

5개 추세 국면 × 4개 변동성 국면 = **20가지 조합**, 각각에 맞는 5가지 프로파일 배정.

| 추세 \ 변동성 | LOW_VOL | NORMAL | HIGH_VOL | CRISIS |
|---|---|---|---|---|
| **BULL** | trend_rider | trend_rider | trend_rider | defensive |
| **MILD_BULL** | trend_rider | trend_rider | momentum | defensive |
| **TRANSITION** | scalper | scalper | defensive | survival |
| **MILD_BEAR** | scalper | defensive | survival | survival |
| **BEAR** | defensive | survival | survival | **No Trade** |

**5가지 프로파일** (quant_models.py L1121-1142):

| 프로파일 | TP | SL | Trail | 쿨다운 | 의미 |
|---|---|---|---|---|---|
| trend_rider | 무제한 | 8 | 4 | 2 | 강한 추세 - 추세 깨질 때까지 보유 |
| momentum | 무제한 | 8 | 3.5 | 3 | 중간 추세 |
| scalper | 6 | 2 | 3 | 3 | 횡보장 - 짧게 먹고 나옴 |
| defensive | 3 | 3 | 2.5 | 5 | 약세장 - 자본 보호 |
| survival | 2 | 3.5 | 2 | 7 | 하락장 - 최소 노출 |

→ TP/SL은 ATR × 배수로 계산되므로 실제 % 값은 종목마다 다름.

#### Layer 3: ML Confidence (모델 신뢰도 미세조정)

- MLSignal 앙상블(RF + Logistic + XGB)의 **합의 강도**를 봅니다.
- 3개 모델이 모두 같은 방향이면 → TP를 조금 더 넓혀서 이익을 극대화
- 의견이 갈리면 → TP/SL을 타이트하게 → 리스크 축소

### AI 해석 (Claude Sonnet 4.5)

숫자만 보여주면 비전문가는 이해 못 합니다. 그래서 **Claude API**로 자연어 해석을 덧붙입니다.

**입력**: 15팩터 점수 + AdaptiveParams 프로파일 + 가격 정보
**출력**: 한국어 한 문단 설명

**실제 예시**:

> "삼성전자 PivoxScore 72점 — Value 팩터 우수(PER 15로 저평가, 상위 15%), 최근 3개월 모멘텀 강함(MACD 골든크로스 + 200일선 위), 단 반도체 섹터 Beta 1.4로 시장 대비 출렁임 큼. 현재 Regime은 (MILD_BULL, NORMAL)로 'trend_rider' 프로파일 적용 중. ⚠️ 이는 정보 제공이며 매수 추천이 아닙니다."

---

## Part 5. FAQ (10개)

#### Q1. "이 종목 PivoxScore 80점이면 사야 하나요?"

**아닙니다.** 80점은 "15개 지표가 통계적으로 유리한 구간에 있다"는 **정보**일 뿐입니다. 매수 결정은 본인의 재정 상황, 투자 기간, 포트폴리오 구성, 리스크 감내도 등을 종합해서 본인이 내려야 합니다. PivoxQuant는 투자자문업체가 아닙니다.

#### Q2. "왜 하필 15개인가요?"

월가 학술 근거(Fama-French 3/5 Factor Model, Carhart Momentum, Barra Risk Model)를 기반으로 **한국 개인 투자자 환경에 맞게** 15개로 압축했습니다. 더 추가하면 과적합(overfitting), 더 줄이면 정보 손실이 생깁니다. 15는 최적 밸런스입니다.

#### Q3. "점수는 얼마나 자주 업데이트되나요?"

- **Technical 점수**: 가격 들어올 때마다 (장중 실시간 가능)
- **Fundamental 점수**: 재무제표 발표 시 (분기 1회)
- **News Sentiment**: 하루 1~2회 RSS 갱신
- **AdaptiveParams**: VIX/국면 변경 시 자동 재계산

#### Q4. "데이터는 어디서 오나요?"

- **미국 가격/거래량**: Alpaca Markets API (paper trading)
- **미국 재무제표/밸류에이션**: FMP (Financial Modeling Prep) v4 Stable ($29/월)
- **한국 주식**: KIS 한국투자증권 OpenAPI (read-only)
- **뉴스**: RSS 피드 (Yahoo Finance, Seeking Alpha, 네이버 금융)

#### Q5. "한국 주식과 미국 주식이 다르게 분석되나요?"

네, 다릅니다. `engine.py L152-154`에서 한국 주식은 **Fundamental 비중 32%**, 미국 대형주는 **Quant 비중 50%**로 자동 조정됩니다. 한국은 재무제표 기반 투자가 유효하고, 미국 대형주는 효율적 시장이라 고급 퀀트 시그널이 중요합니다.

#### Q6. "점수는 언제 바뀌나요?"

- 가격 변동 시 (실시간 Technical)
- 재무제표 신규 발표 (분기별 Fundamental)
- AdaptiveParams 프로파일 변경 (국면 전환 시)
- VIX 30 돌파 시 매수 기준 +5점 상향
- 52주 고가 5% 이내 진입 시 모멘텀 보너스

#### Q7. "TipRanks Smart Score와 어떻게 다른가요?"

| 항목 | TipRanks | PivoxQuant |
|---|---|---|
| 언어 | 영어 | **한국어 + 영어** |
| 한국 주식 | 미지원 | **KOSPI/KOSDAQ 지원** |
| AI 해석 | 없음 | **Claude로 한국어 설명** |
| 국면 적응 | 고정 가중치 | **AdaptiveParams 3-Layer** |
| 가격 | $30/월 | ₩9,900~19,900/월 |

#### Q8. "백테스트 정확도는?"

`backtester.py`에서 거래 비용 + 슬리피지를 반영한 백테스트를 돌립니다. 다만 **과거 성과는 미래를 보장하지 않습니다** (Past performance is not indicative of future results). 실제 라이브 성과는 백테스트보다 대체로 20~30% 할인해서 보시는 것이 현실적입니다.

#### Q9. "내 관심 종목 점수가 낮은데 왜죠?"

점수가 낮다 = 현재 **15개 지표 중 여러 개가 불리한 구간**이라는 뜻입니다. 개별 팩터 점수를 확인해보세요:
- Fundamental이 낮으면 → 재무 악화 or 고평가
- Technical이 낮으면 → 최근 주가 흐름 약세
- Quant가 낮으면 → 국면/모멘텀 불리

좋아하는 종목이라도 "지금은 좋지 않다"고 **정보는 정직하게** 드립니다.

#### Q10. "법적으로 문제 없나요?"

PivoxQuant는 **투자자문업이 아닙니다** (자본시장법 제6조의 자문업 등록 X). 대신:
- "추천(recommendation)" 용어 금지 → "정보 제공"
- 시그널 라벨: BUY/SELL 금지 → **POSITIVE/NEGATIVE/NEUTRAL**
- 모든 분석 페이지에 면책 배너 필수
- KIS 주문 기능 disabled (조회 전용)
- 이용약관에 "투자 결정은 사용자 본인 책임" 명시

---

## Part 6. 기술 상세 (개발자 참고용)

### 주요 파일 위치

| 파일 | 역할 | 라인 수 |
|---|---|---|
| `engine.py` | 4-pillar 스코어링 엔진 | 1,448 |
| `quant_models.py` | 58개 퀀트 모델 + AdaptiveParams | 1,782 |
| `risk_defense.py` | 7-Layer Risk Defense | ~ |
| `backtester.py` | 백테스트 + 성과 측정 | ~ |
| `data_fetcher.py` | Alpaca→FMP 폴백, KIS 통합 | ~ |
| `ai_service.py` | Claude API 연동 | ~ |
| `routes/signals.py` | 시그널 REST API | ~ |

### 데이터 흐름 트레이스

```
GET /api/signals/:ticker
  → routes/signals.py
  → engine.QuantEngine.analyze(ticker, capital_usd, profile_params)
    → _technical(hist)              # RSI, MACD, BB, MA, Volume + 고급 9개
    → _fundamental(snapshot)        # PE, Revenue, Margin, D/E, Beta, Forward PE, EPS
    → _fetcher.score_news_sentiment # RSS 키워드
    → _quant_models(hist, profile_params)
       ├─ MeanReversion.analyze
       ├─ MomentumBreakout.analyze
       ├─ VolatilityRegime.analyze
       ├─ RegimeSwitching.analyze
       ├─ MLSignal.generate
       └─ AdaptiveParams.calculate
  → composite = weighted_sum + VIX adjustment + 52W high boost
  → ai_service.interpret(scores) [Claude API]
  → return {score, signal, factors, ai_text}
```

### 캐시 전략

- **FMP API**: TTL 캐시 (services/cache_service.py) — 분기 재무제표는 90일, 가격은 15분
- **KIS 토큰**: 24시간 재사용 (kis_token_manager.py)
- **Regime 계산**: 세션 메모리 캐시 (60초)
- **AI 해석**: ticker + score 해시 키로 6시간 캐시

### 재계산 트리거

1. 가격 업데이트 (SSE realtime_service.py) → Technical 재계산
2. 재무제표 신규 발표 → Fundamental 재계산
3. VIX 임계값 돌파 → AdaptiveParams 재계산 (전체 종목)
4. 유저 profile 변경 (investor_profiles.py) → 가중치 재조정

### 성능 최적화

- `prefetch_discover_pool()`: 디스커버 페이지용 인기 종목 50개를 백그라운드 prefetch
- `_auto_prefetch_if_needed()`: 유저가 검색할 때 관련 종목 같이 워밍업
- numpy vectorized 연산 (pandas iter 금지)
- AdaptiveParams는 `n >= 60` 체크 후 fallback 로직 적용 (데이터 부족 시 단순 모델)

---

## 🎯 이 문서 요약 (한 문장)

**"PivoxQuant는 한 종목을 볼 때 15가지 각도에서 0~100점을 매기고, 시장 국면에 따라 자동으로 기준을 조정해서, Claude AI로 한국어 설명까지 붙여주는 정보 제공 플랫폼입니다."**

---

*본 문서는 코드(engine.py, quant_models.py) 실제 기반으로 작성되었습니다. 수식/가중치가 코드와 다르면 코드가 정답입니다. 버전 관리: git log로 확인.*
