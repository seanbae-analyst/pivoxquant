"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { motion, useReducedMotion, AnimatePresence } from "motion/react";
import type { Variants } from "motion/react";
import {
  TrendingUp,
  Shield,
  Brain,
  Menu,
  X,
  ArrowRight,
  Check,
  Star,
  Activity,
  Home,
  Target,
  Bell,
  Settings,
  Clock,
  Eye,
  FileText,
  Globe2,
  Briefcase,
  Scale,
  Archive,
  Lock,
} from "lucide-react";
import { Hero } from "./hero";

/* ──────────────────────────────────────────────
   Animation variants
   ────────────────────────────────────────────── */

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

const staggerContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};

/* ──────────────────────────────────────────────
   Feature data
   ────────────────────────────────────────────── */

const features = [
  {
    id: "01",
    icon: Eye,
    title: "Observation-only",
    description:
      "We never tell you to buy or sell. We show what the data is doing.",
    span: "md:col-span-2",
  },
  {
    id: "02",
    icon: FileText,
    title: "Goldman-grade artifacts",
    description:
      "17 weekly, monthly, and quarterly PDFs — indistinguishable from institutional research.",
    span: "md:col-span-1",
  },
  {
    id: "03",
    icon: Globe2,
    title: "Dual-market coverage",
    description: "US and KR equities in one pane, via KIS, Alpaca, and FMP.",
    span: "md:col-span-1",
  },
  {
    id: "04",
    icon: Briefcase,
    title: "Your own portfolio",
    description:
      "Reports are drawn from holdings you already have. No watchlists to curate.",
    span: "md:col-span-2",
  },
  {
    id: "05",
    icon: Scale,
    title: "Legal-safe by design",
    description:
      "Engineered to the Korean Capital Markets Act \u00a76 non-advisory boundary.",
    span: "md:col-span-1",
  },
  {
    id: "06",
    icon: Archive,
    title: "Compounding memory",
    description:
      "Every decision logged. Quarterly self-audit, year-end letter to yourself.",
    span: "md:col-span-2",
  },
];

/* ──────────────────────────────────────────────
   Feature Explorer — 17 artifacts
   ────────────────────────────────────────────── */

type Artifact = {
  name: string;
  tier: "PRO" | "PREMIUM";
  tagline: string;
  body: string;
  bullets: string[];
  format: string;
  sampleUrl: string | null;
};

const artifacts: Artifact[] = [
  {
    name: "Morning Brief Plus",
    tier: "PRO",
    tagline: "Pre-market orientation",
    body: "Read as: the pre-open note your desk slides under the door at 6:55 AM.",
    bullets: [
      "Overnight tape on your names",
      "Futures and dollar index snapshot",
      "Earnings day-plan for today's prints",
      "Macro cues drawn from the calendar",
      "Observation summary, not a call",
    ],
    format: "2-page PDF, ~300KB, generated each trading day 06:30 KST.",
    sampleUrl: "/samples/morning_brief_plus.pdf",
  },
  {
    name: "Weekly Memo",
    tier: "PRO",
    tagline: "Monday morning briefing",
    body: "Read as: the Monday morning briefing your research desk leaves on your chair.",
    bullets: [
      "Realized P&L from the last seven days",
      "Position drift and concentration snapshot",
      "Upcoming earnings events on your names",
      "Dividend calendar for the week",
      "Observation summary, not a recommendation",
    ],
    format: "5-page PDF, ~700KB, generated each Sunday 23:00 KST.",
    sampleUrl: "/samples/weekly_memo.pdf",
  },
  {
    name: "Earnings Pre-Brief",
    tier: "PRO",
    tagline: "Day-before earnings setup",
    body: "Read as: the working paper an analyst prepares the night before a print.",
    bullets: [
      "Consensus revenue and EPS range",
      "Year-over-year comparison points",
      "Guidance from the last four quarters",
      "Key metrics specific to the business",
      "Reaction pattern from prior earnings",
    ],
    format: "6-page PDF, ~850KB, generated day before each earnings print.",
    sampleUrl: "/samples/earnings_prebrief.pdf",
  },
  {
    name: "AI Suite",
    tier: "PRO",
    tagline: "Eight-model pattern board",
    body: "Read as: a dashboard of eight independent observational models running in parallel.",
    bullets: [
      "Disposition effect pattern",
      "Herding and crowd-flow pattern",
      "Sentiment-divergence check",
      "Order-flow imbalance reading",
      "Anchoring, tone, rotation, summary",
    ],
    format: "In-app dashboard, refreshed nightly.",
    sampleUrl: null,
  },
  {
    name: "DD Checklist",
    tier: "PRO",
    tagline: "10-K / 10-Q reading aid",
    body: "Read as: the checklist a junior analyst uses to break down a filing line-by-line.",
    bullets: [
      "Revenue composition and segments",
      "Risk-factor delta versus last filing",
      "Cash flow quality indicators",
      "Related-party and off-balance items",
      "Management discussion observations",
    ],
    format: "Interactive checklist, exportable to PDF.",
    sampleUrl: null,
  },
  {
    name: "Burn Rate",
    tier: "PRO",
    tagline: "Cash runway breakdown",
    body: "Read as: the cash-runway worksheet a CFO builds before a board meeting.",
    bullets: [
      "Monthly operating burn trend",
      "Runway in months at current pace",
      "Gross versus net burn split",
      "Working-capital adjustment view",
      "Scenarios drawn from reported data",
    ],
    format: "In-app worksheet, PDF export on demand.",
    sampleUrl: null,
  },
  {
    name: "Credit Rating",
    tier: "PRO",
    tagline: "Altman Z + coverage view",
    body: "Read as: the credit committee's one-pager on balance-sheet health.",
    bullets: [
      "Altman Z-Score composite",
      "Interest-coverage ratio trend",
      "Debt-to-equity progression",
      "Current and quick ratios",
      "Observation note, not a rating action",
    ],
    format: "1-page PDF, generated on refresh.",
    sampleUrl: null,
  },
  {
    name: "Monthly Finance",
    tier: "PREMIUM",
    tagline: "Month-in-review ledger",
    body: "Read as: the month-end close package a controller would hand to the CFO.",
    bullets: [
      "Realized P&L for the calendar month",
      "Dividend and interest income ledger",
      "Fees, spreads, and cost summary",
      "Month-over-month equity delta",
      "Observations on pace and drift",
    ],
    format: "8-page PDF, generated first business day of each month.",
    sampleUrl: null,
  },
  {
    name: "Risk Board Deck",
    tier: "PREMIUM",
    tagline: "Board-grade risk review",
    body: "Read as: the deck a CIO reads before a quarterly risk-committee meeting.",
    bullets: [
      "Concentration and single-name exposure",
      "Drawdown history and tail snapshot",
      "Factor tilts drawn from holdings",
      "Correlation map across positions",
      "Observation summary, no directive",
    ],
    format: "12-slide PDF deck, generated weekly.",
    sampleUrl: "/samples/risk_board.pdf",
  },
  {
    name: "Quarterly Self-Report",
    tier: "PREMIUM",
    tagline: "Own-decisions audit",
    body: "Read as: a private 10-Q written by your research desk about your own quarter.",
    bullets: [
      "Decisions logged during the quarter",
      "Position changes with rationale entered",
      "Realized outcomes against entry notes",
      "Pattern observations across trades",
      "Questions to carry into next quarter",
    ],
    format: "10-page PDF, generated quarterly.",
    sampleUrl: "/samples/quarterly_self_report.pdf",
  },
  {
    name: "Year-End Letter",
    tier: "PREMIUM",
    tagline: "A letter to next year's self",
    body: "Read as: a letter your research desk writes from you, to the version of you reading it next January.",
    bullets: [
      "Annual realized P&L recap",
      "Decisions that compounded, decisions that did not",
      "Patterns drawn from the decision log",
      "Observations on style drift",
      "Questions for the year ahead",
    ],
    format: "14-page PDF, generated end of December.",
    sampleUrl: "/samples/year_end_letter.pdf",
  },
  {
    name: "Capital Allocation",
    tier: "PREMIUM",
    tagline: "Allocation what-if scenarios",
    body: "Read as: the working paper behind a re-allocation proposal, stopping short of recommending one.",
    bullets: [
      "Current weights across positions",
      "Scenarios drawn from alternative mixes",
      "Historical correlation implications",
      "Drawdown footprint per scenario",
      "Observations, never a directive",
    ],
    format: "In-app scenario board, PDF export available.",
    sampleUrl: null,
  },
  {
    name: "Insider Mirror",
    tier: "PREMIUM",
    tagline: "Form 4 and DART event feed",
    body: "Read as: the event feed a filings-desk maintains on names you already hold.",
    bullets: [
      "Form 4 entries on US names",
      "DART major-shareholder disclosures for KR",
      "Transaction size and pattern notes",
      "Grouping by role and recurrence",
      "Event log, no interpretive call",
    ],
    format: "Rolling feed, weekly PDF digest.",
    sampleUrl: null,
  },
  {
    name: "Portfolio Segment",
    tier: "PREMIUM",
    tagline: "Sector and region breakdown",
    body: "Read as: the slide a PM uses to explain where the book actually lives.",
    bullets: [
      "Sector weights across holdings",
      "Region and currency exposure",
      "Market-cap band distribution",
      "Style tilts drawn from names",
      "Observations on drift over time",
    ],
    format: "4-page PDF, refreshed weekly.",
    sampleUrl: null,
  },
  {
    name: "Dividend Income",
    tier: "PREMIUM",
    tagline: "Twelve-month income ledger",
    body: "Read as: the trailing-twelve-month income ledger an accountant keeps for you.",
    bullets: [
      "Dividends received by position",
      "Ex-date and pay-date calendar",
      "Yield-on-cost per holding",
      "Currency split across payments",
      "Observations on income concentration",
    ],
    format: "6-page PDF, regenerated monthly.",
    sampleUrl: null,
  },
  {
    name: "Self Audit",
    tier: "PREMIUM",
    tagline: "Quarterly decision review",
    body: "Read as: the review a coach runs with you about your own quarter — drawn only from your decision log.",
    bullets: [
      "Decisions grouped by conviction note",
      "Entry-to-exit span patterns",
      "Rule adherence observations",
      "Style-drift flags, if any",
      "Questions surfaced by the log itself",
    ],
    format: "8-page PDF, quarterly cadence.",
    sampleUrl: null,
  },
  {
    name: "Brag Card",
    tier: "PREMIUM",
    tagline: "Monthly highlight digest",
    body: "Read as: the single-page highlight your desk hands you at month-end — realized wins, carried observations.",
    bullets: [
      "Top realized gainers of the month",
      "Dividend income received",
      "Longest holdings, still compounding",
      "Decisions that held up in hindsight",
      "A single observation line per item",
    ],
    format: "1-page PDF, monthly.",
    sampleUrl: null,
  },
];


/* ──────────────────────────────────────────────
   Equity curve SVG
   ────────────────────────────────────────────── */

function MiniEquityCurve() {
  return (
    <svg
      viewBox="0 0 200 80"
      className="w-full h-24"
      preserveAspectRatio="none"
      role="img"
      aria-label="10-year backtest equity curve, observational"
    >
      <defs>
        <linearGradient id="curveGradV2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8B6F47" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#8B6F47" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Grid dots 0.04 alpha */}
      {Array.from({ length: 10 }).map((_, col) =>
        Array.from({ length: 4 }).map((_, row) => (
          <circle
            key={`${col}-${row}`}
            cx={10 + col * 20}
            cy={15 + row * 18}
            r={0.6}
            fill="#F5F0E8"
            fillOpacity={0.04}
          />
        ))
      )}
      {/* Fill */}
      <path
        d="M0 60 C20 58, 30 52, 50 48 C70 44, 80 38, 100 40 C120 42, 130 26, 150 20 C170 14, 180 16, 200 10 L200 80 L0 80 Z"
        fill="url(#curveGradV2)"
      />
      {/* Bronze curve */}
      <path
        d="M0 60 C20 58, 30 52, 50 48 C70 44, 80 38, 100 40 C120 42, 130 26, 150 20 C170 14, 180 16, 200 10"
        fill="none"
        stroke="#8B6F47"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ──────────────────────────────────────────────
   Dashboard equity curve (full width section)
   ────────────────────────────────────────────── */

function DashboardEquityCurve() {
  return (
    <svg
      viewBox="0 0 500 120"
      className="w-full h-full"
      preserveAspectRatio="none"
      role="img"
      aria-label="Research terminal equity curve"
    >
      <defs>
        <linearGradient id="dashCurveV2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8B6F47" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#8B6F47" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Horizontal gridlines — ivory 0.06 */}
      {[30, 60, 90].map((y) => (
        <line
          key={y}
          x1={0}
          y1={y}
          x2={500}
          y2={y}
          stroke="#F5F0E8"
          strokeOpacity={0.06}
          strokeWidth={0.5}
        />
      ))}
      <path
        d="M0 90 C30 88, 50 80, 80 75 C110 70, 130 65, 160 58 C190 51, 210 55, 240 48 C270 41, 290 38, 320 32 C350 26, 370 30, 400 22 C430 14, 460 18, 500 10 L500 120 L0 120 Z"
        fill="url(#dashCurveV2)"
      />
      <path
        d="M0 90 C30 88, 50 80, 80 75 C110 70, 130 65, 160 58 C190 51, 210 55, 240 48 C270 41, 290 38, 320 32 C350 26, 370 30, 400 22 C430 14, 460 18, 500 10"
        fill="none"
        stroke="#8B6F47"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ──────────────────────────────────────────────
   CountUp — scroll-triggered number animation
   ────────────────────────────────────────────── */

function CountUp({
  to,
  duration = 1400,
  className,
  style,
  ariaLabel,
}: {
  to: number;
  duration?: number;
  className?: string;
  style?: React.CSSProperties;
  ariaLabel?: string;
}) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const startedRef = useRef(false);
  const prefersReduced = useReducedMotion();

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (prefersReduced) {
      setValue(to);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !startedRef.current) {
            startedRef.current = true;
            const start = performance.now();
            const step = (now: number) => {
              const elapsed = now - start;
              const t = Math.min(1, elapsed / duration);
              // easeOutCubic
              const eased = 1 - Math.pow(1 - t, 3);
              setValue(Math.round(eased * to));
              if (t < 1) requestAnimationFrame(step);
            };
            requestAnimationFrame(step);
          }
        });
      },
      { threshold: 0.3 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [to, duration, prefersReduced]);

  return (
    <span ref={ref} className={className} style={style} aria-label={ariaLabel}>
      {value}
    </span>
  );
}

