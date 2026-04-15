"""
PivoxQuant -- Investor Profile Strategy Mapping System
Maps 8 investor types to complete quant parameter sets.

This module is the bridge between the onboarding questionnaire (questionnaire.py)
and the quant engine (engine.py, backtester.py, autotrader.py).

Each profile defines:
  1. Scoring weights     -- how much each analysis pillar matters
  2. Entry/exit params   -- thresholds, TP/SL modes, trail widths
  3. Position sizing     -- concentration, max positions, rebalance cadence
  4. Model selection     -- which quant models to activate
  5. Risk controls       -- drawdown halts, daily loss limits
  6. AdaptiveParams mod  -- how to adjust the 3-Layer engine per profile

Architecture:
  questionnaire.py  ->  calculate_profile_v2()  ->  investor_type (str)
  investor_profiles.py  ->  get_profile_params(investor_type)  ->  full param dict
  engine.py  ->  analyze(profile_params=...)
  backtester.py  ->  run(profile_params=...)

Design Principles:
  - All numeric params are derived from backtested ranges, not guesswork
  - Weights must sum to 1.0 (tech + fund + news + quant)
  - TP/SL are ATR multiples, not fixed percentages
  - More conservative profiles have WIDER stops (counterintuitive but correct:
    they trade less frequently, so each trade needs more room)
  - Aggressive profiles have TIGHTER stops but higher win-rate requirements
"""

from decimal import Decimal


# =============================================================================
# INVESTOR PROFILE PARAMETERS
# =============================================================================
#
# Parameter justification guide (why each number):
#
# Scoring weights (must sum to 1.0):
#   tech_weight  -- Technical analysis (RSI, MACD, Bollinger, MA, Volume)
#   fund_weight  -- Fundamental analysis (P/E, Revenue Growth, Margins)
#   news_weight  -- News/sentiment (RSS keyword scoring, VIX proxy)
#   quant_weight -- Quant models (MeanReversion, Momentum, Regime, ML)
#
# Entry/Exit:
#   buy_threshold   -- min composite score to enter (0-100)
#   sell_threshold   -- score below which to exit (0-100)
#   tp_mode         -- "normal" (fixed TP target) or "trail_only" (no TP cap)
#   tp_mult         -- ATR multiplier for take-profit (higher = wider TP)
#   sl_mult         -- ATR multiplier for stop-loss
#   trail_mult      -- ATR multiplier for trailing stop width
#   tp_min / tp_max -- absolute clamp range for TP% (profile safety bounds)
#   sl_min / sl_max -- absolute clamp range for SL%
#
# Position sizing:
#   max_position_pct -- max % of portfolio in a single position
#   max_positions    -- max concurrent positions
#   rebalance_days   -- how often to rebalance (in trading days)
#   position_kelly_frac -- Kelly fraction multiplier (1.0 = full Kelly, <1 = fractional)
#
# Model activation:
#   use_tsmom          -- Time-series momentum (12m lookback)
#   use_vr_filter      -- Variance ratio filter (random walk test)
#   use_52wk_high      -- 52-week high momentum boost
#   use_stat_arb       -- OU pairs trading
#   use_mean_reversion -- Mean reversion z-score
#   use_regime_switch  -- Markov regime switching
#   use_ml_signal      -- AdaBoost ML ensemble
#   use_cross_asset    -- Cross-asset macro momentum
#   use_vix_strategy   -- VIX-based exposure scaling
#
# Risk controls:
#   max_drawdown_halt_pct  -- halt all trading if portfolio DD exceeds this
#   daily_loss_halt_pct    -- halt for the day if daily loss exceeds this (None = disabled)
#   max_daily_trades       -- max trades per day (circuit breaker)
#   leverage_allowed       -- whether margin/leveraged ETFs are permitted
#   max_leverage           -- max leverage ratio (1.0 = no leverage)
#
# Adaptive params modifier:
#   adaptive_aggression    -- multiplier on AdaptiveParams ATR scaling
#                             >1.0 = wider exits, <1.0 = tighter exits
#   regime_sensitivity     -- how strongly regime shifts affect the profile
#                             0.0 = ignore regime, 1.0 = full regime adaptation
#   ml_trust               -- how much to trust ML signal adjustments
#                             0.0 = ignore ML, 1.0 = full ML adjustment

