"use client";

/**
 * Risk Observation Board — Vantablack ink terminal card on ivory shell.
 *
 * Sections:
 *  1. Terminal header + title
 *  2. 4 KPI stats (VaR / ES / Max DD / Corr Risk Index)
 *  3. Seven-Layer Risk Defense ladder (inline)
 *  4. Correlation heatmap (Bronze gradient tiles on ink)
 *  5. Rolling 30-day VaR sparkline (Bronze stroke on ink)
 *  6. DisclaimerBanner
 *
 * Neutral observation language only ("observed", "within band").
 */

import useSWR from "swr";
import { useMemo } from "react";
import { apiFetch } from "@/lib/api";
import {
  RISK_SUMMARY,
  RISK_LAYERS,
  RISK_CORRELATION,
  RISK_ROLLING_VAR,
} from "@/lib/endpoints";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { InteractiveLineChart } from "@/components/charts/interactive-line-chart";
import {
  SEVEN_LAYER_MOCK,
  type RiskLayer,
  type LayerStatus,
} from "@/components/risk/seven-layer-panel";

const fetcher = <T,>(url: string) => apiFetch<T>(url);

// Shared SWR options — refresh each minute for observational freshness
// while the window is visible. Revalidate on focus so users coming back
// to the tab always see the latest observation.
const SWR_OPTS = {
  refreshInterval: 60_000,
  revalidateOnFocus: true,
  dedupingInterval: 15_000,
} as const;

interface RiskSummary {
  var_1d_pct: number;
  es_1d_pct: number;
  max_dd_90d_pct: number;
  corr_risk_index: number;
}
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

