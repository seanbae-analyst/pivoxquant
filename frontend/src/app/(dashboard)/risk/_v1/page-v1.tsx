"use client";

/**
 * Risk Observation Board — Vantablack ink terminal card on ivory shell.
 *
 * Sections:
 *  1. Terminal header + title
 *  2. Sample-preview banner (when unauthenticated or empty portfolio)
 *  3. 4 KPI stats (VaR / ES / Max DD / Corr Risk Index)
 *  4. Seven-Layer Risk Defense ladder (inline)
 *  5. Correlation heatmap (Bronze gradient tiles on ink)
 *  6. Rolling 30-day VaR sparkline (Bronze stroke on ink)
 *  7. DisclaimerBanner
 *
 * Graceful degradation: if the viewer is not signed in (401) or has an
 * empty portfolio, we render a fully populated *illustrative* board with
 * a prominent "Sample preview" banner so the page communicates what the
 * Risk Board is for, even without user data. Neutral observation language
 * only — no recommend/advice/guarantee wording anywhere.
 */

import useSWR from "swr";
import { useMemo } from "react";
import { Info } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import {
  RISK_SUMMARY,
  RISK_LAYERS,
  RISK_CORRELATION,
  RISK_ROLLING_VAR,
} from "@/lib/endpoints";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { InteractiveLineChart } from "@/components/charts/interactive-line-chart";
import {
  type RiskLayer,
  type LayerStatus,
} from "@/components/risk/seven-layer-panel";

/* ────────────────────────────────────────────────────────────────────
 * Demo constants — used when the viewer is unauthenticated or has an
 * empty portfolio. Values are illustrative only (clearly labelled as
 * "Sample preview" in the banner) and use neutral observation language.
 * ──────────────────────────────────────────────────────────────────── */

interface RiskSummary {
  var_1d_pct: number;
  es_1d_pct: number;
  max_dd_90d_pct: number;
  corr_risk_index: number;
}

const DEMO_SUMMARY: RiskSummary = {
  var_1d_pct: -2.14,
  es_1d_pct: -3.42,
  max_dd_90d_pct: -8.7,
  corr_risk_index: 0.58,
};

const DEMO_LAYERS: RiskLayer[] = [
  { no: 1, name: "VaR Layer", status: "green", metricLabel: "Daily 1-day 95% VaR", metricValue: "−2.14%", observation: "Within observed band." },
  { no: 2, name: "Correlation Layer", status: "yellow", metricLabel: "Avg pairwise", metricValue: "0.62", observation: "Elevated — 4 holdings move in step." },
  { no: 3, name: "VIX Regime", status: "green", metricLabel: "VIX level", metricValue: "15.8", observation: "Low-volatility regime observed." },
  { no: 4, name: "Tail Risk", status: "green", metricLabel: "Tail ratio", metricValue: "1.18", observation: "Balanced — upside tail > downside." },
  { no: 5, name: "Daily Loss Guard", status: "green", metricLabel: "Today", metricValue: "−0.4%", observation: "Well within −3% self-set threshold." },
  { no: 6, name: "Sector Exposure", status: "yellow", metricLabel: "Max sector", metricValue: "34% Tech", observation: "Above 30% soft limit — concentration noted." },
  { no: 7, name: "Cash Buffer", status: "green", metricLabel: "Cash", metricValue: "12%", observation: "Above 8% floor." },
];

const DEMO_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "JPM", "XOM", "UNH"];
const DEMO_CORR_MATRIX: number[][] = [
  [1.00, 0.82, 0.78, 0.75, 0.71, 0.68, 0.62, 0.31, 0.15, 0.22],
  [0.82, 1.00, 0.74, 0.79, 0.70, 0.66, 0.58, 0.35, 0.18, 0.24],
  [0.78, 0.74, 1.00, 0.72, 0.68, 0.70, 0.74, 0.28, 0.11, 0.20],
  [0.75, 0.79, 0.72, 1.00, 0.76, 0.65, 0.55, 0.33, 0.17, 0.26],
  [0.71, 0.70, 0.68, 0.76, 1.00, 0.62, 0.54, 0.29, 0.14, 0.19],
  [0.68, 0.66, 0.70, 0.65, 0.62, 1.00, 0.59, 0.25, 0.12, 0.17],
  [0.62, 0.58, 0.74, 0.55, 0.54, 0.59, 1.00, 0.21, -0.05, 0.11],
  [0.31, 0.35, 0.28, 0.33, 0.29, 0.25, 0.21, 1.00, 0.44, 0.48],
  [0.15, 0.18, 0.11, 0.17, 0.14, 0.12, -0.05, 0.44, 1.00, 0.36],
  [0.22, 0.24, 0.20, 0.26, 0.19, 0.17, 0.11, 0.48, 0.36, 1.00],
];