INVESTOR_PROFILES: dict[str, dict] = {

    # =========================================================================
    # 1. PASSIVE INDEX HUGGER
    # =========================================================================
    # Goal: Beat the index by 1-2% with minimal effort.
    # Philosophy: Buy quality, hold forever, rebalance quarterly.
    # Benchmark: SPY total return + 1-2% alpha
    #
    # Weight rationale:
    #   fund_weight=0.40 -- fundamentals dominate for long-term holds
    #   quant_weight=0.42 -- quant models filter regime risk (avoid buying at tops)
    #   tech_weight=0.15 -- minimal technical timing (just MA cross for entry)
    #   news_weight=0.03 -- news is noise for long-term holders
    #
    # buy_threshold=85: ultra-selective. Only enter when fundamentals AND quant
    #   models agree very strongly. Fewer trades, highest conviction only.
    # sell_threshold=15: extremely slow to sell. Only exit on severe deterioration.
    # trail_mult=8.0: very wide trailing stop. Gives positions room for 15-20%
    #   pullbacks within larger uptrends (normal for index components).
    # sl_mult=4.0: wide stop loss. Passive holders accept -8 to -12% drawdowns
    #   on individual positions as the cost of holding through volatility.
    # max_positions=10: diversified enough to approximate index behavior.
    # rebalance_days=63: quarterly (63 trading days). Minimizes turnover and
    #   transaction cost drag.
    # =========================================================================
    "passive_index_hugger": {
        # -- Scoring weights (sum = 1.0) --
        "tech_weight": 0.15,
        "fund_weight": 0.40,
        "news_weight": 0.03,
        "quant_weight": 0.42,

        # -- Entry / Exit --
        "buy_threshold": 85,
        "sell_threshold": 15,
        "tp_mode": "trail_only",
        "tp_mult": 999.0,       # no fixed TP -- let winners compound for years
        "sl_mult": 4.0,         # wide SL: 4x ATR ~ 8-12% for typical large caps
        "trail_mult": 8.0,      # very wide trail: 8x ATR ~ 16-24%. Maximum patience.
        "tp_min": 5.0,
        "tp_max": 999.0,        # no cap on upside
        "sl_min": 5.0,
        "sl_max": 15.0,         # never let a single loss exceed 15%

        # -- Position sizing --
        "max_position_pct": 15,  # max 15% per position (diversified)
        "max_positions": 10,
        "rebalance_days": 90,    # ~quarterly+ (90 trading days). Minimizes turnover further.
        "position_kelly_frac": 0.25,  # quarter-Kelly: ultra-conservative sizing

        # -- Model activation --
        "use_tsmom": True,        # 12m momentum filter: avoid buying losers
        "use_vr_filter": False,   # not relevant for long-term
        "use_52wk_high": True,    # prefer stocks near highs (momentum premium)
        "use_stat_arb": False,    # no pairs trading
        "use_mean_reversion": False,  # passive holders ride trends, not reversals
        "use_regime_switch": True,    # avoid entering during bear regimes
        "use_ml_signal": False,       # ML adds noise for quarterly rebalancing
        "use_cross_asset": True,      # macro awareness for timing entries
        "use_vix_strategy": True,     # scale exposure with VIX
        "use_disposition": False,     # behavioral noise irrelevant for passive
        "use_ofi": False,             # order flow irrelevant for long-term
        "use_anchoring": True,        # near 52wk high = quality confirmation
        "use_sentiment_div": False,   # sentiment noise for passive holders

        # -- Risk controls --
        "max_drawdown_halt_pct": 20,  # halt at -20% portfolio DD
        "daily_loss_halt_pct": None,  # no daily limit (long-term perspective)
        "max_daily_trades": 2,
        "leverage_allowed": False,
        "max_leverage": 1.0,

        # -- Adaptive params modifier --
        "adaptive_aggression": 1.3,    # wider exits than default (more patient)
        "regime_sensitivity": 0.4,     # muted regime response (don't panic-sell)
        "ml_trust": 0.0,              # ignore ML noise

        # -- UI/UX --
        "ai_coaching_style": "educational",
        "alert_frequency": "weekly",
        "scan_interval_sec": 3600,     # check once per hour

        # -- Description --
        "description": "Minimal trading. Wide stops. Let winners compound for years. Quarterly rebalance.",
        "description_kr": "최소 거래. 넓은 손절선. 수익은 복리로 성장시킴. 분기별 리밸런싱.",
    },

    # =========================================================================
    # 2. STEADY ACCUMULATOR
    # =========================================================================
    # Goal: Monthly DCA into quality stocks, moderate growth, low volatility.
    # Philosophy: Time in market beats timing the market. Compound steadily.
    # Benchmark: 10-15% annualized with max DD under 15%.
    #
    # Weight rationale:
    #   fund_weight=0.38 -- still fundamental-driven for quality selection
    #   quant_weight=0.35 -- quant models help with entry timing within DCA cycle
    #   tech_weight=0.22 -- more tech than passive (uses RSI for DCA timing)
    #   news_weight=0.05 -- slight news awareness (avoid buying into bad news)
    #
    # buy_threshold=76: more selective than before. DCA still buys regularly,
    #   but higher bar filters out marginal setups and reduces churn.
    # sell_threshold=20: patient seller. Only exit clear underperformers.
    # trail_mult=6.0: wide trail aligned with passive patience. Monthly review cadence
    #   means faster response to deterioration.
    # rebalance_days=21: monthly (21 trading days). Aligns with DCA schedule.
    # =========================================================================
    "steady_accumulator": {
        "tech_weight": 0.22,
        "fund_weight": 0.38,
        "news_weight": 0.05,
        "quant_weight": 0.35,

        "buy_threshold": 76,
        "sell_threshold": 20,
        "tp_mode": "trail_only",
        "tp_mult": 999.0,
        "sl_mult": 3.5,          # 3.5x ATR ~ 7-10% for quality large caps
        "trail_mult": 6.0,       # 6x ATR ~ 12-18%. Wider trail reduces whipsaw exits.
        "tp_min": 5.0,
        "tp_max": 999.0,
        "sl_min": 4.0,
        "sl_max": 12.0,

        "max_position_pct": 15,
        "max_positions": 12,
        "rebalance_days": 21,     # monthly
        "position_kelly_frac": 0.30,

        "use_tsmom": True,
        "use_vr_filter": False,
        "use_52wk_high": True,
        "use_stat_arb": False,
        "use_mean_reversion": True,   # buy the dip within DCA (mild MR timing)
        "use_regime_switch": True,
        "use_ml_signal": False,
        "use_cross_asset": True,
        "use_vix_strategy": True,
        "use_disposition": True,      # disposition helps find retail selling pressure dips for DCA timing
        "use_ofi": False,             # order flow irrelevant for monthly DCA
        "use_anchoring": True,        # anchoring confirms quality near 52wk highs
        "use_sentiment_div": False,   # sentiment noise for steady accumulators

        "max_drawdown_halt_pct": 18,
        "daily_loss_halt_pct": None,
        "max_daily_trades": 3,
        "leverage_allowed": False,
        "max_leverage": 1.0,

        "adaptive_aggression": 1.15,
        "regime_sensitivity": 0.5,
        "ml_trust": 0.0,

        "ai_coaching_style": "balanced",
        "alert_frequency": "daily",
        "scan_interval_sec": 1800,

        "description": "Monthly DCA with quality filter. Wide trailing stops. Compound steadily.",
        "description_kr": "월간 적립식 투자 + 품질 필터. 넓은 트레일링 스톱. 꾸준한 복리 성장.",
    },

    # =========================================================================
    # 3. SWING TRADER
    # =========================================================================
    # Goal: Capture multi-day to multi-week price swings.
    # Philosophy: Technical setups + momentum confirmation. Active management.
    # Benchmark: 15-25% annualized, Sharpe > 1.0
    #
    # Weight rationale:
    #   tech_weight=0.40 -- technical patterns drive swing entry/exit
    #   quant_weight=0.35 -- quant models for momentum confirmation
    #   fund_weight=0.18 -- fundamentals as quality filter (avoid junk rallies)
    #   news_weight=0.07 -- news catalysts can trigger swings
    #
    # buy_threshold=70: slightly more selective to reduce overtrading on marginal
    #   setups. Still enough opportunities for active swing traders.
    # sell_threshold=28: active sell discipline. Exit when setup breaks down.
    # tp_mult=12.0: wider TP target. Lets winning swings run further before capping.
    # sl_mult=2.5: tighter stop than passive. Swing trades have defined risk.
    # trail_mult=4.0: wider trail reduces premature exits on intra-swing noise.
    # max_positions=8: focused but not concentrated. Enough to diversify sectors.
    # rebalance_days=7: weekly review cycle matches swing holding period.
    # =========================================================================
    "swing_trader": {
        "tech_weight": 0.40,
        "fund_weight": 0.18,
        "news_weight": 0.07,
        "quant_weight": 0.35,

        "buy_threshold": 70,
        "sell_threshold": 28,
        "tp_mode": "normal",
        "tp_mult": 12.0,         # 12x ATR ~ wider TP. Let winners run further.
        "sl_mult": 2.5,          # 2.5x ATR ~ 5-7.5% SL
        "trail_mult": 4.0,       # 4x ATR trail. Wider to survive intra-swing noise.
        "tp_min": 6.0,
        "tp_max": 22.0,
        "sl_min": 3.0,
        "sl_max": 8.0,

        "max_position_pct": 20,
        "max_positions": 8,
        "rebalance_days": 7,
        "position_kelly_frac": 0.40,

        "use_tsmom": True,
        "use_vr_filter": True,    # filter random walks (no trend = no swing)
        "use_52wk_high": True,
        "use_stat_arb": False,
        "use_mean_reversion": True,   # buy oversold bounces
        "use_regime_switch": True,
        "use_ml_signal": True,        # ML helps with swing timing
        "use_cross_asset": False,     # stock-level focus
        "use_vix_strategy": True,
        "use_disposition": True,      # disposition effect useful for swing timing
        "use_ofi": True,              # order flow confirms swing entry/exit
        "use_anchoring": True,        # 52wk high anchoring boosts near highs
        "use_sentiment_div": True,    # sentiment divergence signals swing reversals

        "max_drawdown_halt_pct": 22,
        "daily_loss_halt_pct": 4,     # halt at -4% daily loss
        "max_daily_trades": 8,
        "leverage_allowed": True,
        "max_leverage": 1.5,

        "adaptive_aggression": 1.0,   # default adaptive behavior
        "regime_sensitivity": 0.8,    # responsive to regime changes
        "ml_trust": 0.6,

        "ai_coaching_style": "opportunity",
        "alert_frequency": "realtime",
        "scan_interval_sec": 300,

        "description": "Multi-day to multi-week swings. Technical setups + momentum. Active risk management.",
        "description_kr": "수일~수주 스윙 매매. 기술적 셋업 + 모멘텀. 적극적 리스크 관리.",
    },

    # =========================================================================
    # 4. MOMENTUM RIDER
    # =========================================================================
    # Goal: Ride strong price trends for weeks to months.
    # Philosophy: "The trend is your friend." Never cap winners. Cut losers fast.
    # Benchmark: 20-35% annualized but with higher DD tolerance (25%+).
    #
    # Weight rationale:
    #   tech_weight=0.30 -- technical for entry timing and trend confirmation
    #   quant_weight=0.50 -- quant models are primary signal (TSMOM, 52wk high)
    #   fund_weight=0.15 -- minimal fundamentals (momentum ignores value)
    #   news_weight=0.05 -- news can confirm/deny momentum thesis
    #
    # buy_threshold=75: more selective entry. Filters out weak momentum setups
    #   that would generate whipsaws. Strong momentum still enters easily.
    # trail_mult=7.0: very wide trailing stop. Momentum stocks have violent pullbacks
    #   within uptrends. 7x ATR gives 14-21% room. Widens 75% per 100% gain.
    # sl_mult=3.0: moderate stop. Cut losers before they become deep losses.
    # max_positions=5: concentrated. Momentum works best with conviction bets.
    # rebalance_days=10: bi-weekly scan for new momentum candidates.
    # =========================================================================
    "momentum_rider": {
        "tech_weight": 0.30,
        "fund_weight": 0.15,
        "news_weight": 0.05,
        "quant_weight": 0.50,

        "buy_threshold": 75,
        "sell_threshold": 30,
        "tp_mode": "trail_only",
        "tp_mult": 999.0,        # never cap gains -- ride the trend
        "sl_mult": 3.0,          # 3x ATR ~ 6-9% initial stop
        "trail_mult": 7.0,       # 7x ATR ~ 14-21% trail. Widens 75% per 100% gain.
        "tp_min": 8.0,
        "tp_max": 999.0,
        "sl_min": 4.0,
        "sl_max": 12.0,

        "max_position_pct": 30,   # concentrated bets on trending stocks
        "max_positions": 5,
        "rebalance_days": 10,     # bi-weekly
        "position_kelly_frac": 0.50,  # half-Kelly (aggressive but not reckless)

        "use_tsmom": True,        # PRIMARY signal for this profile
        "use_vr_filter": True,    # filter stocks in random walk (no trend)
        "use_52wk_high": True,    # stocks near highs have momentum premium
        "use_stat_arb": False,
        "use_mean_reversion": False,  # momentum is anti-mean-reversion
        "use_regime_switch": True,
        "use_ml_signal": True,
        "use_cross_asset": False,
        "use_vix_strategy": True,
        "use_disposition": False,     # disposition is contrarian -- conflicts with momentum
        "use_ofi": True,              # OFI confirms momentum with institutional flow
        "use_anchoring": True,        # anchoring boosts score near 52wk highs
        "use_sentiment_div": True,    # sentiment divergence warns of momentum exhaustion

        "max_drawdown_halt_pct": 28,  # higher tolerance for trend followers
        "daily_loss_halt_pct": 5,
        "max_daily_trades": 6,
        "leverage_allowed": True,
        "max_leverage": 1.5,

        "adaptive_aggression": 1.1,
        "regime_sensitivity": 0.9,    # very responsive to regime (momentum = regime-dependent)
        "ml_trust": 0.7,

        "ai_coaching_style": "aggressive",
        "alert_frequency": "realtime",
        "scan_interval_sec": 300,

        "description": "Ride strong trends. Trail-only exits. Never cap winners. Cut losers fast.",
        "description_kr": "강한 추세 추종. 트레일링만 사용. 수익 제한 없음. 손실은 빠르게 차단.",
    },

    # =========================================================================
    # 5. VALUE HUNTER
    # =========================================================================
    # Goal: Buy undervalued stocks, hold through temporary drawdowns.
    # Philosophy: "Be fearful when others are greedy, greedy when others are fearful."
    # Benchmark: 12-20% annualized with lower volatility than market.
    #
    # Weight rationale:
    #   fund_weight=0.45 -- fundamentals are THE signal (P/E, margins, FCF)
    #   quant_weight=0.30 -- quant models confirm value (mean reversion, VR filter)
    #   tech_weight=0.18 -- technical only for entry timing on value setups
    #   news_weight=0.07 -- contrarian: bad news on good company = opportunity
    #
    # buy_threshold=70: slightly lower bar for contrarian entries. Value stocks
    #   often have low tech scores (downtrend), so fund + quant must compensate.
    # sell_threshold=18: very patient seller. Value thesis takes months to play out.
    # trail_mult=6.0: wide trail. Value stocks can be volatile as the market
    #   re-rates them. Wider trail avoids being shaken out prematurely.
    # sl_mult=4.0: wide stop. Value investors accept drawdowns if thesis holds.
    # max_positions=10: moderate diversification across value opportunities.
    # rebalance_days=21: monthly. Value changes slowly; no need for frequent review.
    # =========================================================================
    "value_hunter": {
        "tech_weight": 0.18,
        "fund_weight": 0.45,
        "news_weight": 0.07,
        "quant_weight": 0.30,

        "buy_threshold": 70,
        "sell_threshold": 18,
        "tp_mode": "trail_only",
        "tp_mult": 999.0,
        "sl_mult": 4.0,          # 4x ATR ~ 8-12%. Wide -- value takes time.
        "trail_mult": 6.0,       # 6x ATR ~ 12-18%. Wider for re-rating volatility.
        "tp_min": 8.0,
        "tp_max": 999.0,
        "sl_min": 5.0,
        "sl_max": 15.0,

        "max_position_pct": 20,
        "max_positions": 10,
        "rebalance_days": 21,
        "position_kelly_frac": 0.35,

        "use_tsmom": False,       # value stocks often have negative momentum
        "use_vr_filter": True,    # confirm mean-reverting behavior
        "use_52wk_high": False,   # value stocks are often FAR from 52wk highs
        "use_stat_arb": False,
        "use_mean_reversion": True,   # PRIMARY: buy when z-score < -2
        "use_regime_switch": True,
        "use_ml_signal": False,       # ML tends to be momentum-biased; counterproductive here
        "use_cross_asset": True,      # macro matters for value rotation
        "use_vix_strategy": True,
        "use_disposition": True,      # disposition = contrarian signal (retail panic selling = buy)
        "use_ofi": False,             # order flow irrelevant for value thesis
        "use_anchoring": False,       # value stocks are far from 52wk highs by definition
        "use_sentiment_div": True,    # sentiment divergence = value trap filter

        "max_drawdown_halt_pct": 22,
        "daily_loss_halt_pct": None,  # value investors don't day-trade
        "max_daily_trades": 3,
        "leverage_allowed": False,
        "max_leverage": 1.0,

        "adaptive_aggression": 1.2,   # wider than default (patient)
        "regime_sensitivity": 0.5,    # moderate: value works in all regimes but timing differs
        "ml_trust": 0.0,

        "ai_coaching_style": "analytical",
        "alert_frequency": "daily",
        "scan_interval_sec": 1800,

        "description": "Contrarian fundamental buyer. Wide stops. Holds through drawdowns if thesis intact.",
        "description_kr": "역발상 펀더멘탈 매수. 넓은 손절. 투자 논리가 유효하면 하락도 견딤.",
    },

    # =========================================================================
    # 6. RISK-MANAGED GROWTH
    # =========================================================================
    # Goal: Above-market returns with HARD drawdown limits.
    # Philosophy: Growth with a seatbelt. Never let a position ruin the portfolio.
    # Benchmark: 15-25% annualized with max DD capped at 15%.
    #
    # Weight rationale:
    #   quant_weight=0.38 -- quant models for timing and risk signals
    #   tech_weight=0.30 -- technical for precise entry/exit (tighter stops need better timing)
    #   fund_weight=0.25 -- fundamental quality filter (avoid fragile companies)
    #   news_weight=0.07 -- news for risk events
    #
    # buy_threshold=72: slightly higher bar. More selective to reduce drawdown risk.
    # sell_threshold=32: faster exit discipline. Exits sooner to protect against drawdown.
    # tp_mult=5.0: normal mode with defined TP target.
    # sl_mult=2.0: TIGHT stop. This is the defining feature: hard loss limit.
    # trail_mult=3.0: moderate trail. Locks in gains efficiently.
    # max_drawdown_halt_pct=12: EARLY halt at 12% to stay safely below 15% MDD cap.
    # daily_loss_halt_pct=3: also daily circuit breaker.
    # =========================================================================
    "risk_managed_growth": {
        "tech_weight": 0.30,
        "fund_weight": 0.25,
        "news_weight": 0.07,
        "quant_weight": 0.38,

        "buy_threshold": 72,
        "sell_threshold": 32,
        "tp_mode": "normal",
        "tp_mult": 5.0,          # 5x ATR ~ 10-15% TP target
        "sl_mult": 2.0,          # 2x ATR ~ 4-6%. TIGHT. Defining feature.
        "trail_mult": 3.0,       # 3x ATR ~ 6-9% trail. Keep tight for DD control.
        "tp_min": 6.0,
        "tp_max": 20.0,
        "sl_min": 3.0,
        "sl_max": 7.0,           # hard cap: no single loss > 7%

        "max_position_pct": 12,   # no single position dominates
        "max_positions": 15,
        "rebalance_days": 10,     # bi-weekly
        "position_kelly_frac": 0.35,

        "use_tsmom": True,
        "use_vr_filter": True,
        "use_52wk_high": True,
        "use_stat_arb": False,
        "use_mean_reversion": True,
        "use_regime_switch": True,
        "use_ml_signal": True,
        "use_cross_asset": True,
        "use_vix_strategy": True,     # scales exposure with VIX -- critical for risk mgmt
        "use_disposition": True,      # disposition helps detect retail panic for risk awareness
        "use_ofi": True,              # OFI detects institutional selling pressure early
        "use_anchoring": True,        # anchoring confirms quality positions near highs
        "use_sentiment_div": True,    # sentiment divergence = early risk warning

        "max_drawdown_halt_pct": 12,  # HARD 12% DD halt -- early stop to stay below 15% cap
        "daily_loss_halt_pct": 3,     # tight daily limit
        "max_daily_trades": 5,
        "leverage_allowed": False,
        "max_leverage": 1.0,

        "adaptive_aggression": 0.75,  # even tighter exits for hard DD control
        "regime_sensitivity": 1.0,    # fully responsive (de-risk in bear regimes)
        "ml_trust": 0.5,

        "ai_coaching_style": "balanced",
        "alert_frequency": "daily",
        "scan_interval_sec": 900,

        "description": "Growth with hard drawdown limits. Tight stops. Portfolio-level circuit breaker at -12%.",
        "description_kr": "엄격한 하방 보호 성장투자. 타이트한 손절. 포트폴리오 -12%에서 자동 중단.",
    },

    # =========================================================================
    # 7. AGGRESSIVE SCALPER
    # =========================================================================
    # Goal: Frequent small profits from short-term price moves.
    # Philosophy: High win rate, small gains, even smaller losses. Volume = edge.
    # Benchmark: 25-50% annualized, very high turnover, tight drawdowns.
    #
    # Weight rationale:
    #   tech_weight=0.50 -- technical analysis dominates short-term price action
    #   quant_weight=0.35 -- quant for momentum/volatility regime (which environments favor scalping)
    #   news_weight=0.10 -- news creates the volatility scalpers need
    #   fund_weight=0.05 -- fundamentals are irrelevant for minutes-to-hours holding
    #
    # buy_threshold=63: slightly higher bar. Reduces noise trades while keeping
    #   enough volume. The edge still comes from tight risk management.
    # sell_threshold=35: aggressive exit. Leave at first sign of trouble.
    # tp_mult=2.5: tight TP. Take the money and run. 2.5x ATR ~ 5-7.5%.
    # sl_mult=1.5: VERY tight stop. 1.5x ATR ~ 3-4.5%. Max loss per trade is small.
    # trail_mult=2.0: tight trail for locking in quick gains.
    # max_positions=5: focused. Scalpers can't monitor 15 positions.
    # rebalance_days=1: daily. Positions are mostly flat by EOD.
    # =========================================================================
    "aggressive_scalper": {
        "tech_weight": 0.50,
        "fund_weight": 0.05,
        "news_weight": 0.10,
        "quant_weight": 0.35,

        "buy_threshold": 63,
        "sell_threshold": 35,
        "tp_mode": "normal",
        "tp_mult": 2.5,          # 2.5x ATR ~ 5-7.5%. Quick profit targets.
        "sl_mult": 1.5,          # 1.5x ATR ~ 3-4.5%. Very tight.
        "trail_mult": 2.0,       # 2x ATR trail
        "tp_min": 2.0,
        "tp_max": 8.0,
        "sl_min": 1.0,
        "sl_max": 4.0,

        "max_position_pct": 30,   # concentrated but short-duration
        "max_positions": 5,
        "rebalance_days": 1,
        "position_kelly_frac": 0.60,  # more aggressive Kelly for high-frequency

        "use_tsmom": False,       # irrelevant for intraday
        "use_vr_filter": False,
        "use_52wk_high": False,
        "use_stat_arb": False,
        "use_mean_reversion": True,   # scalpers play micro mean reversion
        "use_regime_switch": True,    # avoid scalping in crisis regimes
        "use_ml_signal": True,        # ML is useful for short-term prediction
        "use_cross_asset": False,
        "use_vix_strategy": True,     # high VIX = wider intraday ranges = better for scalpers
        "use_disposition": False,     # behavioral bias irrelevant for scalping timeframe
        "use_ofi": True,              # OFI is critical -- volume pressure drives short-term moves
        "use_anchoring": False,       # 52wk high irrelevant for intraday
        "use_sentiment_div": False,   # sentiment divergence too slow for scalping

        "max_drawdown_halt_pct": 20,
        "daily_loss_halt_pct": 3,     # tight daily halt: -3% and stop for the day
        "max_daily_trades": 20,
        "leverage_allowed": True,
        "max_leverage": 2.0,

        "adaptive_aggression": 0.7,   # much tighter than default
        "regime_sensitivity": 0.6,    # moderate (scalpers can work in most regimes)
        "ml_trust": 0.8,             # lean heavily on ML for short-term signals

        "ai_coaching_style": "aggressive",
        "alert_frequency": "realtime",
        "scan_interval_sec": 60,

        "description": "High-frequency short-term trades. Tight stops. Quick profits. Daily loss circuit breaker.",
        "description_kr": "고빈도 단기매매. 타이트한 손절. 빠른 수익 실현. 일일 손실 한도.",
    },

    # =========================================================================
    # 8. MACRO ROTATOR
    # =========================================================================
    # Goal: Sector and asset class rotation based on macro regime.
    # Philosophy: Think in terms of economic cycles, not individual stocks.
    # Benchmark: 12-20% annualized with lower correlation to any single sector.
    #
    # Weight rationale:
    #   quant_weight=0.40 -- quant models drive macro regime detection
    #   fund_weight=0.25 -- fundamental sector analysis (earnings cycles)
    #   tech_weight=0.20 -- technical for sector relative strength
    #   news_weight=0.15 -- macro news (Fed, rates, geopolitics) is critical
    #
    # buy_threshold=72: more selective. Macro rotators don't trade often;
    #   higher bar filters out weak rotation signals.
    # sell_threshold=25: moderate patience. Macro themes play out over months.
    # tp_mult=5.0: normal TP. Sector rotations have defined targets.
    # sl_mult=3.5: moderate-wide stop. Sector-level moves are noisy.
    # trail_mult=5.0: wider trail for riding sector trends without whipsaw.
    # max_positions=12: diversified across sectors and asset classes.
    # rebalance_days=14: bi-weekly aligns with macro data release cycles.
    # use_cross_asset=True: THE defining model for this profile.
    # =========================================================================
    "macro_rotator": {
        "tech_weight": 0.20,
        "fund_weight": 0.25,
        "news_weight": 0.15,
        "quant_weight": 0.40,

        "buy_threshold": 72,
        "sell_threshold": 25,
        "tp_mode": "normal",
        "tp_mult": 5.0,          # 5x ATR ~ 10-15% TP per rotation
        "sl_mult": 3.5,          # 3.5x ATR ~ 7-10.5%. Sector moves are volatile.
        "trail_mult": 5.0,       # 5x ATR trail. Wider for sector trend noise.
        "tp_min": 8.0,
        "tp_max": 25.0,
        "sl_min": 5.0,
        "sl_max": 12.0,

        "max_position_pct": 18,
        "max_positions": 12,
        "rebalance_days": 14,
        "position_kelly_frac": 0.40,

        "use_tsmom": True,        # sector momentum is the core signal
        "use_vr_filter": True,    # filter sectors in random walk
        "use_52wk_high": True,
        "use_stat_arb": True,     # pairs between sectors (e.g. XLE vs XLK)
        "use_mean_reversion": False,  # macro rotators follow trends, not reversals
        "use_regime_switch": True,    # PRIMARY: Markov regime switching
        "use_ml_signal": True,
        "use_cross_asset": True,      # THE defining model for macro rotation
        "use_vix_strategy": True,
        "use_disposition": False,     # individual behavioral bias irrelevant for macro
        "use_ofi": False,             # order flow less meaningful at sector/macro level
        "use_anchoring": True,        # sector 52wk high anchoring for rotation timing
        "use_sentiment_div": True,    # macro sentiment divergence signals regime shifts

        "max_drawdown_halt_pct": 22,
        "daily_loss_halt_pct": None,  # macro positions need days to develop
        "max_daily_trades": 5,
        "leverage_allowed": True,
        "max_leverage": 1.5,

        "adaptive_aggression": 1.05,
        "regime_sensitivity": 1.3,    # AMPLIFIED regime response -- rotate faster on regime shifts
        "ml_trust": 0.6,

        "ai_coaching_style": "analytical",
        "alert_frequency": "daily",
        "scan_interval_sec": 900,

        "description": "Sector and asset rotation based on macro regime. Cross-asset momentum. Bi-weekly rebalance.",
        "description_kr": "매크로 레짐 기반 섹터/자산 로테이션. 크로스 에셋 모멘텀. 격주 리밸런싱.",
    },
}


