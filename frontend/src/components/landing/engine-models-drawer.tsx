"use client";

/**
 * EngineModelsDrawer — interactive 40-model inventory with methodology drawer.
 * ---------------------------------------------------------------------------
 *  Ported from the legacy landing-page.tsx (lines 547-1033, 4167-4235).
 *  Rewired against the real model inventory documented in
 *  reports/audit/MODEL_INVENTORY_2026-04-23.md (40 classes across 6 files).
 *
 *  • 6-category grid (Quant · Risk · Portfolio · Behavioral · AI · Screeners)
 *  • Click any model → right-side drawer (desktop) / bottom sheet (mobile)
 *  • ESC + backdrop close, focus-visible rings, aria-modal
 *  • Bronze #B8956A tokens (--pq-bronze)
 *  • No new pages. No new npm deps. motion/react + lucide-react already used.
 *  • Legal: measurement-only language. No BUY/SELL/HOLD/recommend/advice.
 */

import { useEffect, useState, useSyncExternalStore } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import { X } from "lucide-react";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { PQ_EASE, fadeUp, stagger } from "@/lib/motion";

/* ── md (≥768px) viewport store — useSyncExternalStore source ─── */
function subscribeMdViewport(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const mql = window.matchMedia("(min-width: 768px)");
  mql.addEventListener("change", listener);
  return () => mql.removeEventListener("change", listener);
}
function getMdViewportSnapshot(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(min-width: 768px)").matches;
}

type Category =
  | "QUANT"
  | "RISK"
  | "PORTFOLIO"
  | "BEHAVIORAL"
  | "AI"
  | "SCREENERS";

type ModelDef = {
  id: string;
  name: string;
  category: Category;
  subcategory: string;
  source: string;
  measures: string;
  feeds: string;
  reference?: string;
};

/* ════════════════════════════════════════════════════════════════════
   MODEL INVENTORY — 40 classes (MODEL_INVENTORY_2026-04-23.md)
   ──────────────────────────────────────────────────────────────────
   Quant (16) · Behavioral (5) · Risk (6) · Portfolio (5) · AI (3) · Screeners (5)
   Distributed across engine.py + quant_models.py + signal_models.py +
   risk_models.py + portfolio_models.py + ai_models.py + canslim.py +
   risk_defense.py + indicators.py.
   ════════════════════════════════════════════════════════════════════ */

