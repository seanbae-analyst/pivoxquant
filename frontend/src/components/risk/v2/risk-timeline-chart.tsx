"use client";

/**
 * <RiskTimelineChart /> — Block 5 of /risk v2.
 *
 * 30-day composite risk score (0..100) over time. Bronze stroke + soft
 * fill with a low-alpha strain wash above 60. Lower = calmer; higher =
 * strain — never "loss" or "forecast", per legal copy rules.
 *
 * Data source: derived client-side from rolling VaR (per SPEC §6) until
 * backend ships a first-class composite endpoint. The figcaption
 * documents this for traceability.
 */

import * as React from "react";
import type { RiskTimelinePoint } from "@/lib/hooks";

interface Props {
  series: RiskTimelinePoint[];
  today: number | null;
  avg: number | null;
  max: number | null;
  daysAboveStrain: number;
  strainThreshold: number;
}

const W = 1200;
const H = 200;

function buildPolyline(series: RiskTimelinePoint[]): string {
  if (series.length === 0) return "";
  const dx = W / Math.max(1, series.length - 1);
  return series
    .map((p, i) => {
      const x = (i * dx).toFixed(1);
      // score 0..100 → y H..0 (low score = calm = lower line on screen)
      const y = (H - (p.score / 100) * H).toFixed(1);
      return `${x},${y}`;
    })
    .join(" ");
}

function buildAreaPolygon(series: RiskTimelinePoint[]): string {
  const line = buildPolyline(series);
  if (!line) return "";
  return `${line} ${W},${H} 0,${H}`;
}

export function RiskTimelineChart({
  series,
  today,
  avg,
  max,
  daysAboveStrain,
  strainThreshold,
}: Props) {
  const polyline = buildPolyline(series);
  const polygon = buildAreaPolygon(series);
  const strainY = H - (strainThreshold / 100) * H;

  return (
    <section style={{ marginBottom: 64 }} aria-label="Risk timeline">
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
              fontSize: 12,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            Timeline · 30 days
          </div>
          <h2
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: 32,
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
              margin: 0,
            }}
          >
            Risk over time.
          </h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span
            className="font-mono uppercase"
            style={{
              fontSize: 12,
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.40)",
            }}
          >
            Composite score · 0–100
          </span>
          <span
            className="font-mono"
            style={{
              fontSize: 16,
              color: "var(--pq-ivory)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {today ?? "—"}
          </span>
        </div>
      </div>

      <figure
        className="pq-card"
        style={{
          background: "var(--pq-ink-card, rgba(255,255,255,0.02))",
          border: "1px solid var(--pq-hairline, rgba(245,240,232,0.08))",
          borderRadius: 4,
          padding: 32,
          margin: 0,
        }}
      >
        <figcaption className="sr-only">
          Composite risk score (0–100, higher = more strain) observed over the
          last 30 days. Today {today ?? "—"}, 30-day average {avg ?? "—"}, 30-day
          maximum {max ?? "—"}, days above strain threshold {daysAboveStrain}.
          Data source: derived from rolling VaR.
        </figcaption>

        {series.length < 2 ? (
          <div
            className="font-serif"
            style={{
              fontSize: 14,
              color: "rgba(245,240,232,0.55)",
              padding: "60px 0",
              textAlign: "center",
            }}
          >
            Not enough observations to draw a 30-day trace yet.
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
            style={{ width: "100%", height: 200, display: "block" }}
            aria-hidden
          >
            <defs>
              <linearGradient id="pqRiskFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="rgba(184,149,106,0.16)" />
                <stop offset="100%" stopColor="rgba(184,149,106,0)" />
              </linearGradient>
            </defs>

            {/* Strain wash above threshold (top band, low-alpha) */}
            <rect
              x="0"
              y="0"
              width={W}
              height={strainY}
              fill="rgba(220,38,38,0.04)"
            />

            {/* Gridlines */}
            <line x1="0" x2={W} y1={H * 0.2} y2={H * 0.2} stroke="rgba(245,240,232,0.05)" />
            <line
              x1="0"
              x2={W}
              y1={strainY}
              y2={strainY}
              stroke="rgba(245,240,232,0.08)"
              strokeDasharray="4 6"
            />
            <line x1="0" x2={W} y1={H * 0.6} y2={H * 0.6} stroke="rgba(245,240,232,0.05)" />
            <line x1="0" x2={W} y1={H * 0.8} y2={H * 0.8} stroke="rgba(245,240,232,0.05)" />

            {/* Polygon fill + stroke */}
            <polyline points={polygon} fill="url(#pqRiskFill)" stroke="none" />
            <polyline
              points={polyline}
              fill="none"
              stroke="var(--pq-bronze, #B8956A)"
              strokeWidth="1.6"
            />

            {/* Threshold label */}
            <text
              x={W - 20}
              y={strainY - 4}
              textAnchor="end"
              style={{
                fontSize: 10,
                fill: "rgba(245,240,232,0.40)",
                letterSpacing: "0.18em",
              }}
            className="font-mono" >
              STRAIN · {strainThreshold}
            </text>
          </svg>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: 32,
            marginTop: 24,
            paddingTop: 20,
            borderTop: "1px solid var(--pq-hairline, rgba(245,240,232,0.08))",
          }}
        >
          {[
            { label: "Today", value: today },
            { label: "30-day avg", value: avg },
            { label: "30-day max", value: max },
            { label: "Days above strain", value: daysAboveStrain },
          ].map((kpi) => (
            <div key={kpi.label}>
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: 12,
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                  marginBottom: 8,
                }}
              >
                {kpi.label}
              </div>
              <div
                className="font-mono"
                style={{
                  fontVariantNumeric: "tabular-nums",
                  fontSize: 22,
                  color: "var(--pq-ivory)",
                }}
              >
                {kpi.value ?? "—"}
              </div>
            </div>
          ))}
        </div>
      </figure>
    </section>
  );
}

export default RiskTimelineChart;