/* ══════════════════════════════════════════════
   ENGINE MODEL DEFINITIONS
   ══════════════════════════════════════════════ */

type ModelDef = {
  id: string;
  name: string;
  category: "QUANT" | "RISK" | "AI";
  subcategory: string;
  measures: string;
  feeds: string;
  reference?: string;
};

const MODEL_DEFS: ModelDef[] = [
  // ═══ QUANT ═══
  {
    id: "statarb",
    name: "StatArb",
    category: "QUANT",
    subcategory: "Statistical Arbitrage",
    measures:
      "Deviation of a portfolio pair from its historical cointegration mean, expressed as a Z-score. Flags when the spread widens beyond two standard deviations.",
    feeds:
      "Surfaces in the Morning Brief Plus as a \u201Cspread anomaly\u201D observation on paired holdings.",
    reference:
      "Avellaneda & Lee (2010), \u201CStatistical Arbitrage in the U.S. Equities Market.\u201D",
  },
  {
    id: "meanrev",
    name: "MeanReversion",
    category: "QUANT",
    subcategory: "Ornstein\u2013Uhlenbeck",
    measures:
      "Speed and strength of mean-reverting behavior in individual price series, fit as an OU process with half-life and equilibrium parameters.",
    feeds:
      "Used in Weekly Memo to annotate which positions are currently stretched above or below their estimated long-run mean.",
    reference: "Ornstein\u2013Uhlenbeck stochastic differential equation.",
  },
  {
    id: "tsmom",
    name: "TSMOM (12\u20131)",
    category: "QUANT",
    subcategory: "Time-Series Momentum",
    measures:
      "Past-12-month return excluding the most recent month, per position. Classical Moskowitz-style time-series momentum signal.",
    feeds:
      "Appears in Quarterly Self-Report as a backdrop factor against which your entries are observed.",
    reference:
      "Moskowitz, Ooi & Pedersen (2012), \u201CTime Series Momentum.\u201D",
  },
  {
    id: "crosssectional",
    name: "CrossSectional Momentum",
    category: "QUANT",
    subcategory: "Cross-Sectional Ranking",
    measures:
      "Relative-return ranking across the held universe over a rolling window. Positions held are observed against peer-group percentile.",
    feeds:
      "Portfolio Segment report\u2019s \u201Crelative strength\u201D column.",
  },
  {
    id: "pairs",
    name: "Pairs Trading",
    category: "QUANT",
    subcategory: "Cointegration",
    measures:
      "Engle\u2013Granger two-step cointegration test on candidate pairs in your holdings. Reports p-value, hedge ratio, and residual stationarity.",
    feeds:
      "Sector-level \u201Crelative strength\u201D table in Portfolio Segment report.",
  },
  {
    id: "hrp",
    name: "HRP",
    category: "QUANT",
    subcategory: "Hierarchical Risk Parity",
    measures:
      "Portfolio weights derived from hierarchical clustering on the correlation distance matrix, allocating risk rather than capital.",
    feeds:
      "Capital Allocation report shows your actual weights alongside an HRP-reference weight for comparison.",
    reference:
      "L\u00F3pez de Prado (2016), \u201CBuilding Diversified Portfolios that Outperform Out-of-Sample.\u201D",
  },
  {
    id: "maxdiv",
    name: "Maximum Diversification",
    category: "QUANT",
    subcategory: "Diversification Ratio",
    measures:
      "Portfolio with the highest ratio of weighted-average volatility to overall volatility \u2014 a measure of effective diversification.",
    feeds: "Risk Board Deck diversification tile.",
    reference: "Choueifaty & Coignard (2008).",
  },
  {
    id: "erc",
    name: "Equal Risk Contribution",
    category: "QUANT",
    subcategory: "Risk Parity",
    measures:
      "Portfolio in which each asset contributes equally to total portfolio variance.",
    feeds: "Capital Allocation \u201Cwhat-if\u201D scenario set.",
  },
  {
    id: "minvar",
    name: "MinVariance",
    category: "QUANT",
    subcategory: "Mean-Variance",
    measures:
      "Markowitz minimum-variance portfolio given a user-configurable covariance estimator (sample / Ledoit\u2013Wolf).",
    feeds: "Reference weight in Capital Allocation.",
  },
  {
    id: "gkyz",
    name: "GKYZ Volatility",
    category: "QUANT",
    subcategory: "Range-Based Volatility",
    measures:
      "Garman\u2013Klass\u2013Yang\u2013Zhang volatility estimator using open / high / low / close \u2014 more efficient than close-to-close at equal sample size.",
    feeds: "Volatility column in Risk Board and Weekly Memo.",
    reference: "Yang & Zhang (2000).",
  },
  {
    id: "ledoit",
    name: "Ledoit\u2013Wolf",
    category: "QUANT",
    subcategory: "Covariance Shrinkage",
    measures:
      "Shrinkage estimator that pulls the sample covariance matrix toward a structured target, improving out-of-sample stability.",
    feeds:
      "All portfolio optimizers (HRP, MinVar, MaxDiv) use this as their covariance input.",
    reference: "Ledoit & Wolf (2004).",
  },
  {
    id: "component-es",
    name: "Component ES",
    category: "QUANT",
    subcategory: "Risk Attribution",
    measures:
      "Per-asset contribution to portfolio Expected Shortfall at a chosen confidence level (default 97.5%).",
    feeds:
      "Risk Board Deck \u201Cwho is costing you in the left tail\u201D table.",
  },
  {
    id: "cdd",
    name: "Conditional DD",
    category: "QUANT",
    subcategory: "Conditional Drawdown-at-Risk",
    measures:
      "Expected drawdown given the drawdown exceeds a threshold \u03B1 \u2014 a tail-oriented drawdown measure.",
    feeds: "Annual Year-End Letter drawdown profile.",
  },
  {
    id: "tailratio-sortino",
    name: "Tail Ratio \u00B7 Sortino",
    category: "QUANT",
    subcategory: "Asymmetry & Downside",
    measures:
      "Tail Ratio compares the 95th-percentile return against the absolute 5th-percentile return to capture return asymmetry. Sortino measures return over downside-only deviation (MAR=0 by default).",
    feeds:
      "Quarterly Self-Report asymmetry tile and the Weekly Memo performance ledger.",
  },
  {
    id: "disposition",
    name: "Disposition Effect",
    category: "QUANT",
    subcategory: "Behavioral Bias Detection",
    measures:
      "Ratio of realized gains to realized losses divided by the ratio of paper gains to paper losses. A value greater than 1 indicates a tendency to sell winners and hold losers.",
    feeds:
      "Self Audit behavioral summary, expressed as a neutral observation.",
    reference: "Shefrin & Statman (1985).",
  },
  {
    id: "herding",
    name: "Herding",
    category: "QUANT",
    subcategory: "Crowd-Following Pattern",
    measures:
      "Cross-sectional dispersion of returns against market-wide movement. Low dispersion under extreme market moves indicates herding behavior in the cross-section.",
    feeds: "Market Observation section of Weekly Memo.",
    reference: "Christie & Huang (1995).",
  },
  {
    id: "ofi",
    name: "Order-Flow Imbalance",
    category: "QUANT",
    subcategory: "Microstructure",
    measures:
      "Net signed volume from bid/ask order flow over a rolling window, normalized by total volume.",
    feeds: "Morning Brief Plus liquidity context.",
  },
  {
    id: "anchoring",
    name: "Anchoring",
    category: "QUANT",
    subcategory: "Behavioral Bias Detection",
    measures:
      "Distance of current decision price relative to the 52-week high and recent purchase prices. Quantifies reference-dependent behavior.",
    feeds: "Self Audit decision-review commentary.",
    reference: "Tversky & Kahneman (1974).",
  },

  // ═══ RISK \u2014 7-Layer ═══
  {
    id: "var",
    name: "VaR (historical + parametric)",
    category: "RISK",
    subcategory: "Value at Risk",
    measures:
      "Estimated maximum loss at a chosen confidence level and horizon. Both historical and parametric variants are computed.",
    feeds:
      "Risk Board Deck cover tile. Also enforced as a circuit-breaker: when VaR exceeds the configured ceiling, the artifact flags it at the top of the report.",
  },
  {
    id: "correlation",
    name: "Cross-asset correlation",
    category: "RISK",
    subcategory: "Matrix Monitor",
    measures:
      "Rolling correlation matrix across all held positions plus benchmark. Rising average off-diagonal correlation is flagged as regime compression.",
    feeds: "Risk Board Deck heatmap.",
  },
  {
    id: "vix-regime",
    name: "VIX regime",
    category: "RISK",
    subcategory: "Volatility State",
    measures:
      "Three-state hidden-Markov model over VIX term structure: calm / normal / stressed.",
    feeds:
      "Header badge on every dated artifact: \u201CRegime: Normal\u201D / \u201CRegime: Stressed.\u201D",
  },
  {
    id: "tail-escalation",
    name: "Tail escalation",
    category: "RISK",
    subcategory: "Left-Tail Monitor",
    measures:
      "Detects clustering of daily returns in the left-tail region (beyond 2\u03C3) within a rolling window.",
    feeds: "Risk Board Deck section \u201CLeft-tail clustering.\u201D",
  },
  {
    id: "daily-dd",
    name: "Daily drawdown",
    category: "RISK",
    subcategory: "Circuit Breaker",
    measures:
      "Current daily drawdown versus a configurable ceiling (default 3%). Triggers a circuit-breaker badge when breached.",
    feeds: "Morning Brief Plus top strip.",
  },
  {
    id: "sector-conc",
    name: "Sector concentration",
    category: "RISK",
    subcategory: "Herfindahl Index",
    measures:
      "Herfindahl\u2013Hirschman Index on sector weights. Above 0.25 is flagged as concentrated.",
    feeds: "Portfolio Segment concentration tile.",
  },
  {
    id: "cash-buffer",
    name: "Cash buffer",
    category: "RISK",
    subcategory: "Liquidity Floor",
    measures:
      "Percentage of portfolio in cash versus a user-configured minimum (default 5%).",
    feeds:
      "Weekly Memo \u201CLiquidity\u201D line; breach escalates to the top of the next report.",
  },

  // ═══ AI ═══
  {
    id: "earnings-tone",
    name: "Earnings call tone",
    category: "AI",
    subcategory: "Claude \u00B7 NLP",
    measures:
      "Tone classification (confident / hedging / defensive / cautious) of earnings call transcripts for the names you hold.",
    feeds: "Earnings Pre-Brief \u201CTone vs consensus\u201D line.",
  },
  {
    id: "sector-rotation",
    name: "Sector rotation patterns",
    category: "AI",
    subcategory: "Claude \u00B7 Pattern",
    measures:
      "LLM-aided identification of recent sector relative-strength rotation patterns, cross-checked against a factor-exposure model.",
    feeds: "Portfolio Segment \u201CRotation note.\u201D",
  },
  {
    id: "risk-summary",
    name: "Risk summary (NL)",
    category: "AI",
    subcategory: "Claude \u00B7 Synthesis",
    measures:
      "Natural-language summary of the quant and risk outputs above, written in the voice of a research desk memo.",
    feeds: "Opening paragraph of Risk Board Deck.",
  },
  {
    id: "swot",
    name: "SWOT synthesis",
    category: "AI",
    subcategory: "Claude \u00B7 Framework",
    measures:
      "Company-level strengths / weaknesses / opportunities / threats synthesis from 10-K / 10-Q filings and recent earnings material.",
    feeds: "DD Checklist report.",
  },
  {
    id: "ten-k",
    name: "10-K / 10-Q auto-read",
    category: "AI",
    subcategory: "Claude \u00B7 Document",
    measures:
      "Structured extraction of key sections (Risk Factors, MD&A, Liquidity) from 10-K and 10-Q filings with citations back to the source paragraph.",
    feeds: "DD Checklist body.",
  },
  {
    id: "chat",
    name: "Research chat assistant",
    category: "AI",
    subcategory: "Claude \u00B7 Interactive",
    measures:
      "Conversational interface to query your portfolio data and the artifacts above. Answers are constrained to observations in the source material.",
    feeds:
      "In-app Research Desk chat (outside the PDF artifact set).",
  },
];

/* ══════════════════════════════════════════════
   ENGINE DRAWER CONTENT
   ══════════════════════════════════════════════ */

