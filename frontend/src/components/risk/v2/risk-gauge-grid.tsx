"use client";

/**
 * <RiskGaugeGrid /> — Block 1 of /risk v2.
 *
 * Four big-gauge cards (VaR · Concentration HHI · Correlation avg ·
 * Component ES) arranged 2×2 with a 12px gutter. Linear gauge bar (NOT
 * circular) keeps the same primitive used in home-v2 .gauge.
 *
 * Posture labels are legal-safe (POSITIVE / NEGATIVE / NEUTRAL) — color
 * is always paired with the text label per a11y §11 of SPEC.
 */

import * as React from "react";
import type { RiskSummaryV2, RiskLayerV2, RiskLayerStatus } from "@/lib/hooks";

// Display posture — adds a PENDING state on top of the backend's three so a
// gauge with no observed data can't show a false "POSITIVE" safety signal
// (audit FINDING-018).
type DisplayPosture = RiskLayerStatus | "PENDING";

interface BigGaugeProps {
  eyebrow: string;
  value: string;
  unit?: string;
  range: string;
  gaugePct: number;
  marks: [string, string, string];
  posture: RiskLayerStatus;
}

// §7 three-color system (audit FINDING-019): POSITIVE means "evaluated &
// passing" — it reads NEUTRAL-bronze, NOT green/red. NEGATIVE is the only
// alarm hue (carmine). NEUTRAL / PENDING is muted ivory. Tokens defined in
// globals.css; the literal fallbacks match them so SSR never flashes the
// old Tailwind red/blue.
function postureColor(p: DisplayPosture): string {
  if (p === "POSITIVE") return "var(--pq-positive, #b8956a)";
  if (p === "NEGATIVE") return "var(--pq-negative, #d18888)";
  return "var(--pq-neutral, rgba(245,240,232,0.55))";
}

function BigGaugeCard({
  eyebrow,
  value,
  unit,
  range,
  gaugePct,
  marks,
  posture,
}: BigGaugeProps) {
  const pct = Math.min(100, Math.max(0, gaugePct));
  // FINDING-018: a "—" value means the gauge has no observed data — the
  // posture chip must NOT claim POSITIVE (false safety signal). Show PENDING.
  const displayPosture: DisplayPosture = value === "—" ? "PENDING" : posture;
  return (
    <div
      className="pq-card"
      style={{
        background: "var(--pq-ink-card, rgba(255,255,255,0.02))",
        border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
        borderRadius: 4,
        padding: 28,
        minHeight: 240,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
      role="group"
      aria-label={`${eyebrow}: ${value}${unit ?? ""}, ${displayPosture}`}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
        }}
      >
        {eyebrow}
      </div>

      <div
        style={{
          fontVariantNumeric: "tabular-nums",
          fontSize: "var(--pq-text-gauge)",
          color: "var(--pq-ivory)",
          lineHeight: 1,
          letterSpacing: "-0.01em",
        }}
      className="font-mono" >
        {value}
        {unit ? (
          <span
            style={{
              fontSize: "var(--pq-text-quote)",
              color: "rgba(245,240,232,0.55)",
              marginLeft: 2,
            }}
          >
            {unit}
          </span>
        ) : null}
      </div>

      <div
        className="font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.04em",
          color: "rgba(245,240,232,0.55)",
        }}
      >
        {range}
      </div>

      <div style={{ marginTop: "auto", paddingTop: 12 }}>
        <div
          aria-hidden
          style={{
            height: 6,
            background: "var(--pq-ivory-line-soft)",
            position: "relative",
            overflow: "hidden",
            borderRadius: 1,
          }}
        >
          <span
            style={{
              display: "block",
              height: "100%",
              width: `${pct}%`,
              background:
                "linear-gradient(90deg, var(--pq-bronze-deep,#6F5636), var(--pq-bronze,#B8956A))",
              transition: "width 240ms cubic-bezier(0.16,1,0.3,1)",
            }}
          />
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: 6,
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "rgba(245,240,232,0.55)",
          }}
        className="font-mono" >
          {marks.map((m, i) => (
            <span key={i}>{m}</span>
          ))}
        </div>
        <div
          className="font-mono uppercase"
          style={{
            marginTop: 10,
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: postureColor(displayPosture),
          }}
        >
          Posture · {displayPosture}
        </div>
      </div>
    </div>
  );
}

interface Props {
  summary?: RiskSummaryV2;
  layers?: RiskLayerV2[];
}

function pickStatusByLayerNum(
  layers: RiskLayerV2[] | undefined,
  num: RiskLayerV2["num"],
): RiskLayerStatus {
  return layers?.find((l) => l.num === num)?.status ?? "NEUTRAL";
}