# =============================================================================
# QUESTIONNAIRE SCORING -> INVESTOR TYPE MAPPING
# =============================================================================
#
# The questionnaire produces 6 normalized dimensions (0-10 scale each):
#   1. risk_score        -- composite risk tolerance (40% from risk psychology questions)
#   2. activity_level    -- trading frequency + holding period + rebalance pref
#   3. return_ambition   -- expected returns + volatility tolerance
#   4. experience_level  -- years + asset types traded
#   5. knowledge_score   -- concept familiarity + self-rating
#   6. leverage_appetite -- willingness to use margin
#
# Each investor type has a "centroid" in this 6D space. Classification uses
# weighted Euclidean distance. The type with the smallest distance wins.
#
# Centroid derivation methodology:
#   - Passive Index Hugger: archetypal beginner. Low on everything.
#   - Steady Accumulator: slightly more engaged beginner/intermediate.
#   - Value Hunter: experienced, knowledgeable, but moderate activity.
#   - Risk-Managed Growth: balanced across all axes, moderate risk.
#   - Swing Trader: high activity, moderate-high risk, experienced.
#   - Momentum Rider: high risk + return ambition, moderate knowledge.
#   - Macro Rotator: the expert. High knowledge dominates.
#   - Aggressive Scalper: extreme activity + risk, high experience.

