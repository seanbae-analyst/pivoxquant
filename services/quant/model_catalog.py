"""Static catalog of the 40 quant / risk / portfolio / behavioral / AI / system
models that the user can compose via Feature 1 (Quant Composer).

Source of truth
---------------
The 40-model inventory mirrors the drawer in
``frontend/src/components/landing/engine-models-drawer.tsx`` (the public
landing-page disclosure) and the audit at
``reports/audit/MODEL_INVENTORY_2026-04-23.md``. Names here MUST stay
in lock-step with the Python class names actually invoked by
:mod:`engine` and the various model modules — the composer keys on
``name`` to filter ``quant_score`` contributions per user.

Legal posture
-------------
Every ``description_kr`` and ``description_en`` is observation-only:
no "추천 / 조언 / 매수 / 매도 / buy / sell / hold / recommend / advice"
slips through (verified by :mod:`tests.test_quant_composer`).
``services.legal.forbidden_terms`` is the canonical blocklist; any
addition here must keep that test green.

Persona compatibility
---------------------
``personas_recommended`` is intentionally written as a *describing*
field — "this model is part of the X persona's typical instrument
shelf" — never as a prescription. The Persona → Quant Auto-Apply path
(Feature 2) consumes :data:`PERSONA_QUANT_PRESETS` in
:mod:`services.quant.composer`, not this list.

``data_sparse_compatible`` flags models that work well even when the
user has very little trading history (e.g., volatility regime, VIX) so
the onboarding UI can preferentially surface them on Day-1 accounts.
"""
from __future__ import annotations

from typing import Final


# Canonical category labels (six buckets) — mapped from the drawer's
# six-column display. Stored separately so the routes layer can return
# group counts to the frontend without re-deriving them.
CATEGORIES: Final[tuple[str, ...]] = (
    "Quant Edge",   # 16 models — directional / regime / breakout statistics
    "Signal",       # 5 models  — behavioral / crowding / sentiment
    "Risk",         # 6 models  — vol estimators, tail/loss attribution
    "Portfolio",    # 5 models  — weight optimizers (HRP / ERC / etc.)
    "AI",           # 3 models  — Claude-augmented synthesis nodes
    "System",       # 5 models  — orchestrator + screeners + indicators
)


# ─────────────────────────────────────────────────────────────────────
# 40-model metadata.
#
# Every entry has the exact same shape so the routes layer can serialize
# it without per-row branching:
#
#   - name                    : str   — Python class / instrument name
#   - category                : str   — one of CATEGORIES
#   - module                  : str   — the Python module the class lives in
#                                       (free-text label; not import path)
#   - description_kr          : str   — 1-line Korean observation summary
#   - description_en          : str   — 1-line English observation summary
#   - academic_source         : str   — published paper / textbook anchor
#   - default_weight          : float — neutral multiplier (always 1.0)
#   - personas_recommended    : list  — persona codes whose preset includes
#                                       this model (PERSONA_QUANT_PRESETS)
#   - data_sparse_compatible  : bool  — usable on Day-1 (no trade history)
# ─────────────────────────────────────────────────────────────────────