/**
 * Deterministic 30-day rolling VaR series back-dated from today.
 * We avoid Math.random() so the SSR markup matches the first client
 * render (no hydration warnings).
 */
function buildDemoVarPoints(): { date: string; value: number }[] {
  const today = new Date();
  return Array.from({ length: 30 }, (_, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() - (29 - i));
    const iso = d.toISOString().slice(0, 10);
    // Smooth synthetic curve, range roughly -1.5% .. -2.6%.
    const base = -2.0;
    const wave = Math.sin(i / 3) * 0.4;
    const drift = ((i % 5) - 2) * 0.05;
    return { date: iso, value: Number((base + wave + drift).toFixed(2)) };
  });
}

/* ────────────────────────────────────────────────────────────────────
 * Fetcher that preserves the HTTP status code so we can distinguish
 * 401 (unauth) from other transient failures.
 * ──────────────────────────────────────────────────────────────────── */

const fetcher = async <T,>(url: string): Promise<T> => apiFetch<T>(url);

// Shared SWR options. shouldRetryOnError=false — 401 is not transient,
// retrying just burns requests.
const SWR_OPTS = {
  refreshInterval: 60_000,
  // Bug #3 (HANDOVER v22): aligned with useRiskSummary — 60s polling is
  // sufficient; focus revalidate just adds duplicate fetches on nav.
  revalidateOnFocus: false,
  dedupingInterval: 15_000,
  shouldRetryOnError: false,
} as const;

interface BackendLayer {
  no: number;
  name: string;
  metric_label: string;
  metric_value: string;
  status: "GREEN" | "YELLOW" | "RED";
  observation: string;
}
interface LayersResponse {
  layers: BackendLayer[];
  defense_score: number;
  overall_status: string;
}
interface RollingVarPoint {
  date: string;
  var_pct: number;
}
interface CorrelationPayload {
  labels: string[];
  matrix: number[][];
}

function mapStatus(s: "GREEN" | "YELLOW" | "RED"): LayerStatus {
  return s === "GREEN" ? "green" : s === "YELLOW" ? "yellow" : "red";
}

const STATUS_PILL: Record<LayerStatus, string> = {
  green: "pq-ink-pill--pos",
  yellow: "pq-ink-pill--neu",
  red: "pq-ink-pill--neg",
};
const STATUS_LABEL: Record<LayerStatus, string> = {
  green: "Within Band",
  yellow: "Elevated",
  red: "Above Limit",
};

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