TYPE_CENTROIDS: dict[str, tuple[float, ...]] = {
    #                     risk  activity  return  experience  knowledge  leverage
    "passive_index_hugger": (2.0,   1.0,    2.0,     2.0,        2.0,       0.0),
    "steady_accumulator":   (3.5,   2.5,    4.0,     3.0,        3.5,       0.0),
    "value_hunter":         (4.5,   3.0,    5.5,     6.0,        6.0,       1.0),
    "risk_managed_growth":  (5.5,   5.0,    6.5,     5.0,        5.0,       2.0),
    "swing_trader":         (6.5,   7.0,    6.5,     6.0,        6.5,       3.0),
    "momentum_rider":       (7.5,   7.5,    8.0,     5.5,        5.0,       5.0),
    "macro_rotator":        (5.0,   5.0,    6.0,     7.5,        8.0,       3.0),
    "aggressive_scalper":   (9.0,   9.5,    9.0,     7.0,        7.0,       7.0),
}

# Dimension weights for classification distance calculation.
# Risk and activity matter most for distinguishing types.
DIMENSION_WEIGHTS: tuple[float, ...] = (2.5, 2.0, 1.5, 1.0, 1.0, 1.5)

# Hard override rules: certain answer patterns force a type regardless of distance.
# Format: list of (condition_fn, forced_type, reason)
# These prevent absurd classifications when the distance metric fails at boundaries.
OVERRIDE_RULES = [
    # Scalp + extreme activity -> force scalper
    lambda dims: dims["trading_style"] == "scalp" and dims["activity"] >= 8.5,
    "aggressive_scalper",
    "Scalp trading style with extreme activity overrides distance metric",

    # Very low risk + very low activity -> force passive
    lambda dims: dims["risk"] <= 2.0 and dims["activity"] <= 2.0,
    "passive_index_hugger",
    "Very low risk and activity forces passive classification",

    # Very high knowledge + high experience + moderate activity -> macro rotator
    lambda dims: dims["knowledge"] >= 8 and dims["experience"] >= 7 and 4 <= dims["activity"] <= 6,
    "macro_rotator",
    "Expert-level knowledge with moderate activity indicates macro rotator",
]