const MODEL_DEFS: readonly ModelDef[] = [
  // ═══════════════════════ QUANT (16) ═══════════════════════
  {
    id: "statarb",
    name: "StatArb",
    category: "QUANT",
    subcategory: "Ornstein–Uhlenbeck mean-reversion",
    source: "quant_models.py:16",
    measures:
      "OU-process fit on paired holdings — estimates mean-reversion speed θ, long-run mean μ, and volatility σ. Flags a spread Z-score beyond 2 standard deviations.",
    feeds:
      "Exposed at /api/quant/stat-arb. Surfaces in Morning Brief Plus as a spread-anomaly observation on paired holdings.",
    reference: "Avellaneda & Lee (2010), “Statistical Arbitrage in the U.S. Equities Market.”",
  },
  {
    id: "meanrev",
    name: "MeanReversion",
    category: "QUANT",
    subcategory: "20-day Z-score",
    source: "quant_models.py:187",
    measures:
      "Z = (P − MA₂₀) / σ₂₀. Z < −2 marks a statistically stretched position to the downside; Z > 2 to the upside. Produces a 0–100 score with ±20 pt composite influence.",
    feeds:
      "Weekly Memo annotates which holdings sit stretched versus their rolling mean.",
    reference: "Ornstein–Uhlenbeck stochastic differential equation.",
  },
  {
    id: "momentum-breakout",
    name: "MomentumBreakout",
    category: "QUANT",
    subcategory: "ATR + Volume",
    source: "quant_models.py:250",
    measures:
      "Breakout when close > 20-day range high AND volume ratio > 1.5× average. ATR₂₀ sets the noise floor. ±20 pt composite influence.",
    feeds: "Morning Brief Plus breakout ledger.",
  },
  {
    id: "volatility-regime",
    name: "VolatilityRegime",
    category: "QUANT",
    subcategory: "Annualized σ quantiles",
    source: "quant_models.py:326",
    measures:
      "Classifies current σ (annualized) against historical P25 / P75 into LOW / NORMAL / HIGH / CRISIS. Scales position multiplier 0.2×–1.3×.",
    feeds: "Risk Board Deck header badge and Weekly Memo volatility line.",
  },
  {
    id: "regime-switching",
    name: "RegimeSwitching",
    category: "QUANT",
    subcategory: "Rolling Sharpe state",
    source: "quant_models.py:405",
    measures:
      "Sharpe₂₀ = annualized 20d return / 20d vol. Five states: BULL / MILD_BULL / TRANSITION / MILD_BEAR / BEAR. ±15 pt composite influence.",
    feeds: "Every dated artifact’s header: “Regime: Bull / Transition / Bear.”",
  },
  {
    id: "cross-asset-momentum",
    name: "CrossAssetMomentum",
    category: "QUANT",
    subcategory: "Macro ETF basket",
    source: "quant_models.py:498",
    measures:
      "1-month returns across SPY / TLT / GLD / USO / UUP. SPY > 3% & TLT < 0 → RISK_ON; SPY < −3% & TLT > 0 → RISK_OFF. ±3–8 pt composite influence.",
    feeds: "Macro Observation section of Weekly Memo.",
  },
  {
    id: "vix-strategy",
    name: "VIXStrategy",
    category: "QUANT",
    subcategory: "Fear index regime",
    source: "quant_models.py:596",
    measures:
      "VIX bands: <13 EXTREME_LOW, 13–18 LOW, 18–25 ELEVATED, 25–35 HIGH, >35 PANIC. Scales exposure 10%–100%. VIX > 30 raises entry threshold +5 and cuts composite −5.",
    feeds: "Risk Board Deck cover tile and the artifact header badge.",
  },
  {
    id: "ml-signal",
    name: "MLSignal",
    category: "QUANT",
    subcategory: "AdaBoost ensemble",
    source: "quant_models.py:674",
    measures:
      "15 decision stumps, α = 0.5·ln((1−err)/err). Features: RSI(7/14/21), MA ratios(10/20/50), vol_20, momentum(5/10/20). Outputs BULLISH / BEARISH / NEUTRAL plus prob_up. ±12 pt confidence-weighted influence.",
    feeds:
      "Weekly Memo “model view” line and the Capital Allocation reference path.",
    reference: "Freund & Schapire (1997), AdaBoost.",
  },
  {
    id: "adaptive-params",
    name: "AdaptiveParams",
    category: "QUANT",
    subcategory: "3-Layer TP / SL engine",
    source: "quant_models.py:1100",
    measures:
      "Layer 1: ATR bands. Layer 2: Regime matrix. Layer 3: ML confidence. Switches between five profiles — trend_rider / momentum / scalper / defensive / survival.",
    feeds: "Applied to every engine.analyze() call. Drives the TP/SL column in the ledger.",
  },
  {
    id: "variance-ratio",
    name: "VarianceRatioFilter",
    category: "QUANT",
    subcategory: "Random-walk test",
    source: "quant_models.py:1442",
    measures:
      "Lo & MacKinlay (1988). VR = Var(20d returns) / (20 × Var(1d returns)). VR > 1.2 marks a trending regime; near 1.0 marks random-walk; < 0.8 marks mean-reverting.",
    feeds: "Weekly Memo regime tile. +10 pt composite on confirmed trending.",
    reference: "Lo & MacKinlay (1988).",
  },
  {
    id: "tsmom",
    name: "TSMOM",
    category: "QUANT",
    subcategory: "12-month time-series momentum",
    source: "quant_models.py:1476",
    measures:
      "Ret₁₂m = P_now / P₋₂₅₂ − 1. Strength = |Ret₁₂m| / σ₆₃. ±12 pt composite influence.",
    feeds: "Quarterly Self-Report backdrop factor.",
    reference: "Moskowitz, Ooi & Pedersen (2012), “Time Series Momentum.”",
  },
  {
    id: "fiftytwo-week",
    name: "FiftyTwoWeekHigh",
    category: "QUANT",
    subcategory: "Anchor-proximity",
    source: "quant_models.py:1507",
    measures:
      "ratio = P_now / max(P₋₂₅₂). Above 0.95 is classified POSITIVE with a composite multiplier of 1.3×; 0.7×–1.3× range applied.",
    feeds: "Weekly Memo “proximity to 52-week high” line.",
    reference: "George & Hwang (2004).",
  },
  {
    id: "donchian-breakout",
    name: "DonchianBreakout",
    category: "QUANT",
    subcategory: "Turtle 55/20",
    source: "quant_models.py:1552",
    measures:
      "Entry high = max(High₋₅₅). Exit low = min(Low₋₂₀). ±10 pt composite influence.",
    feeds: "Morning Brief Plus breakout ledger.",
    reference: "Richard Dennis, Turtle Traders (1983).",
  },
  {
    id: "dual-momentum",
    name: "DualMomentum",
    category: "QUANT",
    subcategory: "Absolute + relative",
    source: "quant_models.py:1604",
    measures:
      "Absolute momentum: Ret₁₂m > 0. Relative momentum: Ret₁₂m > SPY₁₂m. POSITIVE only when both conditions hold. ±10 pt composite influence.",
    feeds: "Portfolio Segment report relative-strength column.",
    reference: "Antonacci (2014), “Dual Momentum Investing.”",
  },
  {
    id: "correlation-regime",
    name: "CorrelationRegime",
    category: "QUANT",
    subcategory: "Average pairwise corr",
    source: "quant_models.py:1661",
    measures:
      "60-day pairwise Pearson correlation across an SPY / QQQ / IWM / DIA / XLK basket. Average > 0.7 flags HIGH_CORRELATION — a diversification-collapse regime.",
    feeds: "Risk Board Deck heatmap. Informational (no direct composite impact today).",
  },
  {
    id: "interest-rate-regime",
    name: "InterestRateRegime",
    category: "QUANT",
    subcategory: "Fed-rate cycle classifier",
    source: "quant_models.py:1722",
    measures:
      "Compares fed_rate_current vs six months prior. Five regimes: rising_fast / rising / flat / falling / falling_fast.",
    feeds:
      "Exposed at /api/quant/interest-rate-regime. Macro Observation tile in Weekly Memo.",
  },

  // ═══════════════════════ BEHAVIORAL (5) ═══════════════════════
  {
    id: "disposition",
    name: "DispositionEffect",
    category: "BEHAVIORAL",
    subcategory: "Capital-gains overhang",
    source: "signal_models.py:26",
    measures:
      "Frazzini (2006) CGO. Reference price = Σ(P_t · V_t) / Σ(V_t) (1-year VWAP). CGO = (P_now − ref) / ref. CGO > 0.15 adds +8 contrarian-accumulation points; CGO < −0.15 subtracts 5.",
    feeds: "Self-Audit behavioral summary, expressed as a neutral observation.",
    reference: "Frazzini (2006); Shefrin & Statman (1985).",
  },
  {
    id: "herding",
    name: "HerdingIntensity",
    category: "BEHAVIORAL",
    subcategory: "Cross-sectional dispersion",
    source: "signal_models.py:106",
    measures:
      "CSAD = mean(|R_i − R_m|). Low dispersion under extreme market moves indicates cross-sectional herding.",
    feeds: "Market Observation section of Weekly Memo.",
    reference: "Christie & Huang (1995).",
  },
  {
    id: "sentiment-divergence",
    name: "SentimentPriceDivergence",
    category: "BEHAVIORAL",
    subcategory: "Price vs news drift",
    source: "signal_models.py:210",
    measures:
      "Rate-of-change comparison between price and the rule-based news score. divergence_score = −sign_agree · magnitude.",
    feeds: "Returned inside /api/quant/analyze as spd_result. Feeds the Observations band in Weekly Memo.",
  },
  {
    id: "ofi",
    name: "OrderFlowImbalance",
    category: "BEHAVIORAL",
    subcategory: "Signed-volume proxy",
    source: "signal_models.py:304",
    measures:
      "Cont et al. (2014). OFI_daily = sign(close − open) · volume. OFI_norm = Σ(OFI) / Σ(volume) over 20 days. high_positive: +6; high_negative: −6.",
    feeds: "Morning Brief Plus liquidity context.",
    reference: "Cont, Kukanov & Stoikov (2014).",
  },
  {
    id: "anchoring",
    name: "AnchoringBias",
    category: "BEHAVIORAL",
    subcategory: "52-week nearness × CGO",
    source: "signal_models.py:409",
    measures:
      "nearness = P_now / max(P₋₂₅₂). Interaction score = nearness · |CGO|. Applies a 0.97×–1.03× multiplier on composite.",
    feeds: "Self-Audit decision-review commentary.",
    reference: "George & Hwang (2004), extended with Frazzini CGO.",
  },

  // ═══════════════════════ RISK (6) ═══════════════════════
  {
    id: "gkyz",
    name: "GKYZVolatility",
    category: "RISK",
    subcategory: "Range-based OHLC estimator",
    source: "risk_models.py:14",
    measures:
      "Yang & Zhang (2000). var_YZ = var_overnight + k·var_close + (1−k)·var_RS. Annualized σ_YZ · √252 · 100. ~7–8× more efficient than close-to-close at equal sample size.",
    feeds: "Volatility column in Risk Board and Weekly Memo. Exposed at /api/quant/gkyz-vol.",
    reference: "Yang & Zhang (2000).",
  },
  {
    id: "ledoit",
    name: "LedoitWolfShrinkage",
    category: "RISK",
    subcategory: "Covariance shrinkage",
    source: "risk_models.py:93",
    measures:
      "Ledoit & Wolf (2004). α = b̄² / d̄² (Frobenius-loss minimizer). Σ_shrunk = (1−α)·S + α·F (F = scaled identity).",
    feeds:
      "Covariance input for every portfolio optimizer (HRP, MinVar, MaxDiv, ERC).",
    reference: "Ledoit & Wolf (2004).",
  },
  {
    id: "component-es",
    name: "ComponentES",
    category: "RISK",
    subcategory: "Tail-loss attribution",
    source: "risk_models.py:169",
    measures:
      "Tasche (2002) Euler decomposition. ES_i = w_i · E[r_i | r_port ≤ VaR_α]. Σ ES_i = portfolio ES.",
    feeds: "Risk Board Deck “who is costing you in the left tail” table. Exposed at /api/quant/component-es.",
    reference: "Tasche (2002).",
  },
  {
    id: "cdd",
    name: "ConditionalDrawdown",
    category: "RISK",
    subcategory: "Tail-side MDD",
    source: "risk_models.py:250",
    measures:
      "CDDaR = mean(DD over worst α%). DD_t = (PV_t − peak_t) / peak_t. A tail version of maximum drawdown.",
    feeds: "Annual Year-End Letter drawdown profile.",
  },
  {
    id: "tail-ratio",
    name: "TailRatio",
    category: "RISK",
    subcategory: "Return asymmetry",
    source: "risk_models.py:293",
    measures:
      "ratio = |P95(returns)| / |P5(returns)|. Values > 1 indicate a thicker right tail (upside > downside in the extremes).",
    feeds: "Quarterly Self-Report asymmetry tile.",
  },
  {
    id: "sortino",
    name: "SortinoByPosition",
    category: "RISK",
    subcategory: "Downside-only risk",
    source: "risk_models.py:334",
    measures:
      "Sortino = (E[r] − r_f) / downside_dev. downside_dev = std(r[r < r_f]) · √252. Unlike Sharpe, only downside volatility is penalized.",
    feeds: "Weekly Memo per-position risk ledger.",
    reference: "Sortino et al. (1991).",
  },

  // ═══════════════════════ PORTFOLIO (5) ═══════════════════════
  {
    id: "hrp",
    name: "HRP",
    category: "PORTFOLIO",
    subcategory: "Hierarchical Risk Parity",
    source: "portfolio_models.py:127",
    measures:
      "Three stages: (1) distance = √(½(1 − corr)); (2) single-linkage clustering; (3) recursive bisection with inverse-variance weights. No covariance inversion required.",
    feeds: "Capital Allocation report — your weights shown next to an HRP-reference weight.",
    reference: "López de Prado (2016).",
  },
  {
    id: "tailrisk-parity",
    name: "TailRiskParity",
    category: "PORTFOLIO",
    subcategory: "CVaR parity",
    source: "portfolio_models.py:359",
    measures:
      "Equalizes each asset’s CVaR contribution. Component CVaR_i = w_i · E[r_i | r_port ≤ VaR_α]. Iterative weight adjustment (max 50 iters).",
    feeds: "Capital Allocation “what-if” scenario.",
  },
  {
    id: "maxdiv",
    name: "MaxDiversification",
    category: "PORTFOLIO",
    subcategory: "Diversification ratio",
    source: "portfolio_models.py:505",
    measures:
      "DR = (w′σ) / √(w′Σw). w* = Σ⁻¹σ / (1′Σ⁻¹σ). Uses Ledoit-Wolf Σ.",
    feeds: "Risk Board Deck diversification tile.",
    reference: "Choueifaty & Coignard (2008).",
  },
  {
    id: "erc",
    name: "EqualRiskContribution",
    category: "PORTFOLIO",
    subcategory: "Risk parity",
    source: "portfolio_models.py:653",
    measures:
      "Each asset contributes equally to portfolio variance. w_i · (Σw)_i = target_risk / N. 30-iteration adjustment.",
    feeds: "Capital Allocation reference path.",
  },
  {
    id: "minvar",
    name: "MinVariance",
    category: "PORTFOLIO",
    subcategory: "Markowitz long-only",
    source: "portfolio_models.py:720",
    measures:
      "w* = Σ⁻¹·1 / (1′Σ⁻¹·1). Singular-matrix guard ε = 1e-8. Long-only projection.",
    feeds: "Defensive reference weight in Capital Allocation.",
    reference: "Markowitz (1952).",
  },

  // ═══════════════════════ AI (3) ═══════════════════════
  {
    id: "earnings-tone",
    name: "EarningsCallToneAnalyzer",
    category: "AI",
    subcategory: "Claude · NLP",
    source: "ai_models.py:122",
    measures:
      "claude-haiku-4-5 over earnings transcripts. Loughran-McDonald-style prompt. JSON fields: confidence, guidance_specificity, hedging_frequency, tone_shift, conviction_score. 24-hour cache.",
    feeds: "Earnings Pre-Brief “Tone vs consensus” line.",
    reference: "Loughran & McDonald (2011).",
  },
  {
    id: "sector-rotation",
    name: "AISectorRotation",
    category: "AI",
    subcategory: "Claude · Macro",
    source: "ai_models.py:358",
    measures:
      "claude-haiku-4-5 over VIX, SP500, rates, and USD/KRW. Six cycle stages: Early Recovery / Mid Expansion / Late Expansion / Slowdown / Contraction / Crisis. 6-hour cache.",
    feeds: "Portfolio Segment rotation note.",
  },
  {
    id: "risk-summary",
    name: "AIRiskSummary",
    category: "AI",
    subcategory: "Claude · Synthesis",
    source: "ai_models.py:482",
    measures:
      "claude-haiku-4-5 summary of vol, VaR, MDD, Sharpe, and concentration. JSON fields: summary_en, summary_kr, risk_level, top_risk_factor. 6-hour cache.",
    feeds: "Opening paragraph of Risk Board Deck.",
  },

  // ═══════════════════════ SCREENERS (5) ═══════════════════════
  {
    id: "canslim",
    name: "CANSLIMScreener",
    category: "SCREENERS",
    subcategory: "William O’Neil 7-factor",
    source: "canslim.py:185",
    measures:
      "C (EPS ≥ 25% YoY), A (annual EPS ≥ 25% × 3y), N (within 5% of 52-week high), S (volume > 1.5×), L (1-month return > 0), I (institutional ownership), M (market direction via RegimeSwitching).",
    feeds: "Screener tab in the Research Desk. Exposed at /api/quant/canslim.",
    reference: "William O’Neil, CAN SLIM.",
  },
  {
    id: "risk-defense",
    name: "RiskDefenseSystem",
    category: "SCREENERS",
    subcategory: "7-Layer circuit breakers",
    source: "risk_defense.py",
    measures:
      "Seven checks: L1 VaR ceiling · L2 correlation spike · L3 VIX threshold · L4 tail-attribution skew · L5 daily-loss circuit · L6 sector concentration · L7 regime-driven cash buffer. Eight profile presets.",
    feeds: "Every dated artifact’s circuit-breaker badge and the Risk Board cover tile.",
  },
  {
    id: "quant-engine",
    name: "QuantEngine",
    category: "SCREENERS",
    subcategory: "4-pillar composite",
    source: "engine.py",
    measures:
      "Assembles the composite 0–100 score from Technical (22%), Fundamental (25%), News (3%), and Quant (50%) pillars. Weights adapt by asset type (ETF / large cap / small cap / Korean listing).",
    feeds: "Every artifact in the stack. This is the orchestrator.",
  },
  {
    id: "additional-indicators",
    name: "AdditionalIndicators",
    category: "SCREENERS",
    subcategory: "10 technical overlays",
    source: "indicators.py:15",
    measures:
      "Donchian Channel, Supertrend, Parabolic SAR, Chaikin Money Flow, Accumulation/Distribution Line, Pivot Points, ATR Bands, VWAP, Heikin-Ashi, Keltner Width.",
    feeds: "Optional overlays on the Terminal chart and the Technical pillar.",
  },
  {
    id: "additional-fundamentals",
    name: "AdditionalFundamentals",
    category: "SCREENERS",
    subcategory: "8 fundamental ratios",
    source: "indicators.py:329",
    measures:
      "PEG, Price/Sales, Price/Book, FCF Yield, ROE, ROA, Current Ratio, Interest Coverage.",
    feeds: "Fundamental pillar inputs and DD Checklist body.",
  },
];