/** True if the SWR error represents a 401. */
function is401(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

export default function RiskPage() {
  const {
    data: summary,
    error: summaryErr,
    isLoading: summaryLoading,
  } = useSWR<RiskSummary>(RISK_SUMMARY, fetcher, SWR_OPTS);
  const {
    data: layersData,
    error: layersErr,
    isLoading: layersLoading,
  } = useSWR<LayersResponse | BackendLayer[]>(RISK_LAYERS, fetcher, SWR_OPTS);
  const {
    data: corrData,
    error: corrErr,
    isLoading: corrLoading,
  } = useSWR<CorrelationPayload>(RISK_CORRELATION, fetcher, SWR_OPTS);
  const {
    data: rollingVar,
    error: rollingErr,
    isLoading: rollingLoading,
  } = useSWR<RollingVarPoint[]>(RISK_ROLLING_VAR, fetcher, SWR_OPTS);

  // BUG B FIX: suppress the "Sample preview" banner while any of the four
  // endpoints is still resolving its first response. Previously the banner
  // flashed for 2-3 s on mount because SWR's initial `data === undefined`
  // was interpreted as "no data → show demo board". Now we only decide
  // between real and sample states after at least one settlement (success
  // OR error) for each endpoint.
  const anyLoading =
    summaryLoading || layersLoading || corrLoading || rollingLoading;

  // Mapped layers from backend (if present).
  const apiLayers: RiskLayer[] | null = useMemo(() => {
    const raw = Array.isArray(layersData) ? layersData : layersData?.layers ?? null;
    if (!raw || raw.length === 0) return null;
    return raw.map((l) => ({
      no: l.no,
      name: l.name,
      metricLabel: l.metric_label,
      metricValue: l.metric_value,
      status: mapStatus(l.status),
      observation: l.observation,
    }));
  }, [layersData]);

  // Empty-portfolio detection: summary exists and all figures are zero,
  // and correlation payload is empty.
  const isEmptyPortfolio =
    !!summary &&
    summary.var_1d_pct === 0 &&
    summary.es_1d_pct === 0 &&
    summary.max_dd_90d_pct === 0 &&
    summary.corr_risk_index === 0 &&
    (!corrData || !corrData.matrix || corrData.matrix.length === 0);

  // Auth error: any of the four endpoints returned 401.
  const isAuthError =
    is401(summaryErr) ||
    is401(layersErr) ||
    is401(corrErr) ||
    is401(rollingErr);

  // Real data present? Require a non-empty summary plus at least one other
  // populated payload.
  const hasRealSummary = !!summary && !isEmptyPortfolio;
  const hasRealLayers = apiLayers != null;
  const hasRealCorr =
    Array.isArray(corrData?.matrix) && corrData!.matrix.length > 0;
  const hasRealVar = Array.isArray(rollingVar) && rollingVar.length > 0;
  const hasData = hasRealSummary && (hasRealLayers || hasRealCorr || hasRealVar);

  // Demo fallback switches — per-slot so partial data still shows.
  const displaySummary: RiskSummary =
    summary && !isEmptyPortfolio ? summary : DEMO_SUMMARY;
  const displayLayers: RiskLayer[] = apiLayers ?? DEMO_LAYERS;
  // Defensive: backend should return labels[] + matrix[][] but a stale
  // cache hit or partial degradation can deliver a non-array `matrix` or
  // mismatched lengths. Guard with Array.isArray before reading length
  // so the page can fall back to DEMO without a root crash.
  const corrMatrixSafe = Array.isArray(corrData?.matrix) ? corrData!.matrix : [];
  const corrLabelsSafe = Array.isArray(corrData?.labels) ? corrData!.labels : [];
  const hasRealCorrPayload = corrMatrixSafe.length > 0;
  const displayCorrLabels: string[] = hasRealCorrPayload
    ? corrLabelsSafe
    : DEMO_TICKERS;
  const displayCorrMatrix: number[][] = hasRealCorrPayload
    ? corrMatrixSafe
    : DEMO_CORR_MATRIX;
  const displayVarPoints = useMemo(() => {
    if (Array.isArray(rollingVar) && rollingVar.length > 0) {
      // Backend `routes/risk.py::rolling_var` returns var_pct as a positive
      // magnitude (e.g. 2.5 for "2.5% 1-day VaR"). The Risk page convention
      // — applied uniformly by the four KPI cards via fmtPct(_, "neg") and
      // by buildDemoVarPoints() (which seeds values around -2.0) — is to
      // render losses as a *signed negative percent* (e.g. "-2.50%"). Without
      // this normalization the sparkline flipped from negative numbers in
      // the demo state to positive numbers the moment real data arrived,
      // contradicting the KPI cards above it. Math.abs guards against any
      // future backend sign flip.
      return rollingVar.map((p) => ({
        date: p.date,
        value: -Math.abs(p.var_pct),
      }));
    }
    return buildDemoVarPoints();
  }, [rollingVar]);
  const displayVarSeries = useMemo(
    () => displayVarPoints.map((p) => p.value),
    [displayVarPoints],
  );

  // Suppress the banner during the initial load — only show it once the
  // endpoints have resolved and we can confirm there is no real data.
  // Auth errors (401) are surfaced immediately because they are not
  // transient and the user should see the "sign in" CTA without delay.
  const showSampleBanner = !hasData && (!anyLoading || isAuthError);

  // Wave 2 dashboard sweep (2026-05-19): intentionally NOT migrated to
  // lib/format.ts fmtPct(). Reason: the "neg" sign mode forces a leading
  // minus on VaR/ES/MaxDD KPIs (loss readings render as "-2.41%" even
  // when the backend payload is the absolute magnitude). Lib fmtPct uses
  // `n > 0 ? "+" : ""` which would surface "+2.41%" for the same payload —
  // a sign flip that would visually misrepresent loss metrics. Local
  // helper retained per feedback_feature_preservation.
  const fmtPct = (v: number | undefined | null, sign: "neg" | "auto" = "auto") => {
    if (v == null || Number.isNaN(v) || !Number.isFinite(v)) return "—";
    const abs = Math.abs(v);
    return sign === "neg" ? `-${abs.toFixed(2)}%` : `${v.toFixed(2)}%`;
  };

  // Generic safe-number formatter for the bare-decimal KPI (corr index)
  // and the correlation heatmap cells. Avoids the page-level crash when
  // a backend regression delivers `null` / missing numeric leaves where
  // the TypeScript shape said `number`.
  // (feedback_bug_fix_patterns: per-metric try-except + stale fallback)
  const fmtNum = (v: number | undefined | null, digits = 2): string => {
    if (v == null || typeof v !== "number" || !Number.isFinite(v)) return "—";
    return v.toFixed(digits);
  };

  return (
    <ErrorBoundary>
      {/* Terminal header */}
      <header className="mb-8 flex items-center justify-between gap-4">
        <span className="pq-ink-kicker">PIVOXQUANT · RISK</span>
        <span className="font-mono text-pq-caption uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          {weekTag()}
        </span>
      </header>

      {/* Title */}
      <div className="mb-8">
        <h1 className="pq-ink-h1">Risk Observation Board</h1>
        <p className="mt-2 font-serif text-sm text-[rgba(245,240,232,0.55)]">
          Portfolio risk indicators — observational, informational only.
        </p>
      </div>

      {/* Sample-preview banner (unauth or empty portfolio) */}
      {showSampleBanner ? (
        <div className="mb-8 flex items-start gap-4 rounded-[2px] border border-[rgba(139,111,71,0.25)] bg-[rgba(139,111,71,0.05)] px-5 py-4">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--pq-bronze)]" />
          <div className="flex-1">
            <div className="pq-ink-kicker mb-1">
              {isAuthError
                ? "Sample preview · log in to see yours"
                : "Sample preview · add positions to populate"}
            </div>
            <p className="text-pq-body leading-relaxed text-[rgba(245,240,232,0.75)]">
              {isAuthError
                ? "You are viewing an illustrative risk board with representative observations. Sign in with Google or Kakao to observe your own holdings."
                : "You are viewing an illustrative risk board. Once you add positions in Portfolio, this page will show observations specific to your book."}
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <a
                href={isAuthError ? "/login" : "/portfolio"}
                className="pq-ink-btn-bronze text-pq-mono-sm"
              >
                {isAuthError ? "Sign in" : "Add a position"}
              </a>
              <a href="/pricing" className="pq-ink-btn-ghost text-pq-mono-sm">
                View plans
              </a>
            </div>
          </div>
        </div>
      ) : null}

      {/* 4 KPI stats */}
      <section className="mb-12 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiStat
          label="Portfolio VaR"
          sub="95% · 1D"
          value={fmtPct(displaySummary.var_1d_pct, "neg")}
          caption="Within historical band."
          tone="neg"
        />
        <KpiStat
          label="Expected Shortfall"
          sub="95%"
          value={fmtPct(displaySummary.es_1d_pct, "neg")}
          caption="Avg loss beyond the VaR cut."
          tone="neg"
        />
        <KpiStat
          label="Max Drawdown"
          sub="90D"
          value={fmtPct(displaySummary.max_dd_90d_pct, "neg")}
          caption="Peak-to-trough trailing window."
          tone="neg"
        />
        <KpiStat
          label="Correlation Index"
          sub="pairwise"
          value={fmtNum(displaySummary.corr_risk_index, 2)}
          caption="Blended pairwise + dispersion."
          tone="bronze"
        />
      </section>

      {/* 7-Layer ladder */}
      <section className="mb-12">
        <div className="mb-5 flex items-start justify-between gap-6">
          <div>
            <div className="pq-ink-label mb-1">Defense · 7 independent lines</div>
            <h2 className="pq-ink-h2">Seven-Layer Risk Defense</h2>
          </div>
          <div className="max-w-md text-pq-mono-sm leading-relaxed text-[rgba(245,240,232,0.6)]">
            Disclaimer: seven independent observations of portfolio risk. Any
            single line turning{" "}
            <span className="text-[var(--pq-bronze)]">elevated</span> is noted —
            this is not a recommendation to take any action.
          </div>
        </div>
        <div className="border-t border-[rgba(245,240,232,0.12)]">
          {displayLayers.map((l) => (
            <div
              key={l.no}
              className="grid grid-cols-[28px_1fr_120px] items-center gap-4 border-b border-[var(--pq-ivory-line-soft)] py-4"
            >
              <span className="font-mono text-pq-mono-sm text-[rgba(245,240,232,0.45)]">
                {String(l.no).padStart(2, "0")}
              </span>
              <div className="min-w-0">
                <div className="font-serif text-pq-lead text-[var(--pq-ivory)]">
                  {l.name}
                </div>
                <div className="mt-0.5 text-pq-mono-sm text-[rgba(245,240,232,0.55)]">
                  {l.metricLabel} · <span className="font-mono text-[var(--pq-bronze)]">{l.metricValue}</span> · {l.observation}
                </div>
              </div>
              <div className="text-right">
                <span className={"pq-ink-pill " + STATUS_PILL[l.status]}>
                  {STATUS_LABEL[l.status]}
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Correlation heatmap */}
      <section className="mb-12">
        <div className="mb-3 flex items-start justify-between gap-6">
          <div>
            <div className="pq-ink-label mb-1">Correlation · 90-day observation</div>
            <h2 className="pq-ink-h2">
              How closely your holdings move together
            </h2>
          </div>
          <div className="max-w-md text-pq-mono-sm leading-relaxed text-[rgba(245,240,232,0.6)]">
            Each cell shows how two holdings have moved together over the last 90
            trading days.
            <span className="mx-1 text-[var(--pq-bronze)]">+1.00</span>
            means they move in lockstep,
            <span className="mx-1 text-[var(--pq-bronze)]">0</span>
            means no relationship,
            <span className="mx-1 text-[var(--pq-bronze)]">−1.00</span>
            means opposite. High numbers everywhere = one bet worn in many
            costumes.
          </div>
        </div>

        {/* Gradient legend */}
        <div className="mb-5 flex items-center gap-3 text-pq-eyebrow uppercase tracking-[0.22em] text-[rgba(245,240,232,0.55)]">
          <span>−1</span>
          <span
            className="h-2 max-w-[220px] flex-1"
            style={{
              background:
                "linear-gradient(to right, rgba(209,136,136,0.7), rgba(245,240,232,0.12), rgba(139,111,71,0.75))",
            }}
          />
          <span>+1</span>
          <span className="ml-auto font-mono tracking-[0.18em] text-[rgba(245,240,232,0.4)]">
            Hover a cell for the pair
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="border-collapse">
            <thead>
              <tr>
                <th className="h-8 w-12 text-pq-kicker uppercase tracking-[0.18em] text-[var(--pq-bronze)]" />
                {displayCorrLabels.map((l) => (
                  <th
                    key={l}
                    className="h-8 w-12 text-pq-kicker font-mono uppercase tracking-[0.12em] text-[var(--pq-bronze)]"
                  >
                    {l}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayCorrMatrix.map((row, i) => (
                <tr key={displayCorrLabels[i] ?? `row-${i}`}>
                  <td className="h-10 w-12 pr-2 text-right font-mono text-pq-kicker uppercase tracking-[0.12em] text-[var(--pq-bronze)]">
                    {displayCorrLabels[i]}
                  </td>
                  {(Array.isArray(row) ? row : []).map((v, j) => {
                    // Guard non-numeric leaves: a malformed backend matrix
                    // (e.g. a `null` cell from a partial 90-day window)
                    // would otherwise crash the whole page when .toFixed
                    // is invoked. We render a neutral em-dash + transparent
                    // background so the table degrades cell-by-cell.
                    const isNum =
                      typeof v === "number" && Number.isFinite(v);
                    const alpha = isNum
                      ? Math.min(1, Math.max(0.05, Math.abs(v)))
                      : 0;
                    // Diverging gradient: positive → Bronze, negative → muted rose
                    const bg = !isNum
                      ? "transparent"
                      : v >= 0
                        ? `rgba(139, 111, 71, ${alpha * 0.55})`
                        : `rgba(209, 136, 136, ${alpha * 0.5})`;
                    const cellText = isNum ? v.toFixed(2) : "—";
                    return (
                      <td
                        key={`${i}-${j}`}
                        title={`${displayCorrLabels[i]} × ${displayCorrLabels[j]}: ${cellText}`}
                        className="h-10 w-12 cursor-default text-center font-mono text-pq-eyebrow tabular-nums text-[var(--pq-ivory)] transition-[outline] hover:outline hover:outline-1 hover:outline-[var(--pq-bronze)]"
                        style={{
                          backgroundColor: bg,
                          border: "0.5px solid var(--pq-ivory-line-soft)",
                        }}
                      >
                        {cellText}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Rolling VaR chart */}
      <section className="mb-12">
        <div className="mb-5 flex items-start justify-between gap-6">
          <div>
            <div className="pq-ink-label mb-1">Value at Risk · 30-day trace</div>
            <h2 className="pq-ink-h2">Rolling 30-day VaR</h2>
          </div>
          <div className="max-w-md text-pq-mono-sm leading-relaxed text-[rgba(245,240,232,0.6)]">
            Daily 1-day 95% VaR observed over the last 30 sessions. The line
            shows the worst observed loss under each day&rsquo;s portfolio — a
            moving picture of downside, not a forecast.
          </div>
        </div>
        <RollingVarInk series={displayVarSeries} points={displayVarPoints} />
      </section>

      {/* Methodology rail */}
      <section className="mb-12">
        <h2 className="pq-ink-h2 mb-4">Methodology Notes</h2>
        <ul className="space-y-2 border-t border-[rgba(245,240,232,0.12)] pt-4 text-pq-caption text-[rgba(245,240,232,0.7)]">
          <li className="flex gap-3">
            <span className="font-mono text-[var(--pq-bronze)]">01</span>
            <span><em className="font-serif not- text-[var(--pq-ivory)]">VaR (1-day, 95%)</em> — historical percentile on the 90-day return window, weighted by position size.</span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-[var(--pq-bronze)]">02</span>
            <span><em className="font-serif not- text-[var(--pq-ivory)]">Expected Shortfall</em> — mean of returns below the VaR cutoff (5% left tail).</span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-[var(--pq-bronze)]">03</span>
            <span><em className="font-serif not- text-[var(--pq-ivory)]">Max Drawdown (90D)</em> — peak-to-trough of the portfolio equity curve over the trailing window.</span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-[var(--pq-bronze)]">04</span>
            <span><em className="font-serif not- text-[var(--pq-ivory)]">Correlation Index</em> — average pairwise correlation across holdings on the last 20 sessions.</span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-[var(--pq-bronze)]">05</span>
            <span><em className="font-serif not- text-[var(--pq-ivory)]">Seven-Layer Ladder</em> — soft-limit observations across VaR, correlation, VIX, tail, daily loss, concentration, and cash buffer.</span>
          </li>
        </ul>
      </section>

      {/* Legal disclaimer mounted by (dashboard)/layout.tsx — do not re-mount. */}
    </ErrorBoundary>
  );
}

/* ── KPI stat cell ── */

function KpiStat({
  label,
  sub,
  value,
  caption,
  tone,
}: {
  label: string;
  sub?: string;
  value: string;
  caption: string;
  tone?: "neg" | "bronze" | "ivory";
}) {
  const valueCls =
    tone === "bronze"
      ? "text-[var(--pq-bronze)]"
      : tone === "neg"
        ? "text-[#d18888]"
        : "text-[var(--pq-ivory)]";
  return (
    <div className="pq-ink-stat">
      <div className="flex items-baseline justify-between">
        <span className="pq-ink-label">{label}</span>
        {sub ? (
          <span className="font-mono text-pq-kicker text-[rgba(245,240,232,0.4)]">
            {sub}
          </span>
        ) : null}
      </div>
      <div className={"pq-ink-num mt-2 " + valueCls}>{value}</div>
      <div className="pq-ink-caption mt-1">{caption}</div>
    </div>
  );
}

/* ── Rolling VaR — interactive hover chart ── */

function RollingVarInk({
  series,
  points,
}: {
  series: number[];
  points: { date: string; value: number }[];
}) {
  if (!Array.isArray(series) || series.length < 2) {
    return <div className="pq-ink-empty">—</div>;
  }
  // Filter non-finite leaves before reducing — guards against an
  // upstream serializer that flips a numeric leaf to null and would
  // otherwise produce NaN bounds that surface as "NaN%" in the legend.
  const finite = series.filter((n): n is number => Number.isFinite(n));
  const hi = finite.length > 0 ? Math.max(...finite) : 0;
  const lo = finite.length > 0 ? Math.min(...finite) : 0;

  return (
    <div className="rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-4">
      <InteractiveLineChart
        points={points}
        height={180}
        valueFormatter={(v) => `${v.toFixed(2)}%`}
        dateFormatter={(d) => {
          const parsed = new Date(d);
          return isNaN(parsed.getTime())
            ? d
            : parsed.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              });
        }}
        yLabel="1-day 95% VaR (observed)"
        ariaLabel="Rolling 30-day VaR"
      />
      <div className="mt-2 flex justify-between font-mono text-pq-eyebrow text-[rgba(245,240,232,0.45)]">
        <span>max {hi.toFixed(2)}%</span>
        <span>min {lo.toFixed(2)}%</span>
      </div>
    </div>
  );
}