# =============================================================================
# TIE-BREAKING RULES
# =============================================================================
# When the top-2 type scores are within 10% of each other (distance ratio < 1.1),
# we apply tie-breaking heuristics based on secondary signals.
#
# Tie-breaking priority:
#   1. Holding period preference (strongest signal for style)
#   2. Income stability (biases toward conservative side)
#   3. Loss aversion score (high loss aversion -> more conservative type)
#   4. If still tied: pick the LESS aggressive type (conservative bias)
#
# Rationale: when the system is uncertain, erring on the conservative side
# protects the user. It is better to be slightly too conservative than to
# put a risk-averse user into an aggressive profile.

# Aggression ordering from most conservative (0) to most aggressive (7)
AGGRESSION_ORDER: dict[str, int] = {
    "passive_index_hugger": 0,
    "steady_accumulator": 1,
    "value_hunter": 2,
    "risk_managed_growth": 3,
    "macro_rotator": 4,
    "swing_trader": 5,
    "momentum_rider": 6,
    "aggressive_scalper": 7,
}

# Holding period -> type affinity (tie-breaker when distances are close)
HOLDING_PERIOD_AFFINITY: dict[str, list[str]] = {
    "intraday": ["aggressive_scalper", "swing_trader"],
    "days": ["swing_trader", "momentum_rider", "aggressive_scalper"],
    "weeks": ["swing_trader", "momentum_rider", "risk_managed_growth"],
    "months": ["value_hunter", "macro_rotator", "steady_accumulator", "momentum_rider"],
    "years": ["passive_index_hugger", "steady_accumulator", "value_hunter"],
}