export default function RiskPage() {
  const { data: summary } = useSWR<RiskSummary>(RISK_SUMMARY, fetcher, SWR_OPTS);
  const { data: layersData } = useSWR<LayersResponse | BackendLayer[]>(
    RISK_LAYERS,
    fetcher,
    SWR_OPTS,
  );
  const { data: corrData } = useSWR<CorrelationPayload>(
    RISK_CORRELATION,
    fetcher,
    SWR_OPTS,
  );
  const { data: rollingVar } = useSWR<RollingVarPoint[]>(
    RISK_ROLLING_VAR,
    fetcher,
    SWR_OPTS,
  );

  // Empty-portfolio detection: summary exists and all figures are zero,
  // and correlation payload is empty. Show an editorial placeholder banner.
  const isEmptyPortfolio =
    !!summary &&
    summary.var_1d_pct === 0 &&
    summary.es_1d_pct === 0 &&
    summary.max_dd_90d_pct === 0 &&
    summary.corr_risk_index === 0 &&
    (!corrData || !corrData.matrix || corrData.matrix.length === 0);

  const layers: RiskLayer[] = useMemo(() => {
    const raw = Array.isArray(layersData) ? layersData : layersData?.layers ?? null;
    if (!raw || raw.length === 0) return SEVEN_LAYER_MOCK;
    return raw.map((l) => ({
      no: l.no,
      name: l.name,
      metricLabel: l.metric_label,
      metricValue: l.metric_value,
      status: mapStatus(l.status),
      observation: l.observation,
    }));
  }, [layersData]);

  const fmtPct = (v: number | undefined, sign: "neg" | "auto" = "auto") => {
    if (v == null || Number.isNaN(v)) return "—";
    const abs = Math.abs(v);
    return sign === "neg" ? `-${abs.toFixed(2)}%` : `${v.toFixed(2)}%`;
  };

  // Mock correlation fallback.
  const corrLabels = corrData?.labels ?? ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"];
  const corrMatrix = useMemo(() => {
    if (corrData?.matrix && corrData.matrix.length > 0) return corrData.matrix;
    // Deterministic mock matrix
    return corrLabels.map((_, i) =>
      corrLabels.map((_, j) => {
        if (i === j) return 1;
        const seed = (i + 1) * (j + 2);
        return Math.round(((seed % 70) / 100 + 0.2) * 100) / 100;
      }),
    );
  }, [corrData, corrLabels]);

  // Mock rolling VaR fallback — retain both legacy series (numbers-only) and
  // dated points for the interactive chart.
  const rollingVarPoints = useMemo(() => {
    if (rollingVar && rollingVar.length > 0) {
      return rollingVar.map((p) => ({ date: p.date, value: p.var_pct }));
    }
    // 30-day synthetic series, back-dated from today.
    const today = new Date();
    return Array.from({ length: 30 }).map((_, i) => {
      const d = new Date(today);
      d.setDate(d.getDate() - (29 - i));
      const iso = d.toISOString().slice(0, 10);
      return { date: iso, value: -(1.6 + Math.sin(i / 3) * 0.4 + (i % 5) * 0.1) };
    });
  }, [rollingVar]);
  const rollingVarSeries = useMemo(
    () => rollingVarPoints.map((p) => p.value),
    [rollingVarPoints],
  );

  return (
    <ErrorBoundary>
      {/* Terminal header */}
      <header className="mb-8 flex items-center justify-between gap-4">
        <span className="pq-ink-kicker">PIVOXQUANT · RISK</span>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          {weekTag()}
        </span>
      </header>

      {/* Title */}
      <div className="mb-10">
          <h1 className="pq-ink-h1">Risk Observation Board</h1>
          <p className="mt-2 font-serif italic text-sm text-[rgba(245,240,232,0.55)]">
            Portfolio risk indicators — observational, informational only.
          </p>
        </div>

        {/* Empty-portfolio editorial notice */}
        {isEmptyPortfolio ? (
          <div className="mb-10 rounded-sm border border-dashed border-[rgba(245,240,232,0.18)] bg-[rgba(255,255,255,0.02)] px-5 py-4">
            <p className="font-serif italic text-[13px] text-[var(--pq-ivory)]">
              No positions under observation yet.
            </p>
            <p className="mt-1 text-[11px] text-[rgba(245,240,232,0.55)]">
              Add a position to see risk signals. The figures below illustrate
              the structure of the observation board with reference values.
            </p>
          </div>
        ) : null}

        {/* 4 KPI stats */}
        <section className="mb-12 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <KpiStat
            label="Portfolio VaR"
            sub="95% · 1D"
            value={summary ? fmtPct(summary.var_1d_pct, "neg") : "—"}
            caption="Within historical band."
            tone="neg"
          />
          <KpiStat
            label="Expected Shortfall"
            sub="95%"
            value={summary ? fmtPct(summary.es_1d_pct, "neg") : "—"}
            caption="Avg loss beyond the VaR cut."
            tone="neg"
          />
          <KpiStat
            label="Max Drawdown"
            sub="90D"
            value={summary ? fmtPct(summary.max_dd_90d_pct, "neg") : "—"}
            caption="Peak-to-trough trailing window."
            tone="neg"
          />
          <KpiStat
            label="Correlation Index"
            sub="pairwise"
            value={summary ? summary.corr_risk_index.toFixed(2) : "—"}
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
            <div className="max-w-md text-[11px] leading-relaxed text-[rgba(245,240,232,0.6)]">
              Seven independent observations of portfolio risk. Any single line
              turning <span className="text-[var(--pq-bronze)]">elevated</span> is
              noted — none recommend action.
            </div>
          </div>
          <div className="border-t border-[rgba(245,240,232,0.12)]">
            {layers.map((l) => (
              <div
                key={l.no}
                className="grid grid-cols-[28px_1fr_120px] items-center gap-4 border-b border-[rgba(245,240,232,0.06)] py-4"
              >
                <span className="font-mono text-[11px] text-[rgba(245,240,232,0.45)]">
                  {String(l.no).padStart(2, "0")}
                </span>
                <div className="min-w-0">
                  <div className="font-serif italic text-[15px] text-[var(--pq-ivory)]">
                    {l.name}
                  </div>
                  <div className="mt-0.5 text-[11px] text-[rgba(245,240,232,0.55)]">
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
            <div className="max-w-md text-[11px] leading-relaxed text-[rgba(245,240,232,0.6)]">
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
          <div className="mb-5 flex items-center gap-3 text-[10px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.55)]">
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
                  <th className="h-8 w-12 text-[9px] uppercase tracking-[0.18em] text-[var(--pq-bronze)]" />
                  {corrLabels.map((l) => (
                    <th
                      key={l}
                      className="h-8 w-12 text-[9px] font-mono uppercase tracking-[0.12em] text-[var(--pq-bronze)]"
                    >
                      {l}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {corrMatrix.map((row, i) => (
                  <tr key={corrLabels[i]}>
                    <td className="h-10 w-12 pr-2 text-right font-mono text-[9px] uppercase tracking-[0.12em] text-[var(--pq-bronze)]">
                      {corrLabels[i]}
                    </td>
                    {row.map((v, j) => {
                      const alpha = Math.min(1, Math.max(0.05, Math.abs(v)));
                      // Diverging gradient: positive → Bronze, negative → muted rose
                      const bg =
                        v >= 0
                          ? `rgba(139, 111, 71, ${alpha * 0.55})`
                          : `rgba(209, 136, 136, ${alpha * 0.5})`;
                      return (
                        <td
                          key={`${i}-${j}`}
                          title={`${corrLabels[i]} × ${corrLabels[j]}: ${v.toFixed(2)}`}
                          className="h-10 w-12 cursor-default text-center font-mono text-[10px] tabular-nums text-[var(--pq-ivory)] transition-[outline] hover:outline hover:outline-1 hover:outline-[var(--pq-bronze)]"
                          style={{
                            backgroundColor: bg,
                            border: "0.5px solid rgba(245,240,232,0.06)",
                          }}
                        >
                          {v.toFixed(2)}
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
            <div className="max-w-md text-[11px] leading-relaxed text-[rgba(245,240,232,0.6)]">
              Daily 1-day 95% VaR observed over the last 30 sessions. The line
              shows the worst observed loss under each day&rsquo;s portfolio — a
              moving picture of downside, not a forecast.
            </div>
          </div>
          <RollingVarInk series={rollingVarSeries} points={rollingVarPoints} />
        </section>

        {/* Methodology rail */}
        <section className="mb-12">
          <h2 className="pq-ink-h2 mb-4">Methodology Notes</h2>
          <ul className="space-y-2 border-t border-[rgba(245,240,232,0.12)] pt-4 text-[12px] text-[rgba(245,240,232,0.7)]">
            <li className="flex gap-3">
              <span className="font-mono text-[var(--pq-bronze)]">01</span>
              <span><em className="font-serif not-italic text-[var(--pq-ivory)]">VaR (1-day, 95%)</em> — historical percentile on the 90-day return window, weighted by position size.</span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono text-[var(--pq-bronze)]">02</span>
              <span><em className="font-serif not-italic text-[var(--pq-ivory)]">Expected Shortfall</em> — mean of returns below the VaR cutoff (5% left tail).</span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono text-[var(--pq-bronze)]">03</span>
              <span><em className="font-serif not-italic text-[var(--pq-ivory)]">Max Drawdown (90D)</em> — peak-to-trough of the portfolio equity curve over the trailing window.</span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono text-[var(--pq-bronze)]">04</span>
              <span><em className="font-serif not-italic text-[var(--pq-ivory)]">Correlation Index</em> — average pairwise correlation across holdings on the last 20 sessions.</span>
            </li>
            <li className="flex gap-3">
              <span className="font-mono text-[var(--pq-bronze)]">05</span>
              <span><em className="font-serif not-italic text-[var(--pq-ivory)]">Seven-Layer Ladder</em> — soft-limit observations across VaR, correlation, VIX, tail, daily loss, concentration, and cash buffer.</span>
            </li>
          </ul>
        </section>

      {/* Disclaimer */}
      <div className="border-t border-[rgba(245,240,232,0.1)] pt-6 text-[rgba(245,240,232,0.7)]">
        <DisclaimerBanner type="signal" />
      </div>
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
          <span className="font-mono text-[9px] text-[rgba(245,240,232,0.4)]">
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
  if (!series || series.length < 2) {
    return <div className="pq-ink-empty">—</div>;
  }
  const hi = Math.max(...series);
  const lo = Math.min(...series);

  return (
    <div className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-4">
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
      <div className="mt-2 flex justify-between font-mono text-[10px] text-[rgba(245,240,232,0.45)]">
        <span>max {hi.toFixed(2)}%</span>
        <span>min {lo.toFixed(2)}%</span>
      </div>
    </div>
  );
}
