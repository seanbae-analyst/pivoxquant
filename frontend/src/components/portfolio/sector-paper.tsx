"use client";

/**
 * <SectorPaper /> — Paper 2 on /portfolio (right column, tilted -3°).
 *
 * Editorial horizontal bar chart: sector weight by market value.
 * Reuses sector allocation computed by the page. Rendering only —
 * no data transforms beyond formatting.
 *
 * Legal: descriptive weighting on user-entered holdings. Nothing
 * prescriptive. No BUY/SELL/HOLD.
 */

import * as React from "react";

interface SectorRow {
  sector: string;
  mv: number;
  pct: number;
}

interface Props {
  rows: SectorRow[];
  bookCurrency?: "USD" | "KRW";
}

function fmtMv(v: number, cur: "USD" | "KRW"): string {
  if (cur === "KRW") return "KRW " + Math.round(v).toLocaleString();
  return (
    "USD " +
    v.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })
  );
}

export function SectorPaper({ rows, bookCurrency = "USD" }: Props) {
  const maxPct = rows.length > 0 ? Math.max(...rows.map((r) => r.pct), 1) : 1;

  return (
    <div
      style={{
        padding: "clamp(22px, 2.5vw, 36px)",
        display: "flex",
        flexDirection: "column",
        gap: 16,
        minHeight: 360,
        position: "relative",
      }}
    >
      <div className="pq-paper-kicker">Sector · Weighting</div>

      <h2
        style={{
          fontSize: "clamp(1.5rem, 2.4vw, 1.9rem)",
          lineHeight: 1.05,
          color: "#1a1a1a",
          letterSpacing: "-0.02em",
          marginTop: -4,
          maxWidth: "16ch",
        }}
      className="font-serif" >
        How the book leans.
      </h2>

      {rows.length === 0 ? (
        <p
          className="pq-paper-body"
          style={{
            color: "rgba(20,20,20,0.55)",
            fontSize: "var(--pq-text-body)",
          }}
        >
          No sector weighting observed yet.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 6 }}>
          {rows.map((r) => {
            const barW = Math.max(2, (r.pct / maxPct) * 100);
            return (
              <div key={r.sector}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    justifyContent: "space-between",
                    marginBottom: 6,
                    gap: 12,
                  }}
                >
                  <span
                    style={{
                      fontSize: "var(--pq-text-body)",
                      color: "#1a1a1a",
                      letterSpacing: "-0.005em",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  className="font-serif" >
                    {r.sector || "—"}
                  </span>
                  <span
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      fontVariantNumeric: "tabular-nums",
                      color: "#B8956A",
                      fontWeight: 600,
                    }}
                  className="font-mono" >
                    {r.pct.toFixed(1)}%
                  </span>
                </div>
                <div
                  style={{
                    height: 2,
                    background: "rgba(184,149,106,0.18)",
                    position: "relative",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      width: `${barW}%`,
                      background:
                        "linear-gradient(90deg, rgba(139,111,71,0.95), rgba(184,149,106,0.55))",
                      transition: "width 480ms cubic-bezier(0.16,1,0.3,1)",
                    }}
                  />
                </div>
                <div
                  style={{
                    marginTop: 4,
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "rgba(20,20,20,0.45)",
                    letterSpacing: "0.02em",
                    fontVariantNumeric: "tabular-nums",
                  }}
                className="font-mono" >
                  {fmtMv(r.mv, bookCurrency)}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Bronze mini-seal */}
      <div
        style={{
          position: "absolute",
          bottom: 18,
          right: 22,
          fontSize: "var(--pq-text-eyebrow)",
          color: "rgba(139,111,71,0.55)",
          letterSpacing: "0.06em",
        }}
        aria-hidden
      className="font-serif" >
        · weighting ·
      </div>
    </div>
  );
}

export default SectorPaper;