def classify_investor_type(
    risk_score: float,
    activity_normalized: float,
    return_normalized: float,
    experience_normalized: float,
    knowledge_score: float,
    leverage_score: float,
    trading_style: str = "swing",
    income_stability: float = 5.0,
    loss_aversion: float = 5.0,
    holding_period: str = "weeks",
) -> dict:
    """
    Classify a user into one of 8 investor types using weighted Euclidean distance
    to type centroids, with override rules and tie-breaking.

    Args:
        risk_score: 0-100 composite risk score (will be normalized to 0-10)
        activity_normalized: 0-10 activity level
        return_normalized: 0-10 return ambition
        experience_normalized: 0-10 experience level
        knowledge_score: 0-10 market knowledge
        leverage_score: 0-10 leverage appetite
        trading_style: str from questionnaire (scalp/day/swing/position/buy_and_hold)
        income_stability: 0-10 income stability score
        loss_aversion: 0-10 loss aversion score
        holding_period: str from questionnaire

    Returns:
        dict with:
            investor_type: str (one of 8 types)
            confidence: float (0-100, how certain the classification is)
            runner_up: str (second closest type)
            distances: dict of type -> distance (for debugging)
            override_applied: bool
            tie_break_applied: bool
    """
    # Normalize risk_score from 0-100 to 0-10
    risk_norm = min(risk_score / 10.0, 10.0)

    user_vector = (
        risk_norm,
        activity_normalized,
        return_normalized,
        experience_normalized,
        knowledge_score,
        leverage_score,
    )

    # Calculate weighted Euclidean distance to each centroid
    distances = {}
    for type_name, centroid in TYPE_CENTROIDS.items():
        distance = sum(
            w * (u - c) ** 2
            for w, u, c in zip(DIMENSION_WEIGHTS, user_vector, centroid)
        )
        distances[type_name] = round(distance, 2)

    # Sort by distance (ascending = closest first)
    sorted_types = sorted(distances.items(), key=lambda x: x[1])
    best_type = sorted_types[0][0]
    best_distance = sorted_types[0][1]
    runner_up = sorted_types[1][0]
    runner_up_distance = sorted_types[1][1]

    override_applied = False
    tie_break_applied = False

    # -- Check override rules --
    dims = {
        "risk": risk_norm,
        "activity": activity_normalized,
        "return_ambition": return_normalized,
        "experience": experience_normalized,
        "knowledge": knowledge_score,
        "leverage": leverage_score,
        "trading_style": trading_style,
    }

    # Override 1: scalper
    if trading_style == "scalp" and activity_normalized >= 8.5:
        best_type = "aggressive_scalper"
        override_applied = True

    # Override 2: passive
    if risk_norm <= 2.0 and activity_normalized <= 2.0:
        best_type = "passive_index_hugger"
        override_applied = True

    # Override 3: macro rotator
    if knowledge_score >= 8 and experience_normalized >= 7 and 4 <= activity_normalized <= 6:
        best_type = "macro_rotator"
        override_applied = True

    # -- Tie-breaking --
    if not override_applied and best_distance > 0:
        distance_ratio = runner_up_distance / best_distance if best_distance > 0 else 999
        if distance_ratio < 1.1:
            # Scores are very close -- apply tie-breaking

            # Rule 1: Holding period affinity
            affinity_types = HOLDING_PERIOD_AFFINITY.get(holding_period, [])
            if best_type not in affinity_types and runner_up in affinity_types:
                best_type, runner_up = runner_up, best_type
                tie_break_applied = True

            # Rule 2: High loss aversion biases conservative
            elif loss_aversion >= 7:
                best_agg = AGGRESSION_ORDER.get(best_type, 4)
                runner_agg = AGGRESSION_ORDER.get(runner_up, 4)
                if runner_agg < best_agg:
                    best_type, runner_up = runner_up, best_type
                    tie_break_applied = True

            # Rule 3: Low income stability biases conservative
            elif income_stability <= 3:
                best_agg = AGGRESSION_ORDER.get(best_type, 4)
                runner_agg = AGGRESSION_ORDER.get(runner_up, 4)
                if runner_agg < best_agg:
                    best_type, runner_up = runner_up, best_type
                    tie_break_applied = True

            # Rule 4: Default tie-break = conservative bias
            else:
                best_agg = AGGRESSION_ORDER.get(best_type, 4)
                runner_agg = AGGRESSION_ORDER.get(runner_up, 4)
                if runner_agg < best_agg:
                    best_type, runner_up = runner_up, best_type
                    tie_break_applied = True

    # Calculate confidence (inverse of distance, normalized)
    max_possible_distance = sum(w * 100 for w in DIMENSION_WEIGHTS)
    confidence = max(0, min(100, round(100 * (1 - best_distance / max_possible_distance) * 100) / 100))

    return {
        "investor_type": best_type,
        "confidence": confidence,
        "runner_up": runner_up,
        "distances": distances,
        "override_applied": override_applied,
        "tie_break_applied": tie_break_applied,
    }


