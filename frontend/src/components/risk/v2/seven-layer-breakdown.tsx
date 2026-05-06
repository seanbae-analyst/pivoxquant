"use client";

/**
 * <SevenLayerBreakdown /> — Block 2 of /risk v2.
 *
 * 7 rows inside a single pq-card. Frontend NEVER computes the status —
 * it only renders what the backend authored (POSITIVE / NEGATIVE /
 * NEUTRAL). Color is always paired with the text label per a11y.
 *
 * Falls back to layer scaffolding (name + description) when the backend
 * has not yet published the layer; values render as "—" with NEUTRAL
 * status.
 */

import * as React from "react";
import type { RiskLayerV2, RiskLayerStatus } from "@/lib/hooks";

interface Props {
  layers: RiskLayerV2[];
  observedAtKst?: string | null;
}

interface LayerScaffold {
  num: 1 | 2 | 3 | 4 | 5 | 6 | 7;
  name: string;
  description: string;
}

const SCAFFOLD: LayerScaffold[] = [
  { num: 1, name: "Value at Risk", description: "95% / 99% one-day, 90-day window." },
  { num: 2, name: "Correlation matrix", description: "Pairwise 90-day; Ledoit-Wolf shrunk." },
  { num: 3, name: "VIX gauge", description: "Spot vs. 30-day mean; regime classifier." },
  { num: 4, name: "Component Expected Shortfall", description: "Tail loss attributed to each position." },
  { num: 5, name: "Daily drawdown", description: "Distance from peak NAV today." },
  { num: 6, name: "Sector concentration", description: "HHI on book sector weights." },
  { num: 7, name: "Cash buffer", description: "Idle cash share of NAV." },
];

function statusColor(s: RiskLayerStatus): string {
  if (s === "POSITIVE") return "var(--pq-positive, #dc2626)";
  if (s === "NEGATIVE") return "var(--pq-negative, #2563eb)";
  return "rgba(245,240,232,0.55)";
}

export function SevenLayerBreakdown({ layers, observedAtKst }: Props) {
  // Merge backend layers onto the scaffold so order + names stay stable
  // even if the backend response is partial.
  const byNum = new Map<number, RiskLayerV2>();
  for (const l of layers) byNum.set(l.num, l);
  const merged = SCAFFOLD.map((s) => {
    const live = byNum.get(s.num);
    return live
      ? {
          ...live,
          name: live.name || s.name,
          description: live.description || s.description,
        }
      : ({
          num: s.num,
          name: s.name,
          description: s.description,
          status: "NEUTRAL" as RiskLayerStatus,
          value: "—",
          threshold: undefined,
          observedAtKst: undefined,
        } satisfies RiskLayerV2);
  });

  return (
    <section style={{ marginBottom: 64 }} id="defense-layers">
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
              fontSize: 10.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            Defense · Seven layers
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
            Layer-by-layer.
          </h2>
        </div>
        {observedAtKst ? (
          <span
            className="font-mono uppercase"
            style={{
              fontSize: 10.5,
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.40)",
            }}
          >
            Last observed · {observedAtKst}
          </span>
        ) : null}
      </div>

      <div
        className="pq-card"
        style={{
          background: "var(--pq-ink-card, rgba(255,255,255,0.02))",
          border: "1px solid var(--pq-hairline, rgba(245,240,232,0.08))",
          borderRadius: 4,
          padding: "8px 28px",
        }}
        role="table"
        aria-label="Seven-layer risk defense breakdown"
      >
        {merged.map((l, i) => (
          <div
            key={l.num}
            role="row"
            className="pq-layer-row"
            style={{
              display: "grid",
              gridTemplateColumns: "56px 1fr 110px 130px 110px 140px",
              alignItems: "center",
              gap: 12,
              padding: "20px 0",
              borderBottom:
                i < merged.length - 1
                  ? "1px solid var(--pq-hairline, rgba(245,240,232,0.08))"
                  : "none",
            }}
          >
            <span
              className="font-display"
              style={{
                fontSize: 22,
                color: "var(--pq-bronze)",
                letterSpacing: "-0.01em",
              }}
            >
              {String(l.num).padStart(2, "0")}
            </span>

            <div style={{ minWidth: 0 }}>
              <div
                className="font-display"
                style={{
                  fontSize: 18,
                  color: "var(--pq-ivory)",
                  letterSpacing: "-0.005em",
                }}
              >
                {l.name}
              </div>
              {l.description ? (
                <div
                  className="font-serif"
                  style={{
                    fontSize: 12.5,
                    color: "rgba(245,240,232,0.55)",
                    marginTop: 4,
                  }}
                >
                  {l.description}
                </div>
              ) : null}
            </div>

            <span
              role="cell"
              aria-label={`status: ${l.status}`}
              className="font-mono uppercase"
              style={{
                fontSize: 10.5,
                letterSpacing: "0.22em",
                color: statusColor(l.status),
              }}
            >
              {l.status}
            </span>

            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                fontSize: 16,
                color: "var(--pq-ivory)",
              }}
            >
              {l.value}
            </span>

            <span
              className="font-mono"
              style={{
                fontSize: 11.5,
                color: "rgba(245,240,232,0.55)",
              }}
            >
              {l.threshold ?? "—"}
            </span>

            <span
              className="font-mono"
              style={{
                fontSize: 10.5,
                color: "rgba(245,240,232,0.40)",
                textAlign: "right",
                letterSpacing: "0.04em",
              }}
            >
              {l.observedAtKst ?? observedAtKst ?? "—"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default SevenLayerBreakdown;
