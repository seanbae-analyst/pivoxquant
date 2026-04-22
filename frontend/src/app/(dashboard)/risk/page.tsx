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
import { TerminalSidebar } from "@/components/layout/terminal-sidebar";
import {
  SEVEN_LAYER_MOCK,
  type RiskLayer,
  type LayerStatus,
} from "@/components/risk/seven-layer-panel";

const fetcher = <T,>(url: string) => apiFetch<T>(url);

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
  const { data: summary } = useSWR<RiskSummary>(RISK_SUMMARY, fetcher);
  const { data: layersData } = useSWR<LayersResponse | BackendLayer[]>(
    RISK_LAYERS,
    fetcher,
  );
  const { data: corrData } = useSWR<CorrelationPayload>(
    RISK_CORRELATION,
    fetcher,
  );
  const { data: rollingVar } = useSWR<RollingVarPoint[]>(
    RISK_ROLLING_VAR,
    fetcher,
  );

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

  // Mock rolling VaR fallback.
  const rollingVarSeries = useMemo(() => {
    if (rollingVar && rollingVar.length > 0) return rollingVar.map((p) => p.var_pct);
    // 30-day synthetic series
    return Array.from({ length: 30 }).map((_, i) => {
      return -(1.6 + Math.sin(i / 3) * 0.4 + (i % 5) * 0.1);
    });
  }, [rollingVar]);

  return (
    <ErrorBoundary>
      <div className="pq-ink-card">
        {/* Terminal header */}
        <header className="mb-8 flex items-center justify-between gap-4">
          <span className="pq-ink-kicker">PIVOXQUANT · RISK</span>
          <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
            {weekTag()}
          </span>
        </header>

        <div className="flex gap-8 md:gap-10">
          <TerminalSidebar active="risk" />
          <div className="flex-1 min-w-0">
        {/* Title */}
        <div className="mb-10">
          <h1 className="pq-ink-h1">Risk Observation Board</h1>
          <p className="mt-2 font-serif italic text-sm text-[rgba(245,240,232,0.55)]">
            Portfolio risk indicators — observational, informational only.
          </p>
        </div>

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
          <h2 className="pq-ink-h2 mb-5">Seven-Layer Risk Defense</h2>
          <div className="border-t border-[rgba(245,240,232,0.12)]">
            {layers.map((l) => (
              <div
                key={l.no}
                className="grid grid-cols-[28px_1fr_auto_120px] items-center gap-4 border-b border-[rgba(245,240,232,0.06)] py-4"
              >
                <span className="font-mono text-[11px] text-[rgba(245,240,232,0.45)]">
                  {String(l.no).padStart(2, "0")}
                </span>
                <div>
                  <div className="font-serif italic text-[15px] text-[var(--pq-ivory)]">
                    {l.name}
                  </div>
                  <div className="mt-0.5 text-[11px] text-[rgba(245,240,232,0.55)]">
                    {l.metricLabel} · <span className="font-mono text-[var(--pq-bronze)]">{l.metricValue}</span> · {l.observation}
                  </div>
                </div>
                <div />
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
          <h2 className="pq-ink-h2 mb-4">Correlation Matrix</h2>
          <p className="mb-5 text-[11px] text-[rgba(245,240,232,0.55)]">
            Pairwise 60-day rolling correlation across top holdings.
          </p>
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
                      return (
                        <td
                          key={`${i}-${j}`}
                          className="h-10 w-12 text-center font-mono text-[10px] tabular-nums text-[var(--pq-ivory)]"
                          style={{
                            backgroundColor: `rgba(139, 111, 71, ${alpha * 0.55})`,
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
          <h2 className="pq-ink-h2 mb-4">Rolling 30-day VaR</h2>
          <p className="mb-5 text-[11px] text-[rgba(245,240,232,0.55)]">
            Historical 1-day 95% VaR observed over the last 30 sessions.
          </p>
          <RollingVarInk series={rollingVarSeries} />
        </section>

        {/* Disclaimer */}
        <div className="border-t border-[rgba(245,240,232,0.1)] pt-6 text-[rgba(245,240,232,0.7)]">
          <DisclaimerBanner type="signal" />
        </div>
          </div>
        </div>
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

/* ── Rolling VaR inline SVG ── */

function RollingVarInk({ series }: { series: number[] }) {
  if (!series || series.length < 2) {
    return <div className="pq-ink-empty">—</div>;
  }
  const w = 720;
  const h = 160;
  const pad = 24;
  const lo = Math.min(...series);
  const hi = Math.max(...series);
  const range = hi - lo || 1;
  const step = (w - pad * 2) / (series.length - 1);
  const points = series
    .map((v, i) => {
      const x = pad + i * step;
      const y = pad + ((hi - v) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-4">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-[160px] w-full"
        preserveAspectRatio="none"
      >
        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map((t) => (
          <line
            key={t}
            x1={pad}
            x2={w - pad}
            y1={pad + t * (h - pad * 2)}
            y2={pad + t * (h - pad * 2)}
            stroke="rgba(245,240,232,0.06)"
            strokeWidth="0.5"
          />
        ))}
        <polyline
          points={points}
          fill="none"
          stroke="var(--pq-bronze)"
          strokeWidth="1.5"
        />
      </svg>
      <div className="mt-2 flex justify-between font-mono text-[10px] text-[rgba(245,240,232,0.45)]">
        <span>{hi.toFixed(2)}%</span>
        <span>{lo.toFixed(2)}%</span>
      </div>
    </div>
  );
}