function EngineDrawerContent({
  model,
  onClose,
  mobile,
}: {
  model: ModelDef;
  onClose: () => void;
  mobile?: boolean;
}) {
  const titleId = mobile ? "engine-model-title-mobile" : "engine-model-title";
  return (
    <div className="relative flex flex-col p-8 md:p-10">
      {/* Close button */}
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="absolute top-5 right-5 p-2 transition-opacity hover:opacity-70"
        style={{ color: "var(--pq-ivory)" }}
      >
        <X className="h-4 w-4" aria-hidden />
      </button>

      {/* Header */}
      <header className="mb-8 pr-8">
        <div className="mb-3 inline-flex items-center gap-2.5">
          <span
            aria-hidden
            className="h-px w-5"
            style={{ backgroundColor: "rgba(139,111,71,0.7)" }}
          />
          <span
            className="font-serif text-[10.5px] uppercase"
            style={{
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
            }}
          >
            {model.category} &middot; {model.subcategory}
          </span>
        </div>
        <h3
          id={titleId}
          className="font-serif"
          style={{
            fontSize: "clamp(1.6rem, 3.2vw, 2.1rem)",
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            fontWeight: 500,
            color: "var(--pq-ivory)",
          }}
        >
          {model.name}
        </h3>
        <span
          className="mt-4 inline-flex items-center gap-2 font-mono text-[10.5px] uppercase"
          style={{
            padding: "4px 10px",
            borderRadius: "999px",
            border: "1px solid rgba(139,111,71,0.5)",
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
      </header>

      {/* What it measures */}
      <section className="mb-7">
        <h4
          className="font-serif text-[10.5px] uppercase mb-3"
          style={{
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          What it measures
        </h4>
        <p
          className="font-serif"
          style={{
            fontSize: "14.5px",
            lineHeight: 1.65,
            color: "rgba(245,240,232,0.82)",
          }}
        >
          {model.measures}
        </p>
      </section>

      {/* How it enters a report */}
      <section className="mb-7">
        <h4
          className="font-serif text-[10.5px] uppercase mb-3"
          style={{
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          How it enters a report
        </h4>
        <p
          className="font-serif"
          style={{
            fontSize: "14.5px",
            lineHeight: 1.65,
            color: "rgba(245,240,232,0.82)",
          }}
        >
          {model.feeds}
        </p>
      </section>

      {/* Reference */}
      {model.reference && (
        <section className="mb-7">
          <h4
            className="font-serif text-[10.5px] uppercase mb-3"
            style={{
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
            }}
          >
            Reference
          </h4>
          <p
            className="font-serif italic"
            style={{
              fontSize: "13px",
              lineHeight: 1.6,
              color: "var(--pq-muted)",
            }}
          >
            {model.reference}
          </p>
        </section>
      )}

      {/* Footer disclaimer */}
      <footer
        className="mt-4 pt-5"
        style={{ borderTop: "1px solid rgba(245,240,232,0.08)" }}
      >
        <p
          className="font-serif text-[11px] italic"
          style={{ color: "var(--pq-muted)", letterSpacing: "0.02em" }}
        >
          Measurement only &mdash; not a directive.
        </p>
      </footer>
    </div>
  );
}

/* ══════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════ */

export default function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState<number>(0);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const prefersReduced = useReducedMotion();

  const selectedModel =
    selectedModelId !== null
      ? MODEL_DEFS.find((m) => m.id === selectedModelId) ?? null
      : null;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // ESC closes the Engine drawer
  useEffect(() => {
    if (selectedModelId === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedModelId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedModelId]);

  // If user prefers reduced motion, skip framer variants
  const motionProps = (v: Variants) =>
    prefersReduced
      ? {}
      : {
          initial: "hidden" as const,
          whileInView: "visible" as const,
          viewport: { once: true, margin: "-60px" },
          variants: v,
        };

  // Hero is in the initial viewport — use `animate` instead of `whileInView`
  // so IntersectionObserver timing issues (first paint, hydration after
  // beta-gate redirect) cannot leave elements stuck at opacity:0.
  const heroMotionProps = (v: Variants) =>
    prefersReduced
      ? {}
      : {
          initial: "hidden" as const,
          animate: "visible" as const,
          variants: v,
        };

  return (
    <div className="min-h-screen overflow-x-hidden" style={{ backgroundColor: "var(--pq-ink)", color: "var(--pq-ivory)" }}>
      {/* ─── 1. NAVIGATION — Vantablack sticky top bar ─── */}
      <nav
        className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
        style={{
          backgroundColor: scrolled ? "rgba(10,10,10,0.85)" : "rgba(10,10,10,0.55)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          borderBottom: "0.5pt solid rgba(245,240,232,0.08)",
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo — serif letterspaced */}
            <Link href="/" className="flex items-center">
              <span
                className="font-serif text-[13px] sm:text-sm"
                style={{
                  color: "var(--pq-ivory)",
                  letterSpacing: "0.22em",
                  textTransform: "uppercase",
                  fontWeight: 500,
                }}
              >
                PIVOXQUANT
              </span>
            </Link>

            {/* Desktop Nav */}
            <div className="hidden md:flex items-center gap-10">
              <a
                href="#features"
                className="text-[12.5px] transition-colors font-serif"
                style={{ color: "rgba(245,240,232,0.65)", letterSpacing: "0.02em" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--pq-ivory)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(245,240,232,0.65)")}
              >
                Product
              </a>
              <a
                href="#pricing"
                className="text-[12.5px] transition-colors font-serif"
                style={{ color: "rgba(245,240,232,0.65)", letterSpacing: "0.02em" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--pq-ivory)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(245,240,232,0.65)")}
              >
                Pricing
              </a>
              <a
                href="#sample-reports"
                className="text-[12.5px] transition-colors font-serif"
                style={{ color: "rgba(245,240,232,0.65)", letterSpacing: "0.02em" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--pq-ivory)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(245,240,232,0.65)")}
              >
                Research
              </a>
              <Link
                href="/login"
                className="text-[12.5px] transition-colors font-serif"
                style={{ color: "rgba(245,240,232,0.65)", letterSpacing: "0.02em" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--pq-ivory)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(245,240,232,0.65)")}
              >
                Log in
              </Link>
            </div>

            {/* Desktop CTA — Bronze pill */}
            <div className="hidden md:flex items-center">
              <Link
                href="/signup"
                className="inline-flex items-center px-5 h-9 rounded-full text-[12.5px] font-medium transition-all active:scale-[0.97]"
                style={{
                  backgroundColor: "var(--pq-bronze)",
                  color: "var(--pq-ink)",
                  letterSpacing: "0.02em",
                }}
              >
                Start trial
              </Link>
            </div>

            {/* Mobile hamburger */}
            <button
              className="md:hidden flex h-11 w-11 items-center justify-center rounded-sm transition-colors"
              style={{ color: "var(--pq-ivory)" }}
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="md:hidden"
            style={{
              backgroundColor: "rgba(10,10,10,0.95)",
              backdropFilter: "blur(16px)",
              borderBottom: "0.5pt solid rgba(245,240,232,0.08)",
            }}
          >
            <div className="px-4 py-4 space-y-1">
              {[
                { label: "Product", href: "#features" },
                { label: "Pricing", href: "#pricing" },
                { label: "Research", href: "#sample-reports" },
              ].map((l) => (
                <a
                  key={l.label}
                  href={l.href}
                  className="block text-sm py-3 font-serif"
                  style={{ color: "rgba(245,240,232,0.7)" }}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {l.label}
                </a>
              ))}
              <hr style={{ borderColor: "var(--pq-border)" }} />
              <Link href="/login" className="block text-sm py-3 font-serif" style={{ color: "rgba(245,240,232,0.7)" }}>
                Log in
              </Link>
              <Link
                href="/signup"
                className="block text-center px-5 py-2.5 rounded-full text-sm font-medium"
                style={{ backgroundColor: "var(--pq-bronze)", color: "var(--pq-ink)" }}
              >
                Start trial
              </Link>
            </div>
          </motion.div>
        )}
      </nav>

      {/* ─── 2. HERO SECTION — Hero v2 (Vantablack + Ivory + Bronze) ─── */}
      <Hero />

      {/* ─── 3. INTRO / PROOF OF DISCIPLINE — Ivory band ─── */}
      <section
        className="relative pt-32 pb-28 md:pt-48 md:pb-36 lg:pt-56 lg:pb-44"
        style={{ backgroundColor: "var(--pq-ivory)", color: "var(--pq-ink)" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            {...motionProps(staggerContainer)}
            className="grid md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-12 md:gap-20 items-center"
          >
            {/* Left: copy */}
            <motion.div variants={fadeUp} className="max-w-xl">
              <div className="mb-7 inline-flex items-center gap-2.5">
                <span
                  aria-hidden
                  className="h-px w-7"
                  style={{ backgroundColor: "rgba(139, 111, 71, 0.8)" }}
                />
                <span
                  className="font-serif text-[11px] uppercase"
                  style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
                >
                  Proof of Discipline
                </span>
              </div>
              <p className="pq-deck pq-deck--ink mb-4">
                Ten-year observation. One discipline.
              </p>
              <h2
                className="font-serif mb-6"
                style={{
                  fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                  lineHeight: 1.08,
                  letterSpacing: "-0.02em",
                  fontWeight: 500,
                  color: "var(--pq-ink)",
                }}
              >
                Ten years of a single rule,
                <br />
                backtested in the open.
              </h2>
              <p
                className="font-serif mb-8"
                style={{
                  fontSize: "clamp(15px, 1.3vw, 17px)",
                  lineHeight: 1.65,
                  color: "#3A3A3A",
                }}
              >
                Observation-only methodology. S&amp;P 500 universe, transaction costs included. 2014–2024 observed.
              </p>

              <div className="flex flex-wrap items-center gap-3">
                <a
                  href="/samples/sp500_backtest.pdf"
                  target="_blank"
                  rel="noopener"
                  className="group inline-flex h-11 items-center gap-2 rounded-sm px-5 text-[13px] font-medium transition-transform duration-200 hover:-translate-y-px active:translate-y-0"
                  style={{
                    backgroundColor: "var(--pq-ink)",
                    color: "var(--pq-ivory)",
                    letterSpacing: "0.02em",
                  }}
                >
                  View full backtest
                  <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                </a>
                <a
                  href="#features"
                  className="inline-flex h-11 items-center gap-2 rounded-sm border bg-transparent px-5 text-[13px] font-medium transition-colors duration-200"
                  style={{
                    borderColor: "rgba(10,10,10,0.25)",
                    color: "var(--pq-ink)",
                    letterSpacing: "0.02em",
                  }}
                >
                  Read methodology
                </a>
              </div>
            </motion.div>

            {/* Right: Vantablack equity-curve card */}
            <motion.div variants={fadeUp}>
              <div
                className="rounded-sm p-6 md:p-8"
                style={{
                  backgroundColor: "var(--pq-ink)",
                  border: "0.5pt solid rgba(245,240,232,0.12)",
                  boxShadow: "0 30px 60px -30px rgba(10,10,10,0.35)",
                }}
              >
                <div className="flex items-center justify-between mb-5">
                  <span
                    className="font-serif text-[10px] uppercase"
                    style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
                  >
                    Equity Curve · 2014 – 2024
                  </span>
                  <span
                    className="font-mono tabular-nums text-[11px]"
                    style={{ color: "rgba(245,240,232,0.6)" }}
                  >
                    SPX · Observation
                  </span>
                </div>
                <MiniEquityCurve />
                <div className="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
                  {[
                    { k: "CAGR", v: "21.19%", note: "observed, 2014–2024" },
                    { k: "Sharpe", v: "0.94", note: "risk-adjusted return" },
                    { k: "Alpha vs SPX", v: "+9.66%", note: "benchmark excess" },
                    { k: "2022 Bear", v: "+23.2pp", note: "outperformance" },
                  ].map((s) => (
                    <div key={s.k}>
                      <p
                        className="font-serif text-[9.5px] uppercase leading-none mb-2"
                        style={{ letterSpacing: "0.22em", color: "var(--pq-muted)" }}
                      >
                        {s.k}
                      </p>
                      <p
                        className="font-mono tabular-nums text-[17px] leading-none mb-1.5"
                        style={{
                          color: "var(--pq-ivory)",
                          letterSpacing: "-0.01em",
                          fontFeatureSettings: '"tnum", "lnum"',
                        }}
                      >
                        {s.v}
                      </p>
                      <p
                        className="font-serif italic leading-tight"
                        style={{
                          fontSize: "10.5px",
                          color: "rgba(245,240,232,0.5)",
                        }}
                      >
                        {s.note}
                      </p>
                    </div>
                  ))}
                </div>
                <p
                  className="mt-5 font-serif text-[10.5px] italic leading-relaxed"
                  style={{ color: "var(--pq-muted)" }}
                >
                  Backtest, hypothetical. Past performance does not guarantee future results.
                </p>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* ─── SAMPLE REPORTS — Vantablack, 3 open + S&P Proof + 3 locked previews ─── */}
      <section
        id="sample-reports"
        className="py-28 md:py-40 lg:py-48"
        style={{ backgroundColor: "#0A0A0A" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-20 md:mb-24">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span aria-hidden className="h-px w-7" style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }} />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                Sample Desk
              </span>
            </div>
            <p className="pq-deck mb-4">
              Four pages pulled from the drawer — the rest sit with members.
            </p>
            <h2
              className="font-serif mb-10 md:mb-14"
              style={{
                fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 500,
                color: "var(--pq-ivory)",
              }}
            >
              A glimpse of what
              <br />
              members receive.
            </h2>
            <p
              className="font-serif"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "rgba(245,240,232,0.65)",
              }}
            >
              Four open artifacts, rendered from realistic portfolio data. The remaining three sit behind the desk door — covers visible, content reserved for paid members.
            </p>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10 md:gap-14"
          >
            {([
              // ── Open teasers (3) — clickable PDFs
              {
                file: "weekly_memo",
                tier: "PRO",
                tierLabel: "Pro",
                title: "Weekly Memo",
                desc: "Monday 7:00 AM briefing — what moved your book, what to watch.",
                locked: false,
                badge: "OPEN SAMPLE",
              },
              {
                file: "sp500_backtest",
                tier: "PROOF",
                tierLabel: "Proof",
                title: "S&P 500 Backtest",
                desc: "Ten-year observation. One discipline.",
                locked: false,
                badge: "PROOF",
              },
              {
                file: "risk_board",
                tier: "PREMIUM",
                tierLabel: "Premium",
                title: "Risk Board Deck",
                desc: "Concentration, drawdown, factor tilts. The deck a CIO reads first.",
                locked: false,
                badge: "OPEN SAMPLE",
              },
              // ── Locked previews (3) — covers visible, content reserved
              {
                file: "year_end_letter",
                tier: "PREMIUM",
                tierLabel: "Premium",
                title: "Year-End Letter",
                desc: "Annual letter to yourself — realized P&L, decisions, lessons.",
                locked: true,
                badge: "MEMBERS ONLY",
              },
              {
                file: "quarterly_self_report",
                tier: "PREMIUM",
                tierLabel: "Premium",
                title: "Quarterly Self-Report",
                desc: "Your private 10-Q. The quarter, audited by your own desk.",
                locked: true,
                badge: "MEMBERS ONLY",
              },
              {
                file: "earnings_prebrief",
                tier: "PRO",
                tierLabel: "Pro",
                title: "Earnings Pre-Brief",
                desc: "The working paper before each of your names prints earnings.",
                locked: true,
                badge: "MEMBERS ONLY",
              },
            ] as const).map((r) => {
              const isProof = r.tier === "PROOF";
              const href = r.locked ? "/pricing" : `/samples/${r.file}.pdf`;
              const CardTag: "a" = "a";
              return (
                <motion.div
                  key={r.file}
                  variants={fadeUp}
                  className="relative"
                >
                  <CardTag
                    href={href}
                    {...(r.locked ? {} : { target: "_blank", rel: "noopener" })}
                    aria-label={
                      r.locked
                        ? `${r.title} — members only. View pricing to unlock.`
                        : `${r.title} — open sample PDF`
                    }
                    className={`group block rounded-sm p-5 md:p-6 transition-all duration-300 ${r.locked ? "pq-locked-card" : ""}`}
                    style={{
                      backgroundColor: "rgba(245,240,232,0.03)",
                      border: isProof
                        ? "0.5pt solid rgba(139,111,71,0.38)"
                        : "0.5pt solid rgba(245,240,232,0.10)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "rgba(139,111,71,0.55)";
                      e.currentTarget.style.transform = "translateY(-2px)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = isProof
                        ? "rgba(139,111,71,0.38)"
                        : "rgba(245,240,232,0.10)";
                      e.currentTarget.style.transform = "translateY(0)";
                    }}
                  >
                    {/* PDF thumbnail */}
                    <div
                      className="relative mb-5 rounded-sm overflow-hidden"
                      style={{
                        aspectRatio: "8.5 / 11",
                        backgroundColor: "#F5F0E8",
                        boxShadow:
                          "inset 0 0 0 0.5pt rgba(10,10,10,0.06), 0 24px 48px -24px rgba(0,0,0,0.55)",
                      }}
                    >
                      <div className="absolute inset-0 p-4 md:p-5 flex flex-col">
                        {/* Masthead */}
                        <div
                          className="pb-2"
                          style={{ borderBottom: "0.5pt solid rgba(10,10,10,0.25)" }}
                        >
                          <p
                            className="font-serif uppercase"
                            style={{
                              fontSize: "7.5px",
                              letterSpacing: "0.28em",
                              color: "var(--pq-bronze)",
                            }}
                          >
                            PivoxQuant · {r.tierLabel} Desk
                          </p>
                          <p
                            className="font-serif mt-1.5"
                            style={{
                              fontSize: "10px",
                              lineHeight: 1.2,
                              letterSpacing: "-0.01em",
                              color: "var(--pq-ink)",
                              fontWeight: 500,
                            }}
                          >
                            {r.title}
                          </p>
                        </div>
                        {/* Skeleton body */}
                        <div className="flex-1 mt-3 space-y-1.5">
                          {[100, 92, 96, 78, 88, 94, 70, 90, 82, 96, 74, 88].map(
                            (w, i) => (
                              <div
                                key={i}
                                className="h-[2px] rounded-full"
                                style={{
                                  width: `${w}%`,
                                  backgroundColor: "rgba(10,10,10,0.12)",
                                }}
                              />
                            )
                          )}
                          <div className="pt-2" />
                          <div
                            className="h-10 rounded-sm"
                            style={{ backgroundColor: "rgba(139,111,71,0.10)" }}
                          />
                          {[90, 84, 94, 76].map((w, i) => (
                            <div
                              key={`b-${i}`}
                              className="h-[2px] rounded-full"
                              style={{
                                width: `${w}%`,
                                backgroundColor: "rgba(10,10,10,0.12)",
                              }}
                            />
                          ))}
                        </div>
                        {/* Footer strip */}
                        <div
                          className="pt-2 flex items-center justify-between"
                          style={{ borderTop: "0.5pt solid rgba(10,10,10,0.12)" }}
                        >
                          <span
                            className="font-mono tabular-nums"
                            style={{
                              fontSize: "6.5px",
                              letterSpacing: "0.14em",
                              color: "rgba(10,10,10,0.45)",
                            }}
                          >
                            CONFIDENTIAL · NOT ADVICE
                          </span>
                          <span
                            className="font-mono tabular-nums"
                            style={{
                              fontSize: "6.5px",
                              color: "rgba(10,10,10,0.45)",
                            }}
                          >
                            01 / 08
                          </span>
                        </div>
                      </div>

                      {/* Locked veil + submark + shimmer */}
                      {r.locked && (
                        <>
                          <span aria-hidden className="pq-locked-veil" />
                          <span aria-hidden className="pq-locked-shimmer" />
                          <div
                            className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-4 text-center"
                            aria-hidden
                          >
                            {/* Bronze seal */}
                            <span
                              className="inline-flex h-9 w-9 items-center justify-center rounded-full"
                              style={{
                                border: "0.75pt solid rgba(245, 240, 232, 0.72)",
                                backgroundColor: "rgba(10,10,10,0.35)",
                                color: "var(--pq-ivory)",
                              }}
                            >
                              <Lock className="h-3.5 w-3.5" strokeWidth={1.5} />
                            </span>
                            <span
                              className="font-serif italic"
                              style={{
                                fontSize: "11.5px",
                                letterSpacing: "0.08em",
                                color: "rgba(245, 240, 232, 0.9)",
                              }}
                            >
                              Members only
                            </span>
                            <span
                              className="font-serif uppercase"
                              style={{
                                fontSize: "8.5px",
                                letterSpacing: "0.3em",
                                color: "var(--pq-bronze)",
                              }}
                            >
                              Cover preview only
                            </span>
                          </div>
                        </>
                      )}
                    </div>

                    {/* Badge row */}
                    <div className="mb-2 flex items-center justify-between">
                      <p
                        className="font-serif text-[10.5px] uppercase"
                        style={{
                          letterSpacing: "0.22em",
                          color: isProof
                            ? "var(--pq-bronze-light)"
                            : "var(--pq-bronze)",
                        }}
                      >
                        {r.badge}
                      </p>
                      <p
                        className="font-mono tabular-nums"
                        style={{
                          fontSize: "9.5px",
                          letterSpacing: "0.16em",
                          color: "var(--pq-muted)",
                          textTransform: "uppercase",
                        }}
                      >
                        {r.tier}
                      </p>
                    </div>

                    {/* Title */}
                    <h3
                      className="font-serif mb-2"
                      style={{
                        fontSize: "19px",
                        lineHeight: 1.2,
                        letterSpacing: "-0.01em",
                        color: "var(--pq-ivory)",
                        fontWeight: 500,
                      }}
                    >
                      {r.title}
                    </h3>
                    {/* Desc */}
                    <p
                      className="font-serif mb-4"
                      style={{
                        fontSize: "13.5px",
                        lineHeight: 1.55,
                        color: "rgba(245,240,232,0.6)",
                      }}
                    >
                      {r.desc}
                    </p>
                    <span
                      className="font-serif inline-flex items-center gap-1.5 text-[12.5px]"
                      style={{
                        color: "var(--pq-bronze)",
                        letterSpacing: "0.02em",
                      }}
                    >
                      {r.locked ? "Unlock with Pro · Premium" : "View PDF"}
                      <ArrowRight
                        className="w-3.5 h-3.5 transition-transform duration-300 group-hover:translate-x-0.5"
                        strokeWidth={1.5}
                      />
                    </span>
                  </CardTag>
                </motion.div>
              );
            })}
          </motion.div>

          <motion.p
            {...motionProps(fadeUp)}
            className="mt-12 font-serif text-[11px] italic leading-relaxed"
            style={{ color: "rgba(245,240,232,0.45)" }}
          >
            Generated from synthetic holdings. Real reports are drawn from your own positions only. Open samples and backtest cover only — member artifacts are never shared publicly.
          </motion.p>
        </div>
      </section>

      {/* ─── 5. FEATURES BENTO — Vantablack lift ─── */}
      <section
        id="features"
        className="py-20 md:py-28 lg:py-40"
        style={{ backgroundColor: "#111111" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-20 md:mb-24">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span aria-hidden className="h-px w-7" style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }} />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                The Research Desk
              </span>
            </div>
            <h2
              className="font-serif mb-10 md:mb-14"
              style={{
                fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 500,
                color: "var(--pq-ivory)",
              }}
            >
              Not a chatbot.
              <br />
              A research department that files.
            </h2>
            <p
              className="font-serif"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "rgba(245,240,232,0.65)",
              }}
            >
              Seventeen artifacts, drawn from your own holdings. Delivered as PDF, mirrored in the app.
            </p>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 md:grid-cols-3 gap-10 md:gap-14"
          >
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={feature.title}
                  variants={fadeUp}
                  className={`group relative p-7 md:p-8 rounded-sm transition-all duration-300 ${feature.span}`}
                  style={{
                    backgroundColor: "rgba(255,255,255,0.02)",
                    border: "0.5pt solid rgba(245,240,232,0.10)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "rgba(139,111,71,0.55)";
                    e.currentTarget.style.backgroundColor = "rgba(139,111,71,0.035)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "rgba(245,240,232,0.10)";
                    e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.02)";
                  }}
                >
                  <div className="flex items-start justify-between mb-8">
                    <Icon className="w-6 h-6" strokeWidth={1.25} style={{ color: "var(--pq-bronze)" }} />
                    <span
                      className="font-mono tabular-nums text-[10.5px]"
                      style={{ color: "var(--pq-muted)", letterSpacing: "0.14em" }}
                    >
                      {feature.id}
                    </span>
                  </div>
                  <h3
                    className="font-serif mb-3"
                    style={{
                      fontSize: "clamp(20px, 1.65vw, 24px)",
                      lineHeight: 1.2,
                      letterSpacing: "-0.01em",
                      color: "var(--pq-ivory)",
                      fontWeight: 500,
                    }}
                  >
                    {feature.title}
                  </h3>
                  <p
                    className="font-serif"
                    style={{
                      fontSize: "15px",
                      lineHeight: 1.6,
                      color: "rgba(245,240,232,0.65)",
                    }}
                  >
                    {feature.description}
                  </p>
                </motion.div>
              );
            })}
          </motion.div>

          <motion.p
            {...motionProps(fadeUp)}
            className="mt-12 font-serif text-[11px] italic leading-relaxed"
            style={{ color: "var(--pq-muted)" }}
          >
            Informational research only. Not investment advice.
          </motion.p>
        </div>
      </section>

      {/* ─── Section divider — Bronze 1px line ─── */}
      <div
        className="flex items-center justify-center"
        style={{ backgroundColor: "#111111", paddingTop: 0, paddingBottom: 0 }}
        aria-hidden
      >
        <span
          className="h-px"
          style={{ width: "6em", backgroundColor: "rgba(139,111,71,0.5)" }}
        />
      </div>

      {/* ─── 5b. FEATURE EXPLORER — Vantablack lift, click-to-reveal tabs ─── */}
      <section
        id="feature-explorer"
        className="py-20 md:py-28 lg:py-40"
        style={{ backgroundColor: "#111111" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-8 md:mb-12">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span aria-hidden className="h-px w-7" style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }} />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                Explore the Desk
              </span>
            </div>
            <p className="pq-deck mb-4">
              Seventeen artifacts. Six rendered today, eleven staged.
            </p>
            <h2
              className="font-serif mb-8 md:mb-12"
              style={{
                fontSize: "clamp(2rem, 4vw, 3rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 500,
                color: "var(--pq-ivory)",
              }}
            >
              What each artifact actually does.
            </h2>
            <p
              className="font-serif"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "rgba(245,240,232,0.65)",
              }}
            >
              Click any to read the methodology. Six are live; the remaining eleven are staged on the roadmap — methodology visible, samples reserved for members on release.
            </p>
          </motion.div>

          {/* Explorer container */}
          <motion.div
            {...motionProps(fadeUp)}
            className="rounded-sm overflow-hidden"
            style={{
              backgroundColor: "rgba(245,240,232,0.02)",
              border: "0.5pt solid rgba(245,240,232,0.10)",
            }}
          >
            {/* Mobile: horizontal scrolling chips */}
            <div
              className="md:hidden flex overflow-x-auto gap-2 p-4"
              style={{
                borderBottom: "0.5pt solid rgba(245,240,232,0.10)",
                scrollbarWidth: "thin",
              }}
            >
              {artifacts.map((a, i) => (
                <button
                  key={a.name}
                  onClick={() => setSelectedArtifact(i)}
                  className="shrink-0 font-serif px-3 py-2 rounded-sm transition-colors text-[12.5px]"
                  style={{
                    backgroundColor:
                      selectedArtifact === i
                        ? "rgba(139,111,71,0.12)"
                        : "transparent",
                    color:
                      selectedArtifact === i
                        ? "var(--pq-ivory)"
                        : "rgba(245,240,232,0.55)",
                    border:
                      selectedArtifact === i
                        ? "0.5pt solid rgba(139,111,71,0.55)"
                        : "0.5pt solid rgba(245,240,232,0.10)",
                    letterSpacing: "0.02em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {a.name}
                </button>
              ))}
            </div>

            <div className="flex flex-col md:flex-row">
              {/* Desktop: vertical tab list */}
              <div
                className="hidden md:block w-64 lg:w-80 shrink-0"
                style={{
                  borderRight: "0.5pt solid rgba(245,240,232,0.10)",
                  maxHeight: "640px",
                  overflowY: "auto",
                }}
                role="tablist"
                aria-orientation="vertical"
              >
                {artifacts.map((a, i) => {
                  const active = selectedArtifact === i;
                  return (
                    <button
                      key={a.name}
                      role="tab"
                      aria-selected={active}
                      onClick={() => setSelectedArtifact(i)}
                      className="w-full text-left px-6 py-4 transition-all duration-150"
                      style={{
                        backgroundColor: active
                          ? "rgba(139,111,71,0.08)"
                          : "transparent",
                        borderLeft: active
                          ? "2px solid var(--pq-bronze)"
                          : "2px solid transparent",
                        borderBottom: "0.5pt solid rgba(245,240,232,0.06)",
                      }}
                      onMouseEnter={(e) => {
                        if (!active) {
                          e.currentTarget.style.backgroundColor =
                            "rgba(245,240,232,0.04)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!active) {
                          e.currentTarget.style.backgroundColor = "transparent";
                        }
                      }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <span
                          className="font-serif block"
                          style={{
                            fontSize: "16px",
                            color: active
                              ? "var(--pq-ivory)"
                              : "rgba(245,240,232,0.70)",
                            fontWeight: 500,
                            letterSpacing: "-0.005em",
                          }}
                        >
                          {a.name}
                        </span>
                        <span
                          className="font-mono tabular-nums shrink-0 mt-1"
                          style={{
                            fontSize: "9px",
                            letterSpacing: "0.18em",
                            color: active
                              ? "var(--pq-bronze)"
                              : "var(--pq-muted)",
                          }}
                        >
                          {a.tier}
                        </span>
                      </div>
                      <span
                        className="font-serif italic block mt-1"
                        style={{
                          fontSize: "13px",
                          color: "var(--pq-muted)",
                          lineHeight: 1.4,
                        }}
                      >
                        {a.tagline}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Body panel */}
              <div
                className="flex-1 p-10 md:p-14"
                role="tabpanel"
                aria-live="polite"
              >
                <AnimatePresence mode="wait">
                  <motion.div
                    key={selectedArtifact}
                    initial={prefersReduced ? false : { opacity: 0, y: 8 }}
                    animate={prefersReduced ? undefined : { opacity: 1, y: 0 }}
                    exit={prefersReduced ? undefined : { opacity: 0, y: -8 }}
                    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <div className="mb-8 inline-flex items-center gap-2.5">
                      <span
                        aria-hidden
                        className="h-px w-5"
                        style={{ backgroundColor: "rgba(139,111,71,0.7)" }}
                      />
                      <span
                        className="font-mono tabular-nums text-[10px] uppercase"
                        style={{
                          letterSpacing: "0.22em",
                          color: "var(--pq-bronze)",
                        }}
                      >
                        {artifacts[selectedArtifact].tier} · Methodology
                      </span>
                    </div>

                    <h3
                      className="font-serif mb-6"
                      style={{
                        fontSize: "22px",
                        lineHeight: 1.2,
                        letterSpacing: "-0.01em",
                        color: "var(--pq-ivory)",
                        fontWeight: 500,
                      }}
                    >
                      {artifacts[selectedArtifact].name}
                    </h3>

                    <p
                      className="mb-8"
                      style={{
                        fontSize: "15px",
                        lineHeight: 1.6,
                        color: "rgba(245,240,232,0.78)",
                      }}
                    >
                      {artifacts[selectedArtifact].body}
                    </p>

                    <p
                      className="font-serif mb-4"
                      style={{
                        fontSize: "11px",
                        letterSpacing: "0.22em",
                        textTransform: "uppercase",
                        color: "var(--pq-bronze)",
                      }}
                    >
                      What&rsquo;s inside
                    </p>
                    <ul className="mb-10 space-y-2">
                      {artifacts[selectedArtifact].bullets.map((b) => (
                        <li
                          key={b}
                          className="flex items-start gap-3"
                          style={{
                            fontSize: "15px",
                            lineHeight: 1.6,
                            color: "rgba(245,240,232,0.78)",
                          }}
                        >
                          <span
                            aria-hidden
                            className="shrink-0"
                            style={{
                              color: "var(--pq-bronze)",
                              lineHeight: 1.6,
                            }}
                          >
                            •
                          </span>
                          <span>{b}</span>
                        </li>
                      ))}
                    </ul>

                    <p
                      className="font-serif italic mb-8"
                      style={{
                        fontSize: "13px",
                        lineHeight: 1.55,
                        color: "var(--pq-muted)",
                      }}
                    >
                      Format: {artifacts[selectedArtifact].format}
                    </p>

                    {artifacts[selectedArtifact].sampleUrl ? (
                      <a
                        href={artifacts[selectedArtifact].sampleUrl as string}
                        target="_blank"
                        rel="noopener"
                        className="group inline-flex items-center gap-2 font-serif transition-colors"
                        style={{
                          fontSize: "13.5px",
                          color: "var(--pq-bronze)",
                          letterSpacing: "0.02em",
                        }}
                      >
                        View sample PDF
                        <ArrowRight
                          className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5"
                          strokeWidth={1.5}
                        />
                      </a>
                    ) : (
                      <div
                        className="inline-flex items-center gap-3 rounded-sm px-4 py-2.5"
                        style={{
                          border: "0.5pt solid rgba(139,111,71,0.35)",
                          backgroundColor: "rgba(139,111,71,0.06)",
                        }}
                      >
                        <Lock
                          className="h-3 w-3"
                          strokeWidth={1.75}
                          style={{ color: "var(--pq-bronze)" }}
                        />
                        <span
                          className="font-serif uppercase"
                          style={{
                            fontSize: "10.5px",
                            letterSpacing: "0.22em",
                            color: "var(--pq-bronze)",
                          }}
                        >
                          Not yet public
                        </span>
                        <span
                          aria-hidden
                          className="h-3 w-px"
                          style={{ backgroundColor: "rgba(139,111,71,0.3)" }}
                        />
                        <span
                          className="font-serif italic"
                          style={{
                            fontSize: "12px",
                            color: "rgba(245,240,232,0.6)",
                          }}
                        >
                          Released to members on go-live
                        </span>
                      </div>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </motion.div>

          <motion.p
            {...motionProps(fadeUp)}
            className="mt-12 font-serif text-[11px] italic leading-relaxed"
            style={{ color: "var(--pq-muted)" }}
          >
            Informational only. Not investment advice.
          </motion.p>
        </div>
      </section>

      {/* ─── 6. HOW IT WORKS — Ivory, large watermark numerals ─── */}
      <section
        id="how-it-works"
        className="relative overflow-hidden py-20 md:py-28 lg:py-40"
        style={{ backgroundColor: "var(--pq-ivory)", color: "var(--pq-ink)" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-20 md:mb-24">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span aria-hidden className="h-px w-7" style={{ backgroundColor: "rgba(139, 111, 71, 0.8)" }} />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                How This Works
              </span>
            </div>
            <h2
              className="font-serif mb-10 md:mb-14"
              style={{
                fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 500,
                color: "var(--pq-ink)",
              }}
            >
              Three moves.
              <br />
              Then the desk runs on its own.
            </h2>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-16"
          >
            {[
              {
                n: "01",
                title: "Connect",
                body: "Link KIS (Korea) and Alpaca (US). Read-only, no orders, ever. Your keys never leave your session.",
              },
              {
                n: "02",
                title: "Observe",
                body: "We build a private research profile — holdings, cost basis, concentration, realized history.",
              },
              {
                n: "03",
                title: "Read",
                body: "Each Monday at 7:00 AM, a PDF lands in your inbox. You read. You decide. We do not.",
              },
            ].map((step) => (
              <motion.div
                key={step.n}
                variants={fadeUp}
                className="relative"
              >
                <span
                  aria-hidden
                  className="font-serif pointer-events-none absolute -top-10 -left-2 md:-top-16 md:-left-4 select-none"
                  style={{
                    fontSize: "clamp(120px, 16vw, 200px)",
                    lineHeight: 1,
                    fontWeight: 400,
                    color: "rgba(10,10,10,0.04)",
                    letterSpacing: "-0.04em",
                  }}
                >
                  {step.n}
                </span>
                <div
                  className="relative pt-6"
                  style={{ borderTop: "0.5pt solid rgba(10,10,10,0.12)" }}
                >
                  <p
                    className="font-mono tabular-nums text-[11px] mb-5"
                    style={{
                      color: "var(--pq-bronze)",
                      letterSpacing: "0.18em",
                    }}
                  >
                    STEP · {step.n}
                  </p>
                  <h3
                    className="font-serif mb-4"
                    style={{
                      fontSize: "clamp(20px, 1.8vw, 26px)",
                      lineHeight: 1.15,
                      letterSpacing: "-0.01em",
                      color: "var(--pq-ink)",
                      fontWeight: 500,
                    }}
                  >
                    {step.title}
                  </h3>
                  <p
                    className="font-serif"
                    style={{
                      fontSize: "15px",
                      lineHeight: 1.65,
                      color: "#3A3A3A",
                    }}
                  >
                    {step.body}
                  </p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ─── Section divider ─── */}
      <div
        className="flex items-center justify-center"
        style={{ backgroundColor: "var(--pq-ivory)" }}
        aria-hidden
      >
        <span
          className="h-px"
          style={{ width: "6em", backgroundColor: "rgba(139,111,71,0.5)" }}
        />
      </div>

      {/* ─── 5.5 ARCHETYPE — Ivory, calibration questionnaire + 8 archetypes ─── */}
      <section
        id="archetype"
        className="py-20 md:py-28 lg:py-40"
        style={{ backgroundColor: "var(--pq-ivory)", color: "var(--pq-ink)" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <motion.div {...motionProps(fadeUp)} className="max-w-3xl mb-10 md:mb-12">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span
                aria-hidden
                className="h-px w-7"
                style={{ backgroundColor: "rgba(139, 111, 71, 0.8)" }}
              />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                Calibration
              </span>
            </div>
            <p className="pq-deck pq-deck--ink mb-4">
              Twenty questions, then the desk begins to write.
            </p>
            <h2
              className="font-serif mb-10"
              style={{
                fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 500,
                color: "var(--pq-ink)",
              }}
            >
              Before the desk writes you a single word,
              <br />
              it asks you twenty questions.
            </h2>
            <p
              className="font-serif"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "#3A3A3A",
              }}
            >
              20-question onboarding. 8 investor archetypes. Your reports are
              tuned to the one you match — and the questionnaire is available
              to retake whenever your stance changes. The desk doesn&apos;t guess
              what you are; it asks.
            </p>
            <div
              className="mt-10 h-px"
              style={{
                width: "4em",
                backgroundColor: "rgba(139, 111, 71, 0.5)",
              }}
              aria-hidden
            />
          </motion.div>

          {/* Two-column editorial grid */}
          <div className="grid grid-cols-1 md:grid-cols-[1.1fr_0.9fr] gap-12 md:gap-16">
            {/* LEFT — Sample Questions */}
            <motion.div {...motionProps(fadeUp)}>
              <div className="mb-8 inline-flex items-center gap-2.5">
                <span
                  aria-hidden
                  className="h-px w-6"
                  style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }}
                />
                <span
                  className="font-serif text-[10.5px] uppercase"
                  style={{
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                  }}
                >
                  Sample Questions
                </span>
              </div>

              {/* Question 01 */}
              <div
                className="rounded-sm p-6 md:p-7 mb-6"
                style={{
                  backgroundColor: "rgba(10,10,10,0.02)",
                  border: "0.5pt solid rgba(10,10,10,0.10)",
                }}
              >
                <div className="flex items-baseline justify-between mb-4">
                  <span
                    className="font-mono tabular-nums text-[11px]"
                    style={{
                      letterSpacing: "0.14em",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    01 / 20
                  </span>
                  <span
                    className="font-serif italic text-[11px]"
                    style={{ color: "#6B6B6B" }}
                  >
                    drawdown reflex
                  </span>
                </div>
                <p
                  className="font-serif mb-5"
                  style={{
                    fontSize: "15.5px",
                    lineHeight: 1.5,
                    color: "var(--pq-ink)",
                  }}
                >
                  If the index drops 20% in a week, your first instinct is to:
                </p>
                <ul className="space-y-2.5">
                  {[
                    "Deploy capital into the decline",
                    "Hold positions and observe",
                    "Reduce exposure toward cash",
                  ].map((opt) => (
                    <li
                      key={opt}
                      className="flex items-center gap-3"
                      style={{ fontSize: "13.5px", color: "#3A3A3A" }}
                    >
                      <span
                        aria-hidden
                        className="inline-block rounded-full"
                        style={{
                          width: 10,
                          height: 10,
                          border: "1pt solid rgba(10,10,10,0.35)",
                        }}
                      />
                      <span className="font-serif">{opt}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Question 07 */}
              <div
                className="rounded-sm p-6 md:p-7 mb-6"
                style={{
                  backgroundColor: "rgba(10,10,10,0.02)",
                  border: "0.5pt solid rgba(10,10,10,0.10)",
                }}
              >
                <div className="flex items-baseline justify-between mb-4">
                  <span
                    className="font-mono tabular-nums text-[11px]"
                    style={{
                      letterSpacing: "0.14em",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    07 / 20
                  </span>
                  <span
                    className="font-serif italic text-[11px]"
                    style={{ color: "#6B6B6B" }}
                  >
                    concentration posture
                  </span>
                </div>
                <p
                  className="font-serif mb-5"
                  style={{
                    fontSize: "15.5px",
                    lineHeight: 1.5,
                    color: "var(--pq-ink)",
                  }}
                >
                  A single position has grown to 35% of the portfolio. You
                  would describe this as:
                </p>
                <ul className="space-y-2.5">
                  {[
                    "High-conviction concentration",
                    "Drift worth rebalancing",
                    "Unacceptable single-name risk",
                  ].map((opt) => (
                    <li
                      key={opt}
                      className="flex items-center gap-3"
                      style={{ fontSize: "13.5px", color: "#3A3A3A" }}
                    >
                      <span
                        aria-hidden
                        className="inline-block rounded-full"
                        style={{
                          width: 10,
                          height: 10,
                          border: "1pt solid rgba(10,10,10,0.35)",
                        }}
                      />
                      <span className="font-serif">{opt}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <p
                className="font-serif italic"
                style={{
                  fontSize: "12.5px",
                  lineHeight: 1.6,
                  color: "#6B6B6B",
                }}
              >
                18 more questions on horizon, drawdown tolerance, leverage
                posture, thesis changes, and event sensitivity.
              </p>
            </motion.div>

            {/* RIGHT — Eight Archetypes */}
            <motion.div {...motionProps(fadeUp)}>
              <div className="mb-8 inline-flex items-center gap-2.5">
                <span
                  aria-hidden
                  className="h-px w-6"
                  style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }}
                />
                <span
                  className="font-serif text-[10.5px] uppercase"
                  style={{
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                  }}
                >
                  Eight Archetypes
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 md:gap-4">
                {[
                  {
                    n: "\u2460",
                    name: "Growth Seeker",
                    desc: "Small tail, wide horizon, high thesis churn.",
                  },
                  {
                    n: "\u2461",
                    name: "Dividend Compounder",
                    desc: "Yield-first, slow turnover, income ladder.",
                  },
                  {
                    n: "\u2462",
                    name: "Tail Hedger",
                    desc: "Convex exposure, short-vol avoidance, insurance book.",
                  },
                  {
                    n: "\u2463",
                    name: "Contrarian Value",
                    desc: "Low-valuation universe, long-hold, out-of-favor.",
                  },
                  {
                    n: "\u2464",
                    name: "Balanced Generalist",
                    desc: "Equal-risk tilts, diversified sector, 4-factor mix.",
                  },
                  {
                    n: "\u2465",
                    name: "Momentum Rider",
                    desc: "Trend-following, short-hold, quarterly rotation.",
                  },
                  {
                    n: "\u2466",
                    name: "Cash-Heavy Conservatist",
                    desc: "Low gross, high liquidity buffer, event-driven deployment.",
                  },
                  {
                    n: "\u2467",
                    name: "Event-Driven Tactician",
                    desc: "Catalyst-dependent, earnings / merger / macro timing.",
                  },
                ].map((a) => (
                  <div
                    key={a.name}
                    className="rounded-sm p-4 md:p-5"
                    style={{
                      backgroundColor: "rgba(10,10,10,0.02)",
                      border: "0.5pt solid rgba(10,10,10,0.10)",
                    }}
                  >
                    <div
                      className="font-serif italic mb-2"
                      style={{
                        fontSize: "14px",
                        color: "var(--pq-bronze)",
                        lineHeight: 1,
                      }}
                    >
                      {a.n}
                    </div>
                    <div
                      className="font-serif mb-1.5"
                      style={{
                        fontSize: "15px",
                        lineHeight: 1.25,
                        color: "var(--pq-ink)",
                        fontWeight: 500,
                      }}
                    >
                      {a.name}
                    </div>
                    <div
                      style={{
                        fontSize: "12px",
                        lineHeight: 1.55,
                        color: "#4A4A4A",
                      }}
                    >
                      {a.desc}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>

          {/* Footer micro */}
          <motion.p
            {...motionProps(fadeUp)}
            className="font-serif italic mt-14 md:mt-20 max-w-3xl"
            style={{
              fontSize: "12.5px",
              lineHeight: 1.65,
              color: "#6B6B6B",
            }}
          >
            Assignment is a starting point, not a verdict. The questionnaire
            can be retaken at any time, and the desk re-tunes within 24 hours.
            No archetype is a recommendation — they are descriptive frames,
            not prescriptive labels.
          </motion.p>

          {/* Take the assessment — clean CTA, no roman numerals */}
          <motion.div
            {...motionProps(fadeUp)}
            className="mt-10 md:mt-14 flex flex-wrap items-center gap-x-6 gap-y-4"
          >
            <Link
              href="/signup"
              className="group inline-flex h-11 items-center gap-2 rounded-sm px-5 text-[13px] font-medium transition-transform duration-200 hover:-translate-y-px active:translate-y-0"
              style={{
                backgroundColor: "var(--pq-ink)",
                color: "var(--pq-ivory)",
                letterSpacing: "0.02em",
              }}
            >
              Take the assessment
              <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
            </Link>
            <span
              className="font-serif italic"
              style={{
                fontSize: "12px",
                letterSpacing: "0.02em",
                color: "#6B6B6B",
              }}
            >
              Twenty items · approximately four minutes
            </span>
          </motion.div>
        </div>
      </section>

      {/* ─── 5c. THE ENGINE — Vantablack, quant / risk / AI inventory ─── */}
      <section
        id="the-engine"
        className="py-32 md:py-48 lg:py-56"
        style={{ backgroundColor: "#0A0A0A", color: "var(--pq-ivory)" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <motion.div {...motionProps(fadeUp)} className="max-w-3xl mb-10 md:mb-14">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span
                aria-hidden
                className="h-px w-7"
                style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }}
              />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                The Engine
              </span>
            </div>
            <p className="pq-deck mb-4">
              Measurement instruments, never directives.
            </p>
            <h2
              className="pq-silver-matte font-serif mb-10"
              style={{
                fontSize: "clamp(2rem, 4vw, 3.25rem)",
                lineHeight: 1.1,
                letterSpacing: "-0.02em",
                fontWeight: 500,
              }}
            >
              Beneath every report,
              <br />
              58 models running quietly.
            </h2>
            <p
              className="font-serif"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "rgba(245,240,232,0.65)",
              }}
            >
              Each artifact is synthesized from measurement primitives — not
              heuristics, not prompts. Below is a partial inventory of what
              runs in the background, every minute the market is open.
            </p>
            <p
              className="mt-4 font-serif text-[12px]"
              style={{
                letterSpacing: "0.04em",
                color: "var(--pq-bronze)",
              }}
            >
              Click any model to read its methodology.
            </p>
          </motion.div>

          {/* Bronze divider */}
          <div className="flex justify-center mb-10 md:mb-14" aria-hidden>
            <span
              className="h-px"
              style={{ width: "6em", backgroundColor: "rgba(139,111,71,0.5)" }}
            />
          </div>

          {/* 3-column inventory grid — unified heights & baselines */}
          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 md:grid-cols-3 gap-14 md:gap-0 items-stretch"
          >
            {[
              {
                key: "QUANT",
                label: "Quant",
                numeric: 58,
                numericLabel: "fifty-eight statistical models",
                isWord: false,
                caption: "statistical models",
                models: MODEL_DEFS.filter((m) => m.category === "QUANT"),
                extra: <li style={{ color: "var(--pq-muted)" }}>(+40 more)</li>,
                footnote:
                  "Including behavioral, cross-sectional, and ML-based variants.",
                borderRight: true,
              },
              {
                key: "RISK",
                label: "Risk",
                numeric: 7,
                numericLabel: "seven-layer defense",
                isWord: false,
                caption: "7-Layer Defense",
                models: MODEL_DEFS.filter((m) => m.category === "RISK"),
                extra: null,
                footnote:
                  "Each layer acts as a circuit-breaker on every report: if a threshold is breached, the artifact flags it — not silences it.",
                borderRight: true,
              },
              {
                key: "AI",
                label: "AI",
                numeric: null,
                wordValue: "Claude",
                isWord: true,
                caption: "Claude-augmented synthesis",
                models: MODEL_DEFS.filter((m) => m.category === "AI"),
                extra: null,
                footnote:
                  "AI is used to summarize the quant and risk outputs in plain English. It never originates a directive.",
                borderRight: false,
              },
            ].map((col, idx) => (
              <motion.div
                key={col.key}
                variants={prefersReduced ? undefined : fadeUp}
                className={`flex flex-col px-0 md:px-10 lg:px-12 ${col.borderRight ? "md:border-r" : ""} ${idx > 0 ? "border-t md:border-t-0 pt-12 md:pt-0" : ""}`}
                style={{
                  borderColor: "rgba(245,240,232,0.08)",
                }}
              >
                {/* Category label — fixed baseline */}
                <p
                  className="font-serif text-xs uppercase mb-5 flex items-center gap-3"
                  style={{
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                    minHeight: "1.25rem",
                  }}
                >
                  <span aria-hidden style={{ opacity: 0.6, letterSpacing: "0.25em" }}>
                    •—•
                  </span>
                  {col.label}
                </p>

                {/* Number / word — unified size, flex-aligned bottom baseline */}
                <h3
                  className="font-serif mb-2 font-mono tabular-nums"
                  style={{
                    fontSize: "clamp(4.5rem, 7vw, 6rem)",
                    lineHeight: 1,
                    letterSpacing: "-0.03em",
                    fontWeight: 400,
                    color: "var(--pq-ivory)",
                    fontFamily: col.isWord
                      ? "var(--font-serif), Georgia, serif"
                      : undefined,
                    display: "flex",
                    alignItems: "flex-end",
                    minHeight: "clamp(4.5rem, 7vw, 6rem)",
                  }}
                >
                  {col.isWord ? (
                    col.wordValue
                  ) : (
                    <CountUp
                      to={col.numeric as number}
                      ariaLabel={col.numericLabel}
                    />
                  )}
                </h3>

                {/* Caption — fixed height reserved so lists align */}
                <p
                  className="text-sm mb-10"
                  style={{
                    color: "var(--pq-muted)",
                    minHeight: "1.25rem",
                  }}
                >
                  {col.caption}
                </p>

                {/* Model list */}
                <ul
                  className="font-mono space-y-1"
                  style={{
                    fontSize: "13px",
                    lineHeight: 1.8,
                    fontVariantNumeric: "tabular-nums",
                    color: "var(--pq-ivory)",
                  }}
                >
                  {col.models.map((m) => (
                    <li key={m.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedModelId(m.id)}
                        aria-haspopup="dialog"
                        aria-expanded={selectedModelId === m.id}
                        className="pq-model-item text-left"
                      >
                        {m.name}
                      </button>
                    </li>
                  ))}
                  {col.extra}
                </ul>

                {/* Footnote — flush bottom of column */}
                <p
                  className="mt-auto pt-8 font-serif text-[11px] italic leading-relaxed"
                  style={{ color: "var(--pq-muted)" }}
                >
                  {col.footnote}
                </p>
              </motion.div>
            ))}
          </motion.div>

          {/* Figure caption */}
          <motion.p
            {...motionProps(fadeUp)}
            className="mt-20 md:mt-28 max-w-3xl font-serif text-[11.5px] italic leading-relaxed"
            style={{ color: "var(--pq-muted)" }}
          >
            All models are measurement instruments. They quantify, detect, and
            describe &mdash; they do not generate buy / sell / hold
            instructions. Every output feeds the 17 artifacts as observations,
            never as directives. Informational research only.
          </motion.p>
        </div>

        {/* ─── Engine drawer: methodology card ─── */}
        <AnimatePresence>
          {selectedModel && (
            <>
              {/* Backdrop */}
              <motion.button
                key="engine-backdrop"
                type="button"
                aria-label="Close methodology"
                onClick={() => setSelectedModelId(null)}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="fixed inset-0 z-40 cursor-default"
                style={{ backgroundColor: "rgba(10,10,10,0.6)" }}
              />

              {/* Desktop: right-side drawer */}
              <motion.aside
                key="engine-drawer-desktop"
                role="dialog"
                aria-modal="true"
                aria-labelledby="engine-model-title"
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="hidden md:flex fixed top-0 right-0 bottom-0 z-50 w-[28rem] flex-col overflow-y-auto"
                style={{
                  backgroundColor: "#111111",
                  borderLeft: "1px solid rgba(139,111,71,0.4)",
                  color: "var(--pq-ivory)",
                }}
              >
                <EngineDrawerContent
                  model={selectedModel}
                  onClose={() => setSelectedModelId(null)}
                />
              </motion.aside>

              {/* Mobile: bottom sheet */}
              <motion.aside
                key="engine-drawer-mobile"
                role="dialog"
                aria-modal="true"
                aria-labelledby="engine-model-title-mobile"
                initial={{ y: "100%" }}
                animate={{ y: 0 }}
                exit={{ y: "100%" }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="md:hidden fixed left-0 right-0 bottom-0 z-50 flex flex-col overflow-y-auto rounded-t-2xl"
                style={{
                  maxHeight: "80vh",
                  backgroundColor: "#111111",
                  borderTop: "1px solid rgba(139,111,71,0.4)",
                  color: "var(--pq-ivory)",
                }}
              >
                <EngineDrawerContent
                  model={selectedModel}
                  onClose={() => setSelectedModelId(null)}
                  mobile
                />
              </motion.aside>
            </>
          )}
        </AnimatePresence>
      </section>

      {/* ─── 6. DASHBOARD PREVIEW — Ivory, Vantablack mockup ─── */}
      <section
        id="dashboard-preview"
        className="py-20 md:py-28 lg:py-40"
        style={{ backgroundColor: "var(--pq-ivory)", color: "var(--pq-ink)" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-8 md:mb-12">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span aria-hidden className="h-px w-7" style={{ backgroundColor: "rgba(139, 111, 71, 0.8)" }} />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                Research Terminal
              </span>
            </div>
            <h2
              className="font-serif mb-10 md:mb-14"
              style={{
                fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 500,
                color: "var(--pq-ink)",
              }}
            >
              The dashboard your future-self reads
              <br />
              every Monday at 7:00 AM.
            </h2>
            <p
              className="font-serif"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "#3A3A3A",
              }}
            >
              Risk Board, Weekly Memo, and Earnings Pre-Brief — delivered as PDF, mirrored in the app.
            </p>
          </motion.div>

          <motion.div {...motionProps(scaleIn)} className="relative">
            <div
              className="rounded-sm overflow-hidden"
              style={{
                backgroundColor: "var(--pq-ink)",
                border: "0.5pt solid rgba(10,10,10,0.15)",
                boxShadow: "0 40px 80px -40px rgba(10,10,10,0.4)",
              }}
            >
              {/* Terminal chrome */}
              <div
                className="flex items-center justify-between px-5 py-3"
                style={{ borderBottom: "0.5pt solid rgba(245,240,232,0.08)" }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: "var(--pq-bronze)" }}
                  />
                  <span
                    className="font-serif text-[10.5px] uppercase"
                    style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
                  >
                    PivoxQuant · Monday Brief
                  </span>
                </div>
                <span
                  className="font-mono tabular-nums text-[11px]"
                  style={{ color: "rgba(245,240,232,0.5)" }}
                >
                  07:00 KST
                </span>
              </div>

              <div className="flex min-h-[420px] md:min-h-[500px]">
                {/* Sidebar — Vantablack rail */}
                <div
                  className="hidden md:flex flex-col w-52 p-5"
                  style={{ borderRight: "0.5pt solid rgba(245,240,232,0.08)" }}
                >
                  <span
                    className="font-serif text-[11px] uppercase mb-10"
                    style={{
                      letterSpacing: "0.22em",
                      color: "var(--pq-ivory)",
                      fontWeight: 500,
                    }}
                  >
                    PIVOXQUANT
                  </span>
                  <nav className="space-y-0.5">
                    {[
                      { icon: Home, label: "Home", active: true },
                      { icon: Activity, label: "Market", active: false },
                      { icon: Target, label: "Research", active: false },
                      { icon: Shield, label: "Risk Board", active: false },
                      { icon: Brain, label: "Artifacts", active: false },
                      { icon: Bell, label: "Alerts", active: false },
                      { icon: Settings, label: "Settings", active: false },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className="flex items-center gap-2.5 px-2.5 py-2 rounded-sm text-[12.5px] font-serif transition-colors"
                        style={{
                          color: item.active ? "var(--pq-ivory)" : "rgba(245,240,232,0.5)",
                          backgroundColor: item.active ? "rgba(139,111,71,0.12)" : "transparent",
                          borderLeft: item.active ? "2px solid var(--pq-bronze)" : "2px solid transparent",
                        }}
                      >
                        <item.icon className="w-4 h-4" strokeWidth={1.5} />
                        {item.label}
                      </div>
                    ))}
                  </nav>
                </div>

                {/* Main content */}
                <div className="flex-1 p-5 md:p-7">
                  {/* Metric cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
                    {[
                      { label: "Portfolio Value", value: "$127,450", sub: "+12.4% all-time" },
                      { label: "Risk Board", value: "85", sub: "7 signals observed" },
                      { label: "Artifacts Ready", value: "14", sub: "3 new this week" },
                    ].map((m) => (
                      <div
                        key={m.label}
                        className="rounded-sm p-4"
                        style={{
                          backgroundColor: "rgba(255,255,255,0.02)",
                          border: "0.5pt solid rgba(245,240,232,0.08)",
                        }}
                      >
                        <p
                          className="font-serif text-[9.5px] uppercase mb-2"
                          style={{ letterSpacing: "0.22em", color: "var(--pq-muted)" }}
                        >
                          {m.label}
                        </p>
                        <p
                          className="font-mono tabular-nums text-[18px] mb-1.5"
                          style={{ color: "var(--pq-ivory)", letterSpacing: "-0.01em" }}
                        >
                          {m.value}
                        </p>
                        <p
                          className="font-serif text-[11px]"
                          style={{ color: "rgba(245,240,232,0.5)" }}
                        >
                          {m.sub}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Chart */}
                  <div
                    className="rounded-sm p-5 mb-5"
                    style={{
                      backgroundColor: "rgba(255,255,255,0.02)",
                      border: "0.5pt solid rgba(245,240,232,0.08)",
                    }}
                  >
                    <div className="flex items-center justify-between mb-4">
                      <span
                        className="font-serif text-[10.5px] uppercase"
                        style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
                      >
                        Equity · Observation
                      </span>
                      <div className="flex gap-1">
                        {["1M", "3M", "6M", "1Y", "ALL"].map((t) => (
                          <span
                            key={t}
                            className="px-2 py-0.5 rounded-sm font-mono tabular-nums text-[10px]"
                            style={{
                              backgroundColor: t === "6M" ? "var(--pq-bronze)" : "transparent",
                              color: t === "6M" ? "var(--pq-ink)" : "rgba(245,240,232,0.5)",
                              letterSpacing: "0.05em",
                            }}
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="h-28">
                      <DashboardEquityCurve />
                    </div>
                  </div>

                  {/* Observation list */}
                  <div
                    className="rounded-sm overflow-hidden"
                    style={{
                      backgroundColor: "rgba(255,255,255,0.02)",
                      border: "0.5pt solid rgba(245,240,232,0.08)",
                    }}
                  >
                    <div
                      className="px-4 py-2.5"
                      style={{ borderBottom: "0.5pt solid rgba(245,240,232,0.08)" }}
                    >
                      <span
                        className="font-serif text-[10.5px] uppercase"
                        style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
                      >
                        This Week&rsquo;s Observations
                      </span>
                    </div>
                    {[
                      { ticker: "AAPL", name: "Apple", signal: "POSITIVE", score: 78, change: "+1.24%" },
                      { ticker: "MSFT", name: "Microsoft", signal: "POSITIVE", score: 82, change: "+0.82%" },
                      { ticker: "NVDA", name: "NVIDIA", signal: "NEUTRAL", score: 52, change: "−0.34%" },
                    ].map((item, i, arr) => (
                      <div
                        key={item.ticker}
                        className="flex items-center justify-between px-4 py-2.5"
                        style={{
                          borderBottom:
                            i < arr.length - 1
                              ? "0.5pt solid rgba(245,240,232,0.06)"
                              : "none",
                        }}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span
                            className="font-serif text-[13px] truncate"
                            style={{ color: "var(--pq-ivory)" }}
                          >
                            {item.name}
                          </span>
                          <span
                            className="font-mono tabular-nums text-[11px] shrink-0"
                            style={{ color: "var(--pq-muted)" }}
                          >
                            {item.ticker}
                          </span>
                        </div>
                        <div className="flex items-center gap-4">
                          <span
                            className="font-mono tabular-nums text-[11.5px]"
                            style={{
                              color: item.change.startsWith("+") ? "#3C7A52" : "rgba(245,240,232,0.6)",
                            }}
                          >
                            {item.change}
                          </span>
                          <span
                            className="font-mono tabular-nums text-[10px] px-1.5 py-0.5 rounded-sm"
                            style={{
                              color:
                                item.signal === "POSITIVE"
                                  ? "#3C7A52"
                                  : "var(--pq-muted)",
                              border: `0.5pt solid ${
                                item.signal === "POSITIVE"
                                  ? "rgba(60,122,82,0.4)"
                                  : "rgba(245,240,232,0.15)"
                              }`,
                              letterSpacing: "0.06em",
                            }}
                          >
                            {item.signal}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <p
                    className="mt-4 font-serif text-[10.5px] italic"
                    style={{ color: "rgba(245,240,232,0.4)" }}
                  >
                    Observational signals. Not investment advice.
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 7. PRICING — Vantablack, 3 tiers (21st.dev editorial pattern, KRW) ─── */}
      <section
        id="pricing"
        className="py-20 md:py-28 lg:py-40"
        style={{ backgroundColor: "#0A0A0A" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-20 md:mb-24">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span aria-hidden className="h-px w-7" style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }} />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                Membership
              </span>
            </div>
            <p className="pq-deck mb-4">
              Three tiers. One incentive — your quiet compounding.
            </p>
            <h2
              className="font-serif mb-8 md:mb-12"
              style={{
                fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 500,
                color: "var(--pq-ivory)",
              }}
            >
              Flat monthly fee.
              <br />
              No trading commissions. No performance cut.
            </h2>
            <p
              className="font-serif"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "rgba(245,240,232,0.65)",
              }}
            >
              We are never paid when you trade. We are paid when you stay subscribed. The incentive is your quiet compounding.
            </p>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 items-stretch"
          >
            {[
              {
                name: "Observer",
                price: "0",
                period: "forever",
                unit: "KRW",
                dark: false,
                recommended: false,
                tagline: "Read-only observation. 1 artifact per week.",
                features: [
                  "Weekly Memo (abridged)",
                  "Portfolio observation dashboard",
                  "1 broker connection",
                ],
                cta: "Create free account",
                href: "/signup",
              },
              {
                name: "Operator",
                price: "9,900",
                period: "per month",
                unit: "KRW",
                dark: true,
                recommended: true,
                tagline: "Full desk access. 17 artifacts. Weekly ship.",
                features: [
                  "Everything in Observer",
                  "7 Operator artifacts — Morning Brief Plus, Earnings Pre-Brief, DD Checklist, Burn Rate, Credit Rating, AI Suite, Weekly Memo (full)",
                  "2 broker connections",
                  "Risk Board — 7-layer observation",
                ],
                cta: "Start 7-day trial",
                href: "/signup",
              },
              {
                name: "Partner",
                price: "19,900",
                period: "per month",
                unit: "KRW",
                dark: false,
                recommended: false,
                tagline: "Concierge research. Priority renders. Quarterly 1:1 notes.",
                features: [
                  "Everything in Operator",
                  "10 Partner artifacts — Risk Board Deck, Year-End Letter, Quarterly Self-Report, Capital Allocation, Insider Mirror, Portfolio Segment, Dividend Income, Monthly Finance, Self-Audit, Brag Card",
                  "Priority render queue",
                  "Quarterly 1:1 desk notes",
                ],
                cta: "Start 7-day trial",
                href: "/signup",
              },
            ].map((p) => {
              const isDark = p.dark;
              return (
                <motion.div
                  key={p.name}
                  variants={fadeUp}
                  className="relative rounded-sm p-8 md:p-9 flex flex-col"
                  style={{
                    backgroundColor: isDark ? "#111111" : "var(--pq-ivory)",
                    border: p.recommended
                      ? "1px solid var(--pq-bronze)"
                      : isDark
                        ? "0.5pt solid rgba(245,240,232,0.10)"
                        : "0.5pt solid rgba(10,10,10,0.10)",
                    boxShadow: p.recommended
                      ? "0 40px 80px -40px rgba(139,111,71,0.35)"
                      : "none",
                  }}
                >
                  {p.recommended && (
                    <span
                      className="absolute -top-2.5 left-8 px-2.5 py-[3px] font-serif text-[9.5px] uppercase"
                      style={{
                        backgroundColor: "#0A0A0A",
                        color: "var(--pq-bronze)",
                        letterSpacing: "0.3em",
                        border: "1px solid var(--pq-bronze)",
                        borderRadius: "2px",
                      }}
                    >
                      Most chosen
                    </span>
                  )}

                  {/* Tier name + bronze hairline */}
                  <div className="mb-6 flex items-center gap-3">
                    <span
                      className="font-serif text-[11px] uppercase"
                      style={{
                        letterSpacing: "0.26em",
                        color: "var(--pq-bronze)",
                      }}
                    >
                      {p.name}
                    </span>
                    <span
                      aria-hidden
                      className="h-px flex-1"
                      style={{
                        backgroundColor: p.recommended
                          ? "var(--pq-bronze)"
                          : isDark
                            ? "rgba(245,240,232,0.14)"
                            : "rgba(10,10,10,0.12)",
                        opacity: p.recommended ? 0.9 : 0.6,
                      }}
                    />
                  </div>

                  {/* Price — KRW, tabular nums. No symbol prefix. */}
                  <div className="flex items-baseline gap-2 mb-3">
                    <span
                      className="font-mono tabular-nums"
                      style={{
                        fontSize: "clamp(44px, 4.6vw, 56px)",
                        lineHeight: 1,
                        letterSpacing: "-0.03em",
                        fontWeight: 400,
                        color: isDark ? "var(--pq-ivory)" : "var(--pq-ink)",
                      }}
                    >
                      {p.price}
                    </span>
                    <span
                      className="font-serif text-[11px] uppercase"
                      style={{
                        letterSpacing: "0.2em",
                        color: isDark ? "rgba(245,240,232,0.55)" : "#6B6B6B",
                      }}
                    >
                      {p.unit}
                    </span>
                  </div>
                  <p
                    className="font-serif text-[12px] mb-7"
                    style={{
                      color: isDark ? "rgba(245,240,232,0.48)" : "#6B6B6B",
                      letterSpacing: "0.02em",
                    }}
                  >
                    {p.period}
                  </p>

                  {/* Tagline */}
                  <p
                    className="font-serif italic text-[13px] leading-snug mb-7 pb-6"
                    style={{
                      color: isDark ? "rgba(245,240,232,0.72)" : "#2A2A2A",
                      borderBottom: isDark
                        ? "0.5pt solid rgba(245,240,232,0.10)"
                        : "0.5pt solid rgba(10,10,10,0.08)",
                    }}
                  >
                    {p.tagline}
                  </p>

                  <ul className="space-y-3 mb-10 flex-1">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2.5">
                        <Check
                          className="w-3.5 h-3.5 mt-[3px] shrink-0"
                          strokeWidth={2}
                          style={{
                            color: p.recommended
                              ? "var(--pq-bronze)"
                              : isDark
                                ? "var(--pq-ivory)"
                                : "var(--pq-ink)",
                          }}
                        />
                        <span
                          className="font-serif text-[13.5px] leading-snug"
                          style={{
                            color: isDark ? "rgba(245,240,232,0.78)" : "#2A2A2A",
                          }}
                        >
                          {f}
                        </span>
                      </li>
                    ))}
                  </ul>

                  <Link
                    href={p.href}
                    className="block text-center w-full py-3 px-4 font-serif text-[13.5px] transition-colors"
                    style={{
                      backgroundColor: p.recommended
                        ? "var(--pq-bronze)"
                        : isDark
                          ? "var(--pq-ivory)"
                          : "var(--pq-ink)",
                      color: p.recommended
                        ? "var(--pq-ink)"
                        : isDark
                          ? "var(--pq-ink)"
                          : "var(--pq-ivory)",
                      letterSpacing: "0.02em",
                      borderRadius: "2px",
                    }}
                  >
                    {p.cta}
                  </Link>
                </motion.div>
              );
            })}
          </motion.div>

          <motion.p
            {...motionProps(fadeUp)}
            className="mt-12 font-serif text-[11px] italic leading-relaxed"
            style={{ color: "rgba(245,240,232,0.45)" }}
          >
            Billed in KRW. VAT included. Cancel anytime. Informational research tool — no trade instructions issued.
          </motion.p>
        </div>
      </section>

      {/* ─── 8. PULL-QUOTE BELT — Ivory, minimal ─── */}
      <section
        className="py-32 md:py-48 lg:py-56"
        style={{ backgroundColor: "var(--pq-ivory)" }}
      >
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div {...motionProps(fadeUp)}>
            <div className="flex items-center justify-center gap-5 mb-10">
              <span
                aria-hidden
                className="h-px"
                style={{ width: "8em", backgroundColor: "rgba(139,111,71,0.5)" }}
              />
              <span
                className="font-mono tabular-nums text-[10px] uppercase"
                style={{
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                House view
              </span>
              <span
                aria-hidden
                className="h-px"
                style={{ width: "8em", backgroundColor: "rgba(139,111,71,0.5)" }}
              />
            </div>
            <blockquote
              className="font-serif italic"
              style={{
                fontSize: "clamp(22px, 3vw, 34px)",
                lineHeight: 1.3,
                letterSpacing: "-0.015em",
                fontWeight: 400,
                color: "var(--pq-ink)",
              }}
            >
              &ldquo;The quietest portfolios are the ones whose owner writes their own research, every single week.&rdquo;
            </blockquote>
            <p
              className="mt-10 font-serif text-[12.5px]"
              style={{
                color: "#6B6B6B",
                letterSpacing: "0.02em",
              }}
            >
              — The editorial voice PivoxQuant is built around
            </p>
          </motion.div>
        </div>
      </section>

      {/* ─── 9. FINAL CTA — Vantablack, centered ─── */}
      <section
        className="py-32 md:py-48 lg:py-56"
        style={{ backgroundColor: "#0A0A0A" }}
      >
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div {...motionProps(fadeUp)}>
            <div className="mb-8 inline-flex items-center gap-2.5">
              <span aria-hidden className="h-px w-7" style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }} />
              <span
                className="font-serif text-[11px] uppercase"
                style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
              >
                Ready?
              </span>
              <span aria-hidden className="h-px w-7" style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }} />
            </div>
            <h2
              className="font-serif mb-8"
              style={{
                fontSize: "clamp(2rem, 4.8vw, 3.6rem)",
                lineHeight: 1.05,
                letterSpacing: "-0.025em",
                fontWeight: 500,
                backgroundImage:
                  "linear-gradient(180deg, #F5F0E8 0%, #C9C4BC 100%)",
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                color: "transparent",
              }}
            >
              Give your portfolio
              <br />
              someone to report to.
            </h2>
            <p
              className="font-serif mb-10 mx-auto"
              style={{
                fontSize: "clamp(14.5px, 1.2vw, 16px)",
                lineHeight: 1.65,
                color: "rgba(245,240,232,0.6)",
                maxWidth: "32em",
              }}
            >
              Seven days free. Cancel anytime. Visa · Master · Naver Pay · Kakao Pay.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-5">
              <Link
                href="/signup"
                className="pq-cta-underline group inline-flex items-center gap-2 font-serif px-7 py-3.5 transition-all"
                style={{
                  backgroundColor: "var(--pq-bronze)",
                  color: "var(--pq-ink)",
                  fontSize: "14px",
                  letterSpacing: "0.02em",
                  borderRadius: "2px",
                }}
              >
                Start 7-day trial
                <ArrowRight
                  className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-0.5"
                  strokeWidth={1.75}
                />
              </Link>
              <a
                href="#sample-reports"
                className="pq-cta-underline group inline-flex items-center gap-2 font-serif px-7 py-3.5 transition-all"
                style={{
                  border: "0.75pt solid var(--pq-bronze)",
                  color: "var(--pq-bronze)",
                  fontSize: "14px",
                  letterSpacing: "0.02em",
                  borderRadius: "2px",
                  backgroundColor: "transparent",
                }}
              >
                Read sample reports
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 9b. SOCIAL PROOF / LOGO STRIP — Partner badge above footer ─── */}
      <section
        className="py-16 md:py-20"
        style={{ backgroundColor: "#0A0A0A", borderTop: "0.5pt solid #2A2A2A" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.p
            {...motionProps(fadeUp)}
            className="font-serif text-center text-[11px] uppercase mb-10"
            style={{ letterSpacing: "0.22em", color: "var(--pq-muted)" }}
          >
            Data pipeline built on institutional standards
          </motion.p>
          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-2 md:grid-cols-4 gap-10 md:gap-12 items-center"
          >
            {["SEC EDGAR", "FMP", "Alpaca", "KIS"].map((name) => (
              <motion.div
                key={name}
                variants={fadeUp}
                className="flex items-center justify-center"
              >
                <span
                  className="font-serif text-[15px] md:text-[17px]"
                  style={{
                    color: "rgba(245,240,232,0.45)",
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    fontWeight: 400,
                  }}
                >
                  {name}
                </span>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ─── 10. FOOTER — Deep Vantablack ─── */}
      <footer
        className="mt-24 pt-28 pb-20 md:pt-32 md:pb-24"
        style={{
          backgroundColor: "#050505",
          borderTop: "0.5pt solid rgba(245,240,232,0.08)",
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-8 md:gap-10 mb-14">
            {/* Brand col */}
            <div className="col-span-2">
              <Link href="/" className="inline-block mb-5">
                <span
                  className="font-serif"
                  style={{
                    fontSize: "18px",
                    letterSpacing: "0.28em",
                    color: "var(--pq-ivory)",
                    fontWeight: 500,
                  }}
                >
                  PIVOXQUANT
                </span>
              </Link>
              <p
                className="font-serif max-w-xs"
                style={{
                  fontSize: "13.5px",
                  lineHeight: 1.6,
                  color: "rgba(245,240,232,0.5)",
                }}
              >
                Research desk for the self-managed portfolio.
              </p>
            </div>

            {/* Link columns */}
            {[
              {
                title: "Product",
                links: [
                  { label: "Features", href: "#features" },
                  { label: "Pricing", href: "#pricing" },
                  { label: "Sample reports", href: "#sample-reports" },
                  { label: "Dashboard preview", href: "#dashboard-preview" },
                  { label: "Feature explorer", href: "#feature-explorer" },
                ],
              },
              {
                title: "Research",
                links: [
                  { label: "Methodology", href: "#features" },
                  { label: "Backtest (2014–2024)", href: "/simulator/what-if" },
                  { label: "Sample reports", href: "#sample-reports" },
                  { label: "The engine", href: "#the-engine" },
                ],
              },
              {
                title: "Legal",
                links: [
                  { label: "Terms", href: "/terms" },
                  { label: "Privacy", href: "/privacy" },
                  { label: "Disclosures", href: "/terms" },
                  { label: "Similar advisory registration", href: "/terms" },
                  { label: "Cookie policy", href: "/privacy" },
                ],
              },
              {
                title: "Company",
                links: [
                  { label: "Contact", href: "mailto:seanbae1521@gmail.com" },
                  { label: "Sign in", href: "/login" },
                  { label: "Start trial", href: "/signup" },
                ],
              },
            ].map((col) => (
              <div key={col.title}>
                <h4
                  className="font-serif mb-4 uppercase"
                  style={{
                    fontSize: "10.5px",
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                  }}
                >
                  {col.title}
                </h4>
                <ul className="space-y-2.5">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <a
                        href={link.href}
                        className="font-serif transition-colors"
                        style={{
                          fontSize: "13px",
                          color: "rgba(245,240,232,0.55)",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = "var(--pq-ivory)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = "rgba(245,240,232,0.55)";
                        }}
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Divider + bottom bar */}
          <div
            className="pt-8"
            style={{ borderTop: "0.5pt solid rgba(245,240,232,0.08)" }}
          >
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
              <p
                className="font-serif italic"
                style={{
                  fontSize: "11.5px",
                  letterSpacing: "0.01em",
                  color: "rgba(245,240,232,0.5)",
                }}
              >
                © {new Date().getFullYear()} PivoxQuant &nbsp;·&nbsp; All rights reserved.
              </p>
              <p
                className="font-serif italic text-center"
                style={{
                  fontSize: "11px",
                  lineHeight: 1.6,
                  color: "rgba(245,240,232,0.4)",
                }}
              >
                PivoxQuant is not a licensed investment advisor, discretionary manager, or broker-dealer. Research tool only. Past performance does not guarantee future results.
              </p>
              <div className="flex items-center gap-4 md:justify-end">
                {[
                  { label: "GitHub", href: "https://github.com/seanbae-analyst/pivoxquant", external: true },
                  { label: "Email", href: "mailto:seanbae1521@gmail.com", external: false },
                ].map((s, i, arr) => (
                  <span key={s.label} className="inline-flex items-center gap-4">
                    <a
                      href={s.href}
                      target={s.external ? "_blank" : undefined}
                      rel={s.external ? "noopener noreferrer" : undefined}
                      className="font-serif transition-colors"
                      style={{
                        fontSize: "11.5px",
                        letterSpacing: "0.12em",
                        color: "rgba(245,240,232,0.4)",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = "var(--pq-bronze)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = "rgba(245,240,232,0.4)";
                      }}
                    >
                      {s.label.toUpperCase()}
                    </a>
                    {i < arr.length - 1 && (
                      <span
                        aria-hidden
                        className="font-serif"
                        style={{
                          fontSize: "11px",
                          color: "rgba(139,111,71,0.55)",
                        }}
                      >
                        ❦
                      </span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