# =============================================================================
# PUBLIC API -- used by engine.py, backtester.py, autotrader.py
# =============================================================================

def get_profile_params(investor_type: str) -> dict:
    """
    Get the complete parameter set for an investor type.

    Args:
        investor_type: one of the 8 type keys

    Returns:
        dict with all quant parameters for the type.
        Falls back to steady_accumulator if type is unknown.
    """
    return INVESTOR_PROFILES.get(investor_type, INVESTOR_PROFILES["steady_accumulator"]).copy()


def get_engine_params(investor_type: str) -> dict:
    """
    Get a subset of parameters compatible with engine.py's profile_params interface.
    This is what gets passed to QuantEngine.analyze(profile_params=...).

    Returns dict with keys that engine.py expects:
        tech_weight, fund_weight, news_weight, buy_threshold, sell_threshold,
        tp_min, tp_max, sl_min, sl_max
    """
    p = get_profile_params(investor_type)
    return {
        "tech_weight": p["tech_weight"],
        "fund_weight": p["fund_weight"],
        "news_weight": p["news_weight"],
        "buy_threshold": p["buy_threshold"],
        "sell_threshold": p["sell_threshold"],
        "tp_min": p["tp_min"],
        "tp_max": p["tp_max"],
        "sl_min": p["sl_min"],
        "sl_max": p["sl_max"],
        "use_disposition": p["use_disposition"],
        "use_ofi": p["use_ofi"],
        "use_anchoring": p["use_anchoring"],
        "use_sentiment_div": p["use_sentiment_div"],
    }