// eslint-disable-next-line no-restricted-syntax -- local fmt* helper kept per Wave 2/4-B sweep (delegates to, or intentionally diverges from, @/lib/format); see adjacent note
function fmtPct(n: number | undefined, opts?: { signed?: boolean }): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const v = Math.abs(n) <= 1 ? n * 100 : n;
  const sign = opts?.signed && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}`;
}

export function RiskGaugeGrid({ summary, layers }: Props) {
  // VaR 95% / 1-day — value + gauge.
  // Backend (routes/risk.py) returns var_1d_pct already scaled to percent
  // (`-percentile(...)*100`). The old `|x|<=1 ? x*100` heuristic re-multiplied
  // any genuine sub-1% VaR (e.g. a defensive portfolio's 0.6%) into 60%.
  const var95Raw = summary?.var_95 ?? summary?.var_1d_pct;
  const var95Pct = var95Raw != null ? var95Raw : null;
  const var95Display = var95Pct != null ? `−${Math.abs(var95Pct).toFixed(2)}` : "—";
  // Map |VaR| 0..7% → 0..100% along gauge.
  const var95Gauge = var95Pct != null ? Math.min(100, (Math.abs(var95Pct) / 7) * 100) : 0;

  // Concentration HHI — value already 0..1.
  const hhi = summary?.hhi;
  const hhiDisplay = hhi != null && Number.isFinite(hhi) ? hhi.toFixed(3) : "—";
  const hhiRange =
    summary?.sector_top_name && summary?.sector_top_pct != null
      ? `Threshold < 0.25 · ${summary.sector_top_name} ${(summary.sector_top_pct > 1 ? summary.sector_top_pct : summary.sector_top_pct * 100).toFixed(1)}%`
      : "Threshold < 0.25";
  // 0 → 0%, 0.25 → 100% (the breach line).
  const hhiGauge = hhi != null && Number.isFinite(hhi) ? Math.min(100, (hhi / 0.25) * 100) : 0;

  // Correlation 90-day average — value 0..1.
  const corr = summary?.correlation_avg ?? summary?.corr_risk_index;
  const corrDisplay = corr != null && Number.isFinite(corr) ? corr.toFixed(2) : "—";
  const corrMaxClause =
    summary?.correlation_max != null
      ? `Cluster max ${summary.correlation_max.toFixed(2)}`
      : "Cluster snapshot pending";
  // 0 → 0%, 1 → 100%.
  const corrGauge = corr != null && Number.isFinite(corr) ? Math.min(100, corr * 100) : 0;

  // Tail (Component ES) — es_1d_pct is already percent-scaled by the backend
  // (same contract as var_1d_pct); no re-multiplication.
  const tailRaw = summary?.tail_ces ?? summary?.es_1d_pct;
  const tailPct = tailRaw != null ? tailRaw : null;
  const tailDisplay = tailPct != null ? `−${Math.abs(tailPct).toFixed(2)}` : "—";
  // |ES| 0..8% → 0..100%.
  const tailGauge = tailPct != null ? Math.min(100, (Math.abs(tailPct) / 8) * 100) : 0;

  return (
    <section style={{ marginBottom: 64 }} aria-label="Four primary gauges">
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 22,
          gap: 16,
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            Gauges · Four primary
          </div>
          <h2
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: "var(--pq-text-h3)",
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
              margin: 0,
            }}
          >
            Where the book stands.
          </h2>
        </div>
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.55)",
          }}
        >
          Window · 90 days
        </span>
      </div>

      {/* Mobile fix (2026-05-05): force 2-col made each gauge ~155px at 375px,
          clipping the 44px value number against the 28px card padding. Now
          stacks 1-col below the sm breakpoint. */}
      <div
        className="grid gap-3 grid-cols-1 sm:grid-cols-2"
      >
        <BigGaugeCard
          eyebrow="VaR · 95% / 1-day"
          value={var95Display}
          unit="%"
          range="Normal range −2.0 ↔ −3.5%"
          gaugePct={var95Gauge}
          marks={["Calm", "Strained", "Breach"]}
          posture={pickStatusByLayerNum(layers, 1)}
        />
        <BigGaugeCard
          eyebrow="Concentration · HHI"
          value={hhiDisplay}
          range={hhiRange}
          gaugePct={hhiGauge}
          marks={["Diffuse", "Tilted", "Breach"]}
          posture={pickStatusByLayerNum(layers, 6)}
        />
        <BigGaugeCard
          eyebrow="Correlation · 90-day avg"
          value={corrDisplay}
          range={corrMaxClause}
          gaugePct={corrGauge}
          marks={["Independent", "Clustered", "Synced"]}
          posture={pickStatusByLayerNum(layers, 2)}
        />
        <BigGaugeCard
          eyebrow="Tail · Component ES"
          value={tailDisplay}
          unit="%"
          range="99th percentile · 1-day"
          gaugePct={tailGauge}
          marks={["Thin", "Heavy", "Fat"]}
          posture={pickStatusByLayerNum(layers, 4)}
        />
      </div>
    </section>
  );
}

// Suppress unused-import warning for fmtPct (kept for symmetry with other v2 cards).
void fmtPct;

export default RiskGaugeGrid;
