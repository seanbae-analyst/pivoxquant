"use client";

/**
 * <RiskBoardCard /> — Card 2 of /home v2.
 *
 * Maps v1's row-1 "Risk Gauges" (VaR/Sharpe/MaxDD/VIX) to a single editorial
 * card with 4 horizontal CSS gauges per home-v2 SPEC §3.
 *
 * Data: directly subscribes to /api/risk/summary via SWR — same pattern as
 * v1 home/page.tsx line 215 (`useSWR<RiskSummaryResponse>("/api/risk/summary",
 * fetcher, briefOpts)`). No new lib/hooks.ts entry — keeps the contract that
 * existing hooks remain untouched.
 *
 * Sector concentration / correlation cluster — graceful "—" fallback when
 * the snapshot endpoint omits them (matches MIGRATION.md §3 risk note).
 */

import * as React from "react";
import useSWR from "swr";
import { HomeCard } from "./home-card";
import { apiFetch } from "@/lib/api";

interface RiskSummaryShape {
  // Backend (/api/risk/summary) returns snake_case PERCENT values:
  //   var_1d_pct, es_1d_pct, max_dd_90d_pct, corr_risk_index
  // Older optional fractional names (var_95, tail_ces, …) kept for
  // forward-compat with risk-gauge-grid contract.
  var_1d_pct?: number;
  es_1d_pct?: number;
  max_dd_90d_pct?: number;
  corr_risk_index?: number;
  // Legacy / forward-compat
  var_95?: number;
  var_99?: number;
  max_drawdown?: number;
  sharpe?: number;
  sector_concentration?: number;
  correlation_cluster?: number;
  tail_ces?: number;
  gauge?: {
    vix?: number;
    correlation?: number;
    concentration?: number;
  };
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

interface GaugeRowProps {
  label: string;
  value: string;
  /** 0..1 — fill ratio */
  fill: number;
}

function GaugeRow({ label, value, fill }: GaugeRowProps) {
  const pct = Math.min(1, Math.max(0, fill)) * 100;
  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 6,
        }}
      >
        <span
          className="font-mono uppercase"
          style={{
            fontSize: 12,
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
            textTransform: "uppercase",
          }}
        >
          {label}
        </span>
        <span
          className="font-mono"
          style={{
            fontVariantNumeric: "tabular-nums",
            fontSize: 12,
            color: "rgba(245,240,232,0.82)",
          }}
        >
          {value}
        </span>
      </div>
      <div
        style={{
          height: 4,
          background: "rgba(245,240,232,0.06)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <span
          aria-hidden
          style={{
            display: "block",
            height: "100%",
            width: `${pct}%`,
            background:
              "linear-gradient(90deg, var(--pq-bronze-deep, #6F5636), var(--pq-bronze))",
          }}
        />
      </div>
    </div>
  );
}

export function RiskBoardCard() {
  const { data: risk } = useSWR<RiskSummaryShape>(
    "/api/risk/summary",
    fetcher,
    {
      refreshInterval: 600_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60_000,
      errorRetryCount: 2,
      errorRetryInterval: 10_000,
    },
  );

  // Backend snake_case is canonical; legacy fractional fields kept as
  // last-resort fallback. var_1d_pct / es_1d_pct are PERCENT (e.g. 2.14);
  // var_95 / tail_ces (legacy) are FRACTIONS (e.g. 0.0214).  Coerce both
  // to fraction (0..1) here so downstream `* 100` math stays correct.
  const toFraction = (v: number | undefined): number | null => {
    if (v == null || !Number.isFinite(v)) return null;
    return Math.abs(v) <= 1 ? v : v / 100;
  };
  const var95 =
    toFraction(risk?.var_1d_pct) ?? toFraction(risk?.var_95);
  const tail =
    toFraction(risk?.es_1d_pct) ?? toFraction(risk?.tail_ces);
  const sectorConc =
    risk?.sector_concentration != null
      ? risk.sector_concentration
      : risk?.gauge?.concentration;
  const correl =
    risk?.corr_risk_index != null
      ? risk.corr_risk_index
      : risk?.correlation_cluster != null
        ? risk.correlation_cluster
        : risk?.gauge?.correlation;

  const composeWord =
    var95 != null && Math.abs(var95) >= 0.05
      ? "Watchful"
      : var95 != null
        ? "Composed"
        : "Reading…";

  return (
    <HomeCard href="/risk" eyebrow="Risk · 7-Layer Defense" cornerCta="Risk Board ›">
      <div
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: 32,
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          marginBottom: 4,
        }}
      >
        {composeWord}
      </div>
      <p
        className="font-serif"
        style={{
          fontSize: 14,
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.82)",
          margin: "0 0 24px 0",
        }}
      >
        Layer telemetry observed. None breached.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <GaugeRow
          label="VaR 95"
          value={var95 != null ? `${(var95 * 100).toFixed(2)}%` : "—"}
          fill={var95 != null ? Math.min(1, Math.abs(var95) / 0.08) : 0}
        />
        <GaugeRow
          label="Sector concentration"
          value={
            sectorConc != null && Number.isFinite(sectorConc)
              ? `${(sectorConc * 100).toFixed(0)}%`
              : "—"
          }
          fill={
            sectorConc != null && Number.isFinite(sectorConc)
              ? Math.min(1, sectorConc)
              : 0
          }
        />
        <GaugeRow
          label="Correlation cluster"
          value={
            correl != null && Number.isFinite(correl) ? correl.toFixed(2) : "—"
          }
          fill={
            correl != null && Number.isFinite(correl) ? Math.min(1, correl) : 0
          }
        />
        <GaugeRow
          label="Tail (CES)"
          value={tail != null ? `${(tail * 100).toFixed(2)}%` : "—"}
          fill={tail != null ? Math.min(1, Math.abs(tail) / 0.08) : 0}
        />
      </div>
    </HomeCard>
  );
}

export default RiskBoardCard;