const CATEGORIES: readonly {
  key: Category;
  label: string;
  count: number;
  caption: string;
  footnote: string;
}[] = [
  {
    key: "QUANT",
    label: "Quant",
    count: 16,
    caption: "statistical models",
    footnote:
      "Technical 22% · Fundamental 25% · News 3% · Quant 50% (large-cap baseline). Weights adapt by asset type.",
  },
  {
    key: "BEHAVIORAL",
    label: "Behavioral",
    count: 5,
    caption: "bias & crowd signals",
    footnote:
      "Observations only. Behavioral signals are measurement instruments — they describe market structure, not directives.",
  },
  {
    key: "RISK",
    label: "Risk",
    count: 6,
    caption: "risk estimators",
    footnote:
      "Range-based vol, shrinkage covariance, tail attribution. Feeds both the composite score and the Risk Board Deck.",
  },
  {
    key: "PORTFOLIO",
    label: "Portfolio",
    count: 5,
    caption: "weight optimizers",
    footnote:
      "Five reference allocations. Shown in Capital Allocation alongside your actual weights — informational, not prescriptive.",
  },
  {
    key: "AI",
    label: "AI",
    count: 3,
    caption: "Claude-augmented synthesis",
    footnote:
      "Claude Haiku 4.5 summarizes quant and risk outputs in plain English. It never originates a directive.",
  },
  {
    key: "SCREENERS",
    label: "Screeners & Orchestrator",
    count: 5,
    caption: "composite + guardrails",
    footnote:
      "QuantEngine orchestrates the four pillars. RiskDefenseSystem enforces the seven circuit breakers on every dated artifact.",
  },
];