def get_backtester_params(investor_type: str) -> dict:
    """
    Get parameters specific to the backtester.

    Returns dict with:
        buy_threshold, sell_threshold, max_position_pct, max_positions,
        and model activation flags
    """
    p = get_profile_params(investor_type)
    return {
        "buy_threshold": p["buy_threshold"],
        "sell_threshold": p["sell_threshold"],
        "max_position_pct": p["max_position_pct"],
        "max_positions": p["max_positions"],
        "tp_mode": p["tp_mode"],
        "tp_mult": p["tp_mult"],
        "sl_mult": p["sl_mult"],
        "trail_mult": p["trail_mult"],
        "adaptive_aggression": p["adaptive_aggression"],
        "regime_sensitivity": p["regime_sensitivity"],
        "ml_trust": p["ml_trust"],
        "use_tsmom": p["use_tsmom"],
        "use_vr_filter": p["use_vr_filter"],
        "use_52wk_high": p["use_52wk_high"],
        "use_mean_reversion": p["use_mean_reversion"],
        "use_disposition": p["use_disposition"],
        "use_ofi": p["use_ofi"],
        "use_anchoring": p["use_anchoring"],
        "use_sentiment_div": p["use_sentiment_div"],
    }


def get_risk_params(investor_type: str) -> dict:
    """
    Get risk control parameters for the autotrader.

    Returns dict with:
        max_drawdown_halt_pct, daily_loss_halt_pct, max_daily_trades,
        leverage_allowed, max_leverage
    """
    p = get_profile_params(investor_type)
    return {
        "max_drawdown_halt_pct": p["max_drawdown_halt_pct"],
        "daily_loss_halt_pct": p["daily_loss_halt_pct"],
        "max_daily_trades": p["max_daily_trades"],
        "leverage_allowed": p["leverage_allowed"],
        "max_leverage": p["max_leverage"],
        "max_position_pct": p["max_position_pct"],
        "max_positions": p["max_positions"],
    }


def list_all_types() -> list[dict]:
    """
    Return summary info for all 8 types (for the frontend profile selection UI).
    """
    from questionnaire import INVESTOR_TYPES
    result = []
    for key, meta in INVESTOR_TYPES.items():
        params = INVESTOR_PROFILES.get(key, {})
        result.append({
            "type": key,
            "label": meta["label"],
            "label_kr": meta["label_kr"],
            "description": meta["description"],
            "description_kr": meta["description_kr"],
            "trading_style": meta["trading_style"],
            "typical_holding": meta["typical_holding"],
            "max_drawdown_halt_pct": params.get("max_drawdown_halt_pct"),
            "max_positions": params.get("max_positions"),
            "leverage_allowed": params.get("leverage_allowed"),
            "tp_mode": params.get("tp_mode"),
        })
    return result


# =============================================================================
# PROFILE COMPARISON TABLE (for debugging and display)
# =============================================================================

def compare_profiles() -> dict:
    """
    Generate a comparison table of all profiles.
    Useful for the frontend "compare strategies" feature and for debugging.
    """
    comparison = {}
    for type_name, params in INVESTOR_PROFILES.items():
        comparison[type_name] = {
            "weights": {
                "tech": params["tech_weight"],
                "fund": params["fund_weight"],
                "news": params["news_weight"],
                "quant": params["quant_weight"],
            },
            "entry_exit": {
                "buy_threshold": params["buy_threshold"],
                "sell_threshold": params["sell_threshold"],
                "tp_mode": params["tp_mode"],
                "sl_mult": params["sl_mult"],
                "trail_mult": params["trail_mult"],
            },
            "sizing": {
                "max_position_pct": params["max_position_pct"],
                "max_positions": params["max_positions"],
                "rebalance_days": params["rebalance_days"],
                "kelly_frac": params["position_kelly_frac"],
            },
            "risk": {
                "max_dd_halt": params["max_drawdown_halt_pct"],
                "daily_halt": params["daily_loss_halt_pct"],
                "leverage": params["leverage_allowed"],
            },
            "models_active": sum(1 for k, v in params.items()
                                 if k.startswith("use_") and v is True),
        }
    return comparison


# =============================================================================
# VALIDATION
# =============================================================================

def _validate_profiles():
    """
    Sanity-check all profiles on import.
    Raises ValueError if any profile has invalid parameters.
    """
    for type_name, params in INVESTOR_PROFILES.items():
        # Weights must sum to 1.0 (within floating point tolerance)
        weight_sum = (params["tech_weight"] + params["fund_weight"]
                      + params["news_weight"] + params["quant_weight"])
        if abs(weight_sum - 1.0) > 0.01:
            raise ValueError(
                f"Profile '{type_name}' weights sum to {weight_sum:.3f}, not 1.0"
            )

        # Thresholds must be in valid range
        if not (40 <= params["buy_threshold"] <= 95):
            raise ValueError(
                f"Profile '{type_name}' buy_threshold={params['buy_threshold']} "
                f"outside valid range [40, 95]"
            )
        if not (10 <= params["sell_threshold"] <= 50):
            raise ValueError(
                f"Profile '{type_name}' sell_threshold={params['sell_threshold']} "
                f"outside valid range [10, 50]"
            )

        # SL must be tighter than trail for trail-only profiles
        if params["tp_mode"] == "trail_only":
            if params["sl_mult"] > params["trail_mult"]:
                raise ValueError(
                    f"Profile '{type_name}' has sl_mult > trail_mult "
                    f"in trail_only mode (SL would never trigger before trail)"
                )

        # Max position + max positions must be physically possible
        min_portfolio = params["max_positions"] * params["max_position_pct"]
        # It is fine if min_portfolio > 100 (means not all slots will be full-size)

        # Drawdown halt must be positive
        if params["max_drawdown_halt_pct"] <= 0:
            raise ValueError(
                f"Profile '{type_name}' has non-positive max_drawdown_halt_pct"
            )


# Run validation on import
_validate_profiles()