MODEL_CATALOG: Final[list[dict]] = [
    # ════════════════════════ Quant Edge (16) ════════════════════════
    {
        "name": "StatArb",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "쌍 종목 spread 의 OU-process 평균회귀 속도 관찰. Z-score 임계 도달 시 정보 고지.",
        "description_en": "Ornstein–Uhlenbeck mean-reversion fit on paired positions; flags spread Z-score beyond 2 standard deviations as observation.",
        "academic_source": "Avellaneda & Lee (2010), Statistical Arbitrage in the U.S. Equities Market",
        "default_weight": 1.0,
        "personas_recommended": ["quant", "speculator"],
        "data_sparse_compatible": False,
    },
    {
        "name": "MeanReversion",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "20일 Z-score 기반 평균회귀 관찰 지표. 통계적으로 stretched 된 가격 영역을 0–100 점수로 표시.",
        "description_en": "20-day Z-score against the rolling mean; produces a 0–100 stretch metric on each position.",
        "academic_source": "Ornstein–Uhlenbeck stochastic differential equation",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "value", "balanced", "quant"],
        "data_sparse_compatible": True,
    },
    {
        "name": "MomentumBreakout",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "20일 high 돌파 + 거래량 1.5× 동시 만족 관찰. ATR₂₀ 잡음 floor 적용.",
        "description_en": "Range-break observation: close above 20-day high with volume ratio above 1.5×. ATR₂₀ noise floor applied.",
        "academic_source": "Donchian / Turtle methodology",
        "default_weight": 1.0,
        "personas_recommended": ["growth", "speculator", "daytrader", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "VolatilityRegime",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "연환산 σ 분위수로 LOW / NORMAL / HIGH / CRISIS 구간 분류. 포지션 multiplier 0.2–1.3× 관찰.",
        "description_en": "Annualised σ classified against P25/P75 history into LOW / NORMAL / HIGH / CRISIS regimes.",
        "academic_source": "Standard volatility-regime literature",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "income", "value", "balanced", "growth", "quant", "speculator"],
        "data_sparse_compatible": True,
    },
    {
        "name": "RegimeSwitching",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "Rolling Sharpe state 5단계 (BULL / MILD_BULL / TRANSITION / MILD_BEAR / BEAR) 관찰.",
        "description_en": "Rolling Sharpe-state classifier with five regimes from Bull through Bear.",
        "academic_source": "Hamilton (1989), Regime-switching Markov models",
        "default_weight": 1.0,
        "personas_recommended": ["balanced", "growth", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "CrossAssetMomentum",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "SPY / TLT / GLD / USO / UUP 1개월 수익률로 RISK_ON / RISK_OFF 매크로 관찰.",
        "description_en": "Macro RISK_ON / RISK_OFF observation from a SPY / TLT / GLD / USO / UUP basket.",
        "academic_source": "Asness, Moskowitz & Pedersen (2013), Value and Momentum Everywhere",
        "default_weight": 1.0,
        "personas_recommended": ["balanced", "growth", "quant"],
        "data_sparse_compatible": True,
    },
    {
        "name": "VIXStrategy",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "VIX 5단계 밴드 (EXTREME_LOW / LOW / ELEVATED / HIGH / PANIC) 관찰. 노출 다이얼 10–100% 표시.",
        "description_en": "VIX bands (EXTREME_LOW / LOW / ELEVATED / HIGH / PANIC) drive an exposure observation 10%–100%.",
        "academic_source": "Whaley (2000), Investor Fear Gauge",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "income", "value", "balanced", "growth", "quant", "speculator"],
        "data_sparse_compatible": True,
    },
    {
        "name": "MLSignal",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "AdaBoost 15-stump ensemble. RSI / MA ratios / momentum feature 기반 BULLISH / BEARISH / NEUTRAL 관찰.",
        "description_en": "AdaBoost 15-stump ensemble over RSI, MA ratios, vol_20 and momentum features. Outputs BULLISH / BEARISH / NEUTRAL plus prob_up.",
        "academic_source": "Freund & Schapire (1997), AdaBoost",
        "default_weight": 1.0,
        "personas_recommended": ["growth", "quant", "speculator"],
        "data_sparse_compatible": False,
    },
    {
        "name": "AdaptiveParams",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "3-Layer TP/SL 엔진. ATR / regime matrix / ML confidence 합성으로 5개 프로필 자동 전환.",
        "description_en": "Three-layer TP / SL engine: ATR bands, regime matrix, ML confidence. Switches across five profiles.",
        "academic_source": "Internal — synthesis of Wilder ATR + regime literature",
        "default_weight": 1.0,
        "personas_recommended": ["balanced", "growth", "quant", "speculator", "daytrader"],
        "data_sparse_compatible": False,
    },
    {
        "name": "VarianceRatioFilter",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "Lo & MacKinlay random-walk 검정. VR > 1.2 trending, VR < 0.8 mean-reverting 관찰.",
        "description_en": "Lo & MacKinlay random-walk test. VR above 1.2 marks trending; near 1.0 random-walk; below 0.8 mean-reverting.",
        "academic_source": "Lo & MacKinlay (1988)",
        "default_weight": 1.0,
        "personas_recommended": ["quant", "balanced"],
        "data_sparse_compatible": False,
    },
    {
        "name": "TSMOM",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "12개월 time-series momentum. Strength = |Ret₁₂m| / σ₆₃ 관찰 지표.",
        "description_en": "Twelve-month time-series momentum strength = |Ret₁₂m| / σ₆₃ as an observation metric.",
        "academic_source": "Moskowitz, Ooi & Pedersen (2012), Time Series Momentum",
        "default_weight": 1.0,
        "personas_recommended": ["growth", "quant", "speculator"],
        "data_sparse_compatible": False,
    },
    {
        "name": "FiftyTwoWeekHigh",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "52주 고점 anchor 비율 관찰. ratio = P_now / max(P₋₂₅₂). 0.95 이상 POSITIVE 분류.",
        "description_en": "Anchor-proximity to the 52-week high: ratio = P_now / max(P₋₂₅₂). Above 0.95 classified POSITIVE.",
        "academic_source": "George & Hwang (2004)",
        "default_weight": 1.0,
        "personas_recommended": ["growth", "quant", "speculator"],
        "data_sparse_compatible": False,
    },
    {
        "name": "DonchianBreakout",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "Turtle 55/20 entry/exit channel 관찰. Range-break 신호의 고전적 지표.",
        "description_en": "Turtle 55/20 entry/exit channel observation. Classic range-break indicator.",
        "academic_source": "Richard Dennis, Turtle Traders (1983)",
        "default_weight": 1.0,
        "personas_recommended": ["speculator", "daytrader", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "DualMomentum",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "Absolute (Ret₁₂m > 0) 와 Relative (Ret₁₂m > SPY) 동시 충족 시 POSITIVE 관찰.",
        "description_en": "Absolute (Ret₁₂m > 0) and relative (Ret₁₂m > SPY₁₂m) momentum jointly satisfied → POSITIVE observation.",
        "academic_source": "Antonacci (2014), Dual Momentum Investing",
        "default_weight": 1.0,
        "personas_recommended": ["growth", "balanced", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "CorrelationRegime",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "60일 평균 pairwise 상관 관찰. 0.7 초과 시 분산효과 붕괴 영역 표시.",
        "description_en": "60-day average pairwise correlation across an SPY / QQQ / IWM / DIA / XLK basket; above 0.7 flags HIGH_CORRELATION.",
        "academic_source": "Longin & Solnik (2001), Extreme Correlation",
        "default_weight": 1.0,
        "personas_recommended": ["quant", "balanced", "value"],
        "data_sparse_compatible": False,
    },
    {
        "name": "InterestRateRegime",
        "category": "Quant Edge",
        "module": "quant_models",
        "description_kr": "Fed funds rate 6개월 변화로 5단계 cycle (rising_fast / rising / flat / falling / falling_fast) 관찰.",
        "description_en": "Fed-rate cycle classifier: rising_fast / rising / flat / falling / falling_fast.",
        "academic_source": "Bernanke & Blinder (1992), monetary policy regime literature",
        "default_weight": 1.0,
        "personas_recommended": ["income", "value", "balanced", "quant"],
        "data_sparse_compatible": True,
    },

    # ════════════════════════ Signal — Behavioral (5) ════════════════════════
    {
        "name": "DispositionEffect",
        "category": "Signal",
        "module": "signal_models",
        "description_kr": "Frazzini Capital-Gains-Overhang. ref = Σ(P·V)/Σ(V) 의 1년 VWAP. CGO 관찰 지표.",
        "description_en": "Frazzini Capital-Gains-Overhang. Reference price = 1-year VWAP, CGO = (P_now − ref) / ref. Observation only.",
        "academic_source": "Frazzini (2006); Shefrin & Statman (1985)",
        "default_weight": 1.0,
        "personas_recommended": ["value", "balanced", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "HerdingIntensity",
        "category": "Signal",
        "module": "signal_models",
        "description_kr": "CSAD = mean(|R_i − R_m|). 시장 극단 변동 구간의 dispersion 압축을 관찰.",
        "description_en": "Cross-sectional absolute deviation. Low dispersion under extreme moves indicates herding observation.",
        "academic_source": "Christie & Huang (1995)",
        "default_weight": 1.0,
        "personas_recommended": ["quant", "value"],
        "data_sparse_compatible": True,
    },
    {
        "name": "SentimentPriceDivergence",
        "category": "Signal",
        "module": "signal_models",
        "description_kr": "가격 ROC 와 rule-based news score 의 divergence 관찰. divergence_score = −sign_agree·magnitude.",
        "description_en": "Rate-of-change comparison between price and the rule-based news score. divergence_score = −sign_agree · magnitude.",
        "academic_source": "Tetlock (2007), Giving Content to Investor Sentiment",
        "default_weight": 1.0,
        "personas_recommended": ["quant", "growth"],
        "data_sparse_compatible": False,
    },
    {
        "name": "OrderFlowImbalance",
        "category": "Signal",
        "module": "signal_models",
        "description_kr": "Cont et al. signed-volume proxy. OFI_norm 20일 합. high_positive / high_negative 관찰.",
        "description_en": "Cont et al. (2014). OFI_daily = sign(close − open) · volume; OFI_norm summed over 20 days.",
        "academic_source": "Cont, Kukanov & Stoikov (2014)",
        "default_weight": 1.0,
        "personas_recommended": ["daytrader", "quant", "speculator"],
        "data_sparse_compatible": False,
    },
    {
        "name": "AnchoringBias",
        "category": "Signal",
        "module": "signal_models",
        "description_kr": "52주 nearness × |CGO| interaction score. 0.97–1.03× composite multiplier 관찰.",
        "description_en": "52-week nearness × |CGO| interaction score. Applies a 0.97×–1.03× composite multiplier observation.",
        "academic_source": "George & Hwang (2004), extended with Frazzini CGO",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "value", "balanced", "quant"],
        "data_sparse_compatible": False,
    },

    # ════════════════════════ Risk (6) ════════════════════════
    {
        "name": "GKYZVolatility",
        "category": "Risk",
        "module": "risk_models",
        "description_kr": "Yang & Zhang OHLC 범위 기반 변동성 추정기. close-to-close 대비 7–8× 효율적인 관찰량.",
        "description_en": "Yang & Zhang (2000) range-based OHLC variance estimator — roughly 7–8× more efficient than close-to-close.",
        "academic_source": "Yang & Zhang (2000)",
        "default_weight": 1.0,
        "personas_recommended": ["income", "value", "balanced", "growth", "quant"],
        "data_sparse_compatible": True,
    },
    {
        "name": "LedoitWolfShrinkage",
        "category": "Risk",
        "module": "risk_models",
        "description_kr": "공분산 shrinkage. α = b̄²/d̄² Frobenius-loss minimizer. Σ_shrunk = (1−α)·S + α·F.",
        "description_en": "Ledoit & Wolf (2004) covariance shrinkage. Used as the Σ input for portfolio optimisers.",
        "academic_source": "Ledoit & Wolf (2004)",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "value", "balanced", "quant"],
        "data_sparse_compatible": True,
    },
    {
        "name": "ComponentES",
        "category": "Risk",
        "module": "risk_models",
        "description_kr": "Tasche Euler decomposition. ES_i = w_i·E[r_i | r_port ≤ VaR_α]. 좌측 tail 손실 기여 관찰.",
        "description_en": "Tasche (2002) Euler decomposition. ES_i = w_i · E[r_i | r_port ≤ VaR_α]; Σ ES_i = portfolio ES.",
        "academic_source": "Tasche (2002)",
        "default_weight": 1.0,
        "personas_recommended": ["value", "balanced", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "ConditionalDrawdown",
        "category": "Risk",
        "module": "risk_models",
        "description_kr": "CDDaR = mean(DD over worst α%). Tail-side maximum drawdown 관찰.",
        "description_en": "Conditional drawdown-at-risk: mean drawdown across the worst α% of the time-series.",
        "academic_source": "Chekhlov, Uryasev & Zabarankin (2005)",
        "default_weight": 1.0,
        "personas_recommended": ["income", "value", "balanced", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "TailRatio",
        "category": "Risk",
        "module": "risk_models",
        "description_kr": "ratio = |P95(returns)| / |P5(returns)|. 1 이상이면 우측 tail 두께 우위 관찰.",
        "description_en": "ratio = |P95(returns)| / |P5(returns)|. Values above 1 indicate a thicker right tail.",
        "academic_source": "Empirical asymmetry literature",
        "default_weight": 1.0,
        "personas_recommended": ["growth", "quant", "speculator"],
        "data_sparse_compatible": False,
    },
    {
        "name": "SortinoByPosition",
        "category": "Risk",
        "module": "risk_models",
        "description_kr": "Sortino = (E[r] − r_f) / downside_dev. Sharpe 와 달리 하방 변동성만 페널라이즈한 관찰.",
        "description_en": "Sortino = (E[r] − r_f) / downside_dev. Penalises only downside volatility unlike Sharpe.",
        "academic_source": "Sortino et al. (1991)",
        "default_weight": 1.0,
        "personas_recommended": ["income", "value", "balanced", "quant"],
        "data_sparse_compatible": False,
    },

    # ════════════════════════ Portfolio (5) ════════════════════════
    {
        "name": "HRP",
        "category": "Portfolio",
        "module": "portfolio_models",
        "description_kr": "Hierarchical Risk Parity. Distance √(½(1−corr)) → single-linkage → 재귀 bisection. 공분산 역행렬 불필요.",
        "description_en": "Hierarchical Risk Parity. Distance √(½(1−corr)), single-linkage, recursive bisection with inverse-variance weights.",
        "academic_source": "López de Prado (2016)",
        "default_weight": 1.0,
        "personas_recommended": ["balanced", "growth", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "TailRiskParity",
        "category": "Portfolio",
        "module": "portfolio_models",
        "description_kr": "각 자산의 CVaR 기여 균등화. Component CVaR_i = w_i·E[r_i | r_port ≤ VaR_α].",
        "description_en": "Equalises each asset's CVaR contribution: component CVaR_i = w_i · E[r_i | r_port ≤ VaR_α].",
        "academic_source": "Boudt, Carl & Peterson (2013)",
        "default_weight": 1.0,
        "personas_recommended": ["value", "balanced", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "MaxDiversification",
        "category": "Portfolio",
        "module": "portfolio_models",
        "description_kr": "Diversification Ratio DR = (w′σ)/√(w′Σw) 최대화. Ledoit-Wolf Σ 사용.",
        "description_en": "Choueifaty & Coignard diversification ratio DR = (w′σ) / √(w′Σw); maximised with Ledoit-Wolf Σ.",
        "academic_source": "Choueifaty & Coignard (2008)",
        "default_weight": 1.0,
        "personas_recommended": ["balanced", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "EqualRiskContribution",
        "category": "Portfolio",
        "module": "portfolio_models",
        "description_kr": "Risk parity. 각 자산이 포트폴리오 분산에 동일하게 기여하도록 30회 iter 조정.",
        "description_en": "Risk-parity portfolio: every asset contributes equally to portfolio variance after a 30-iteration adjustment.",
        "academic_source": "Maillard, Roncalli & Teiletche (2010)",
        "default_weight": 1.0,
        "personas_recommended": ["income", "balanced", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "MinVariance",
        "category": "Portfolio",
        "module": "portfolio_models",
        "description_kr": "Markowitz long-only 최소분산. w* = Σ⁻¹·1 / (1′Σ⁻¹·1). ε = 1e-8 singular guard.",
        "description_en": "Markowitz long-only minimum-variance solution w* = Σ⁻¹·1 / (1′Σ⁻¹·1) with a singular-matrix guard ε = 1e-8.",
        "academic_source": "Markowitz (1952)",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "income", "value", "balanced", "quant"],
        "data_sparse_compatible": True,
    },

    # ════════════════════════ AI (3) ════════════════════════
    {
        "name": "EarningsCallToneAnalyzer",
        "category": "AI",
        "module": "ai_models",
        "description_kr": "Claude Haiku 4.5 의 어닝스 콜 텍스트 톤 관찰. confidence / hedging / tone_shift JSON 산출.",
        "description_en": "Claude Haiku 4.5 over earnings transcripts. Loughran-McDonald style — JSON: confidence, hedging_frequency, tone_shift, conviction_score.",
        "academic_source": "Loughran & McDonald (2011)",
        "default_weight": 1.0,
        "personas_recommended": ["growth", "quant"],
        "data_sparse_compatible": True,
    },
    {
        "name": "AISectorRotation",
        "category": "AI",
        "module": "ai_models",
        "description_kr": "Claude Haiku 4.5 가 VIX / SP500 / 금리 / USD-KRW 입력으로 6단계 사이클 관찰.",
        "description_en": "Claude Haiku 4.5 over VIX, SP500, rates, and USD/KRW. Six cycle stages from Early Recovery to Crisis.",
        "academic_source": "Sector-rotation cycle literature",
        "default_weight": 1.0,
        "personas_recommended": ["balanced", "growth", "quant"],
        "data_sparse_compatible": True,
    },
    {
        "name": "AIRiskSummary",
        "category": "AI",
        "module": "ai_models",
        "description_kr": "Claude Haiku 4.5 가 vol / VaR / MDD / Sharpe / 집중도 5개 metric 합성한 요약 관찰.",
        "description_en": "Claude Haiku 4.5 synthesises vol, VaR, MDD, Sharpe and concentration into a structured risk summary.",
        "academic_source": "Synthesis layer — no single anchor",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "income", "value", "balanced", "growth", "quant"],
        "data_sparse_compatible": True,
    },

    # ════════════════════════ System — Screeners + Orchestrator (5) ════════════════════════
    {
        "name": "CANSLIMScreener",
        "category": "System",
        "module": "canslim",
        "description_kr": "William O'Neil 7-factor 스크리너. C/A/N/S/L/I/M 7가지 조건의 동시 충족 관찰.",
        "description_en": "William O'Neil 7-factor screener: C, A, N, S, L, I, M — observed jointly per ticker.",
        "academic_source": "William O'Neil — CAN SLIM",
        "default_weight": 1.0,
        "personas_recommended": ["growth", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "RiskDefenseSystem",
        "category": "System",
        "module": "risk_defense",
        "description_kr": "7-Layer 회로차단기. VaR / 상관 spike / VIX / tail-attribution / 일일 손실 / 섹터 집중 / 현금 buffer 관찰.",
        "description_en": "Seven-layer circuit breakers: VaR ceiling, correlation spike, VIX trigger level, tail attribution, daily loss, sector concentration, cash buffer.",
        "academic_source": "Internal — synthesis of risk-control literature",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "income", "value", "balanced", "growth", "quant", "speculator", "daytrader"],
        "data_sparse_compatible": True,
    },
    {
        "name": "QuantEngine",
        "category": "System",
        "module": "engine",
        "description_kr": "4-pillar composite orchestrator. Technical / Fundamental / News / Quant 4개 기둥의 0–100 합성 점수.",
        "description_en": "Four-pillar composite orchestrator. Technical / Fundamental / News / Quant pillars assembled into a 0–100 score.",
        "academic_source": "Multi-factor framework (Fama-French extension)",
        "default_weight": 1.0,
        "personas_recommended": ["beginner", "income", "value", "balanced", "growth", "quant", "speculator", "daytrader"],
        "data_sparse_compatible": True,
    },
    {
        "name": "AdditionalIndicators",
        "category": "System",
        "module": "indicators",
        "description_kr": "10개 기술 overlay: Donchian / Supertrend / PSAR / CMF / A-D / Pivot / ATR Bands / VWAP / Heikin-Ashi / Keltner.",
        "description_en": "Ten technical overlays — Donchian, Supertrend, Parabolic SAR, CMF, A/D Line, Pivots, ATR Bands, VWAP, Heikin-Ashi, Keltner Width.",
        "academic_source": "Wilder, Donchian and standard TA literature",
        "default_weight": 1.0,
        "personas_recommended": ["daytrader", "speculator", "growth", "quant"],
        "data_sparse_compatible": False,
    },
    {
        "name": "AdditionalFundamentals",
        "category": "System",
        "module": "indicators",
        "description_kr": "8개 펀더멘털 비율: PEG / P/S / P/B / FCF Yield / ROE / ROA / Current Ratio / Interest Coverage.",
        "description_en": "Eight fundamental ratios — PEG, P/S, P/B, FCF Yield, ROE, ROA, Current Ratio, Interest Coverage.",
        "academic_source": "Standard fundamental-analysis textbooks",
        "default_weight": 1.0,
        "personas_recommended": ["income", "value", "balanced", "quant"],
        "data_sparse_compatible": True,
    },
]

# Index by name for O(1) lookup. Frozen at import time.
MODEL_BY_NAME: Final[dict[str, dict]] = {m["name"]: m for m in MODEL_CATALOG}


# Sanity invariant — break loudly if the catalog drifts away from the
# 40-model contract (mirrored in the public landing page drawer).
assert len(MODEL_CATALOG) == 40, (
    f"MODEL_CATALOG must contain exactly 40 models; found {len(MODEL_CATALOG)}"
)
assert len(MODEL_BY_NAME) == 40, "Duplicate model names detected in MODEL_CATALOG"


__all__ = ["MODEL_CATALOG", "MODEL_BY_NAME", "CATEGORIES"]