/* ══════════════════════════════════════════════════════════════════════
   DRAWER CONTENT
   ══════════════════════════════════════════════════════════════════════ */

function DrawerContent({
  model,
  onClose,
  titleId,
}: {
  model: ModelDef;
  onClose: () => void;
  titleId: string;
}) {
  return (
    <div className="relative flex flex-col p-7 md:p-10">
      <button
        type="button"
        onClick={onClose}
        aria-label="Close methodology"
        className="absolute top-4 right-4 p-2 transition-opacity hover:opacity-70 focus-visible:opacity-100"
        style={{ color: "var(--pq-ivory)" }}
      >
        <X className="h-4 w-4" aria-hidden />
      </button>

      <header className="mb-7 pr-8">
        <div className="mb-3 inline-flex items-center gap-2.5">
          <span
            aria-hidden
            className="h-px w-5"
            style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
          />
          <span
            className="font-serif uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
            }}
          >
            {CATEGORIES.find((c) => c.key === model.category)?.label} ·{" "}
            {model.subcategory}
          </span>
        </div>
        <h3
          id={titleId}
          className="font-serif"
          style={{
            fontSize: "clamp(1.55rem, 3.2vw, 2.05rem)",
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            fontWeight: 500,
            color: "var(--pq-ivory)",
          }}
        >
          {model.name}
        </h3>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span
            className="inline-flex items-center gap-2 font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              padding: "4px 10px",
              borderRadius: "999px",
              border: "1px solid rgba(184,149,106,0.5)",
              color: "var(--pq-bronze)",
              letterSpacing: "0.18em",
            }}
          >
            <span
              aria-hidden
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: "var(--pq-bronze)" }}
            />
            Live
          </span>
          <span
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              color: "rgba(245,240,232,0.45)",
              letterSpacing: "0.04em",
            }}
          >
            {model.source}
          </span>
        </div>
      </header>

      <section className="mb-6">
        <h4
          className="font-serif uppercase mb-2.5"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          What it measures
        </h4>
        <p
          className="font-serif"
          style={{
            fontSize: "15px",
            lineHeight: 1.65,
            color: "rgba(245,240,232,0.82)",
          }}
        >
          {model.measures}
        </p>
      </section>

      <section className="mb-6">
        <h4
          className="font-serif uppercase mb-2.5"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          How it enters a report
        </h4>
        <p
          className="font-serif"
          style={{
            fontSize: "15px",
            lineHeight: 1.65,
            color: "rgba(245,240,232,0.82)",
          }}
        >
          {model.feeds}
        </p>
      </section>

      {model.reference && (
        <section className="mb-6">
          <h4
            className="font-serif uppercase mb-2.5"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
            }}
          >
            Reference
          </h4>
          <p
            className="font-serif italic"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.58)",
            }}
          >
            {model.reference}
          </p>
        </section>
      )}

      <footer
        className="mt-4 pt-5"
        style={{ borderTop: "1px solid var(--pq-ivory-line)" }}
      >
        <p
          className="font-serif italic"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "rgba(245,240,232,0.58)",
            letterSpacing: "0.02em",
          }}
        >
          Measurement only — not a directive. Research and education use only.
        </p>
      </footer>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   MAIN EXPORT
   ══════════════════════════════════════════════════════════════════════ */

