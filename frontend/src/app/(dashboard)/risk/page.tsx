"use client";

/**
 * Risk Observation Board — editorial flat, Vantablack ink + Bronze accent.
 *
 * Sections:
 *  1. Serif italic heading "Risk Observation Board"
 *  2. 4 KPI cards (editorial flat): VaR / ES / Max DD / Corr Risk Index
 *  3. Seven-Layer Risk Defense ladder
 *  4. Correlation heatmap (up to 10x10)
 *  5. Rolling 30-day VaR line chart
 *  6. DisclaimerBanner
 *
 * Wired to /api/risk/* via SWR (2026-04-22). Mock structure renders on
 * loading/error so the page is never blank. Neutral observation language
 * only ("observed", "within band", "above soft limit").
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
import {
  SevenLayerPanel,
  SEVEN_LAYER_MOCK,
  type RiskLayer,
  type LayerStatus,
} from "@/components/risk/seven-layer-panel";
import { CorrelationHeatmap } from "@/components/risk/correlation-heatmap";
import { RollingVarChart } from "@/components/risk/rolling-var-chart";

/* ── SWR fetcher ── */
const fetcher = <T,>(url: string) => apiFetch<T>(url);

/* ── Backend payload types ── */
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

/* ── Top KPI card ── */

interface KpiCardProps {
  label: string;
  value: string;
  caption: string;
  tone?: "ink" | "bronze" | "faint-red";
}

function KpiCard({ label, value, caption, tone = "ink" }: KpiCardProps) {
  const valueCls =
    tone === "bronze"
      ? "text-[var(--pq-bronze,#8B6F47)]"
      : tone === "faint-red"
        ? "text-[#B04A3A]"
        : "text-slate-900";
  return (
    <div className="pt-4">
      <div className="border-t border-slate-200 pt-3">
        <p className="text-[10px] uppercase tracking-widest text-slate-400">
          {label}
        </p>
        <p
          className={`mt-2 font-serif italic text-3xl font-bold tabular-nums ${valueCls}`}
        >
          {value}
        </p>
        <p className="mt-1 text-[11px] leading-snug text-slate-500">
          {caption}
        </p>
      </div>
    </div>
  );
}

function mapStatus(s: "GREEN" | "YELLOW" | "RED"): LayerStatus {
  return s === "GREEN" ? "green" : s === "YELLOW" ? "yellow" : "red";
}

export default function RiskPage() {
  const { data: summary } = useSWR<RiskSummary>(RISK_SUMMARY, fetcher);
  const { data: layersData } = useSWR<LayersResponse | BackendLayer[]>(
    RISK_LAYERS,
    fetcher,
  );
  // correlation + rolling-var are consumed by their own components (which
  // still render mock). We fetch them here so the network panel shows the
  // calls and so future components can pick up the cached SWR entries.
  useSWR<CorrelationPayload>(RISK_CORRELATION, fetcher);
  useSWR<RollingVarPoint[]>(RISK_ROLLING_VAR, fetcher);

  // Normalize the API payload → RiskLayer[] for SevenLayerPanel.
  const layers: RiskLayer[] = useMemo(() => {
    const raw = Array.isArray(layersData)
      ? layersData
      : layersData?.layers ?? null;
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

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-4xl space-y-8 px-1">
        {/* ── Header ── */}
        <header>
          <p className="text-[11px] uppercase tracking-widest text-[var(--pq-bronze,#8B6F47)]">
            Observation
          </p>
          <h1 className="mt-1 font-serif italic text-4xl font-bold text-slate-900">
            Risk Observation Board
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Portfolio risk indicators — observational, informational only.
          </p>
        </header>

        {/* ── 4 KPI cards (editorial flat) ── */}
        <section
          aria-label="Key risk indicators"
          className="grid grid-cols-2 gap-x-6 sm:grid-cols-4"
        >
          <KpiCard
            label="Portfolio VaR (95%, 1D)"
            value={summary ? fmtPct(summary.var_1d_pct, "neg") : "—"}
            caption="1-day historical VaR. Within band."
            tone="faint-red"
          />
          <KpiCard
            label="Expected Shortfall (95%)"
            value={summary ? fmtPct(summary.es_1d_pct, "neg") : "—"}
            caption="Average loss beyond the VaR cut."
            tone="faint-red"
          />
          <KpiCard
            label="Max Drawdown (90D)"
            value={summary ? fmtPct(summary.max_dd_90d_pct, "neg") : "—"}
            caption="Peak-to-trough over the trailing window."
            tone="faint-red"
          />
          <KpiCard
            label="Correlation Risk Index"
            value={
              summary ? summary.corr_risk_index.toFixed(2) : "—"
            }
            caption="Blended pairwise + dispersion score."
            tone="bronze"
          />
        </section>

        {/* ── 7-Layer Risk Defense ladder ── */}
        <SevenLayerPanel layers={layers} />

        {/* ── Correlation heatmap (uses its own mock structure when empty) ── */}
        <CorrelationHeatmap />

        {/* ── Rolling 30-day VaR ── */}
        <RollingVarChart />

        {/* ── Disclaimer ── */}
        <div className="pt-4">
          <DisclaimerBanner type="signal" />
        </div>
      </div>
    </ErrorBoundary>
  );
}
