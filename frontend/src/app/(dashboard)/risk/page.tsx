"use client";

/**
 * Risk Observation Board — editorial flat, Vantablack ink + Bronze accent.
 *
 * Sections:
 *  1. Serif italic heading "Risk Observation Board"
 *  2. 4 KPI cards (editorial flat): VaR / ES / Max DD / Corr Risk Index
 *  3. Seven-Layer Risk Defense ladder (core)
 *  4. Correlation heatmap (10x10 mock)
 *  5. Rolling 30-day VaR line chart
 *  6. DisclaimerBanner
 *
 * All language is neutral ("observation / noted / informational").
 * All UI text uses POSITIVE / NEGATIVE / NEUTRAL phrasing only.
 */

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { SevenLayerPanel } from "@/components/risk/seven-layer-panel";
import { CorrelationHeatmap } from "@/components/risk/correlation-heatmap";
import { RollingVarChart } from "@/components/risk/rolling-var-chart";

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

export default function RiskPage() {
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
            value="-2.14%"
            caption="1-day historical VaR. Within band."
            tone="faint-red"
          />
          <KpiCard
            label="Expected Shortfall (95%)"
            value="-3.42%"
            caption="Average loss beyond the VaR cut."
            tone="faint-red"
          />
          <KpiCard
            label="Max Drawdown (90D)"
            value="-8.7%"
            caption="Peak-to-trough over the trailing window."
            tone="faint-red"
          />
          <KpiCard
            label="Correlation Risk Index"
            value="0.58"
            caption="Blended pairwise + dispersion score."
            tone="bronze"
          />
        </section>

        {/* ── 7-Layer Risk Defense ladder ── */}
        <SevenLayerPanel />

        {/* ── Correlation heatmap ── */}
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