export default function EngineModelsDrawer() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const reduce = useReducedMotion();
  const selected = selectedId
    ? MODEL_DEFS.find((m) => m.id === selectedId) ?? null
    : null;

  // Viewport gate — desktop drawer and mobile bottom sheet are both rendered
  // (Tailwind `hidden md:flex` / `md:hidden`) but only one is visible. We
  // activate the focus trap matching the current viewport so the hidden
  // drawer doesn't compete for Tab handling.
  const isDesktop = useSyncExternalStore(
    subscribeMdViewport,
    getMdViewportSnapshot,
    () => false,
  );

  const desktopTrapRef = useFocusTrap<HTMLElement>(
    Boolean(selected) && isDesktop,
  );
  const mobileTrapRef = useFocusTrap<HTMLElement>(
    Boolean(selected) && !isDesktop,
  );

  // ESC closes drawer
  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  // Lock body scroll while drawer open (reset on close or unmount)
  useEffect(() => {
    if (!selected) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [selected]);

  const motionProps = (v: Variants) =>
    reduce
      ? {}
      : {
          initial: "hidden" as const,
          whileInView: "visible" as const,
          viewport: { once: true, margin: "-60px" },
          variants: v,
        };

  return (
    <section
      className="relative py-24 md:py-32"
      style={{
        backgroundColor: "#050505",
        borderTop: "0.5pt solid rgba(184,149,106,0.14)",
      }}
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="mb-14 md:mb-20 max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2.5">
            <span
              aria-hidden
              className="h-px w-7"
              style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
            />
            <span
              className="font-serif uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              The inventory · 40 models
            </span>
          </div>
          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(1.75rem, 3.8vw, 2.75rem)",
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
              fontWeight: 500,
              color: "var(--pq-ivory)",
              marginBottom: 18,
              maxWidth: "22ch",
            }}
          >
            Every model, cited by name.
          </h2>
          <p
            className="font-serif"
            style={{
              fontSize: "15px",
              lineHeight: 1.65,
              color: "rgba(245,240,232,0.68)",
              maxWidth: "58ch",
            }}
          >
            Click any name below to open its methodology card — the paper, the
            formula, and the place it surfaces in your reports. Every artifact in
            the stack traces back to one of these forty instruments.
          </p>
        </div>

        {/* Category grid */}
        <motion.div
          {...motionProps(stagger)}
          className="grid grid-cols-1 gap-10 md:grid-cols-2 md:gap-12 lg:grid-cols-3"
        >
          {CATEGORIES.map((col) => {
            const models = MODEL_DEFS.filter((m) => m.category === col.key);
            return (
              <motion.div
                key={col.key}
                variants={reduce ? undefined : fadeUp}
                className="flex flex-col"
              >
                <div className="mb-5 flex items-baseline justify-between gap-4">
                  <p
                    className="font-serif uppercase flex items-center gap-3"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.22em",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    <span aria-hidden style={{ opacity: 0.6, letterSpacing: "0.25em" }}>
                      •—•
                    </span>
                    {col.label}
                  </p>
                  <span
                    className="font-mono tabular-nums"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      color: "rgba(245,240,232,0.45)",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {String(col.count).padStart(2, "0")}
                  </span>
                </div>

                <p
                  className="font-serif mb-6"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    color: "rgba(245,240,232,0.55)",
                    letterSpacing: "0.01em",
                  }}
                >
                  {col.caption}
                </p>

                <ul
                  className="font-mono space-y-1.5"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    lineHeight: 1.75,
                    fontVariantNumeric: "tabular-nums",
                    color: "var(--pq-ivory)",
                  }}
                >
                  {models.map((m) => (
                    <li key={m.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(m.id)}
                        aria-haspopup="dialog"
                        aria-expanded={selectedId === m.id}
                        className="pq-model-item text-left"
                      >
                        {m.name}
                      </button>
                    </li>
                  ))}
                </ul>

                <p
                  className="mt-auto pt-8 font-serif italic"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    lineHeight: 1.6,
                    color: "rgba(245,240,232,0.48)",
                  }}
                >
                  {col.footnote}
                </p>
              </motion.div>
            );
          })}
        </motion.div>

        {/* Figure caption */}
        <p
          className="mt-16 md:mt-24 max-w-3xl font-serif italic"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            lineHeight: 1.7,
            color: "rgba(245,240,232,0.48)",
          }}
        >
          All models are measurement instruments. They quantify, detect, and
          describe — they do not generate buy / sell / hold instructions. Every
          output feeds the artifact stack as an observation, never as a
          directive. Research and education use only.
        </p>
      </div>

      {/* ─── Drawer (rendered at section root; position:fixed floats above) ─── */}
      <AnimatePresence>
        {selected && (
          <>
            <motion.button
              key="engine-backdrop"
              type="button"
              aria-label="Close methodology"
              onClick={() => setSelectedId(null)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2, ease: PQ_EASE }}
              className="fixed inset-0 z-40 cursor-default"
              style={{ backgroundColor: "rgba(10,10,10,0.6)" }}
            />

            {/* Desktop: right-side drawer */}
            <motion.aside
              key="engine-drawer-desktop"
              ref={desktopTrapRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby="engine-model-title-desktop"
              tabIndex={-1}
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ duration: 0.3, ease: PQ_EASE }}
              className="hidden md:flex fixed top-0 right-0 bottom-0 z-50 w-[30rem] flex-col overflow-y-auto"
              style={{
                backgroundColor: "#111111",
                borderLeft: "1px solid rgba(184,149,106,0.4)",
                color: "var(--pq-ivory)",
              }}
            >
              <DrawerContent
                model={selected}
                onClose={() => setSelectedId(null)}
                titleId="engine-model-title-desktop"
              />
            </motion.aside>

            {/* Mobile: bottom sheet */}
            <motion.aside
              key="engine-drawer-mobile"
              ref={mobileTrapRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby="engine-model-title-mobile"
              tabIndex={-1}
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ duration: 0.3, ease: PQ_EASE }}
              className="md:hidden fixed left-0 right-0 bottom-0 z-50 flex flex-col overflow-y-auto rounded-t-2xl"
              style={{
                maxHeight: "82vh",
                backgroundColor: "#111111",
                borderTop: "1px solid rgba(184,149,106,0.4)",
                color: "var(--pq-ivory)",
              }}
            >
              {/* Grab handle */}
              <div
                aria-hidden
                className="sticky top-0 flex justify-center py-3"
                style={{ backgroundColor: "#111111" }}
              >
                <span
                  className="block h-1 w-10 rounded-full"
                  style={{ backgroundColor: "rgba(184,149,106,0.5)" }}
                />
              </div>
              <DrawerContent
                model={selected}
                onClose={() => setSelectedId(null)}
                titleId="engine-model-title-mobile"
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </section>
  );
}
