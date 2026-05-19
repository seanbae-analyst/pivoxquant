"use client";

/**
 * <CorrelationHeatmap /> — Risk v2 correlation matrix.
 *
 * Restores the v1 90-day pairwise correlation observation surface that
 * was dropped from /risk v2. The endpoint (RISK_CORRELATION) and the
 * payload shape are unchanged — only the chrome is re-tuned to the v2
 * Vantablack + Bronze tone (hairline borders, mono labels, bronze hover
 * outline) per the design system v3 lock-in.
 *
 * Source of v1 visuals: src/app/(dashboard)/risk/_v1/page-v1.tsx
 *   · Diverging gradient (Bronze positive, muted-rose negative)
 *   · Cell title text "{rowLabel} × {colLabel}: {value.toFixed(2)}"
 *   · Sticky header row with bronze tracking-[0.12em] tickers
 *
 * Legal: observational. No recommend/advice/buy/sell language.
 */

import * as React from "react";
import { useRiskCorrelation } from "@/lib/hooks";

export function CorrelationHeatmap() {
  const { labels, matrix, hasData, isLoading } = useRiskCorrelation();

  return (
    <section
      aria-label="Pairwise correlation matrix"
      style={{ marginBottom: 64 }}
    >
      {/* Section header — mirrors v2 typography rhythm */}
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 8,
        }}
      >
        Correlation · 90-day pairwise observation
      </div>
      <h2
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "var(--pq-text-h3)",
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          margin: "0 0 12px 0",
        }}
      >
        How closely the book moves together.
      </h2>
      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          color: "rgba(245,240,232,0.70)",
          lineHeight: 1.55,
          maxWidth: 640,
          margin: "0 0 22px 0",
        }}
      >
        Each cell shows how two holdings have moved together over the last
        90 trading days.{" "}
        <span style={{ color: "var(--pq-bronze)" }}>+1.00</span> means they
        move in lockstep,{" "}
        <span style={{ color: "var(--pq-bronze)" }}>0</span> means no
        relationship,{" "}
        <span style={{ color: "var(--pq-bronze)" }}>−1.00</span> means
        opposite. High numbers everywhere = one bet worn in many costumes.
      </p>

      {/* Gradient legend */}
      <div
        className="font-mono uppercase"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 18,
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "rgba(245,240,232,0.55)",
        }}
      >
        <span>−1</span>
        <span
          style={{
            height: 8,
            flex: 1,
            maxWidth: 220,
            background:
              "linear-gradient(to right, rgba(209,136,136,0.7), rgba(245,240,232,0.12), rgba(139,111,71,0.75))",
          }}
        />
        <span>+1</span>
        <span
          style={{
            marginLeft: "auto",
            color: "rgba(245,240,232,0.4)",
            letterSpacing: "0.18em",
          }}
        >
          Hover a cell for the pair
        </span>
      </div>

      {/* Empty / loading states */}
      {isLoading ? (
        <div
          className="font-serif"
          style={{
            padding: "32px 0",
            color: "rgba(245,240,232,0.55)",
            fontSize: "var(--pq-text-body)",
          }}
        >
          Observing pairwise correlations…
        </div>
      ) : !hasData ? (
        <div
          className="font-serif"
          style={{
            padding: "32px 0",
            color: "rgba(245,240,232,0.55)",
            fontSize: "var(--pq-text-body)",
          }}
        >
          Not enough holdings to compute a correlation matrix yet. Add at
          least two positions to populate this view.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th
                  className="font-mono uppercase"
                  style={{
                    height: 32,
                    width: 48,
                    fontSize: "var(--pq-text-kicker)",
                    letterSpacing: "0.18em",
                    color: "var(--pq-bronze)",
                  }}
                />
                {labels.map((l) => (
                  <th
                    key={l}
                    className="font-mono uppercase"
                    style={{
                      height: 32,
                      width: 48,
                      fontSize: "var(--pq-text-kicker)",
                      letterSpacing: "0.12em",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    {l}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.map((row, i) => (
                <tr key={labels[i] ?? i}>
                  <td
                    className="font-mono uppercase"
                    style={{
                      height: 40,
                      width: 48,
                      paddingRight: 8,
                      textAlign: "right",
                      fontSize: "var(--pq-text-kicker)",
                      letterSpacing: "0.12em",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    {labels[i]}
                  </td>
                  {(Array.isArray(row) ? row : []).map((v, j) => {
                    // Guard non-numeric cells — a backend regression that
                    // emits `null` in the matrix would otherwise crash the
                    // whole Risk Board on .toFixed (feedback_bug_fix_patterns:
                    // per-metric try-except).
                    const isNum =
                      typeof v === "number" && Number.isFinite(v);
                    const alpha = isNum
                      ? Math.min(1, Math.max(0.05, Math.abs(v)))
                      : 0;
                    const bg = !isNum
                      ? "transparent"
                      : v >= 0
                        ? `rgba(139, 111, 71, ${alpha * 0.55})`
                        : `rgba(209, 136, 136, ${alpha * 0.5})`;
                    const cellText = isNum ? v.toFixed(2) : "—";
                    return (
                      <td
                        key={`${i}-${j}`}
                        title={`${labels[i]} × ${labels[j]}: ${cellText}`}
                        className="font-mono tabular-nums"
                        style={{
                          height: 40,
                          width: 48,
                          textAlign: "center",
                          fontSize: "var(--pq-text-eyebrow)",
                          color: "var(--pq-ivory)",
                          backgroundColor: bg,
                          border: "0.5px solid var(--pq-ivory-line-soft)",
                          cursor: "default",
                          transition: "outline 120ms",
                        }}
                        onMouseEnter={(e) => {
                          (e.currentTarget as HTMLTableCellElement).style.outline =
                            "1px solid var(--pq-bronze)";
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLTableCellElement).style.outline =
                            "none";
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
      )}
    </section>
  );
}

export default CorrelationHeatmap;
