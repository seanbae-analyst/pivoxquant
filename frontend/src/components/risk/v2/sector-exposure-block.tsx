"use client";

/**
 * <SectorExposureBlock /> — Block 4 of /risk v2.
 *
 * Two-column layout: 220px donut on the left + leader-name table on
 * the right. The right table follows the **종목명 main pattern**:
 * leader name as Playfair 16px ivory, ticker below as mono 10px dim.
 */

import * as React from "react";
import type { SectorEntry } from "@/lib/hooks";

interface Props {
  sectors: SectorEntry[];
  sectorCount: number;
  cashPct: number;
}

/** Bronze ramp top-3, then graded ivory tints for the long tail. */
const RING_COLORS = [
  "var(--pq-bronze, #B8956A)",
  "var(--pq-bronze-light, #A3845C)",
  "var(--pq-bronze-deep, #6F5636)",
  "rgba(245,240,232,0.55)",
  "rgba(245,240,232,0.22)",
  "rgba(245,240,232,0.14)",
  "rgba(245,240,232,0.10)",
];
const CASH_COLOR = "var(--pq-ivory-line)";

const EYEBROW_COLORS = [
  "var(--pq-bronze, #B8956A)",
  "var(--pq-bronze-light, #A3845C)",
  "var(--pq-bronze-deep, #6F5636)",
];

export function SectorExposureBlock({ sectors, sectorCount, cashPct }: Props) {
  const RADIUS = 80;
  const CIRC = 2 * Math.PI * RADIUS; // 502.65
  const total = sectors.reduce((a, s) => a + s.pct, 0) + cashPct;

  // Build donut segments. Allocate ring colors to top sectors first, then
  // append a cash segment using the cash ring color. We compute the
  // cumulative offset via reduce (no mutation after render).
  type Seg = { color: string; dasharray: string; dashoffset: number };
  const segmentsAcc = sectors.reduce<{ segs: Seg[]; cum: number }>(
    (acc, s, i) => {
      const ratio = total > 0 ? s.pct / total : 0;
      const len = ratio * CIRC;
      const seg: Seg = {
        color: RING_COLORS[Math.min(i, RING_COLORS.length - 1)],
        dasharray: `${len.toFixed(2)} ${CIRC.toFixed(2)}`,
        dashoffset: -acc.cum,
      };
      return { segs: [...acc.segs, seg], cum: acc.cum + len };
    },
    { segs: [], cum: 0 },
  );
  const segments = segmentsAcc.segs;
  const cashSeg: Seg | null =
    cashPct > 0 && total > 0
      ? {
          color: CASH_COLOR,
          dasharray: `${((cashPct / total) * CIRC).toFixed(2)} ${CIRC.toFixed(2)}`,
          dashoffset: -segmentsAcc.cum,
        }
      : null;

  return (
    <section style={{ marginBottom: 64 }} aria-label="Sector exposure">
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
            Exposure · By sector
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
            Sector lens.
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
          {sectorCount} sector{sectorCount === 1 ? "" : "s"} · cash {cashPct.toFixed(1)}%
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 12,
        }}
        className="pq-sector-grid-v2"
      >
        {/* Donut card */}
        <div
          className="pq-card"
          style={{
            background: "var(--pq-ink-card, rgba(255,255,255,0.02))",
            border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
            borderRadius: 4,
            padding: 24,
            minHeight: 380,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <svg
            width="220"
            height="220"
            viewBox="0 0 220 220"
            style={{ display: "block", marginBottom: 28 }}
            role="img"
            aria-label={`${sectorCount} sector donut, cash buffer ${cashPct.toFixed(1)}%`}
          >
            {/* Track ring */}
            <circle
              cx="110"
              cy="110"
              r={RADIUS}
              fill="none"
              stroke="var(--pq-ivory-line-faint)"
              strokeWidth="32"
            />
            {segments.map((seg, i) => (
              <circle
                key={i}
                cx="110"
                cy="110"
                r={RADIUS}
                fill="none"
                stroke={seg.color}
                strokeWidth="32"
                strokeDasharray={seg.dasharray}
                strokeDashoffset={seg.dashoffset}
                transform="rotate(-90 110 110)"
              />
            ))}
            {cashSeg ? (
              <circle
                cx="110"
                cy="110"
                r={RADIUS}
                fill="none"
                stroke={cashSeg.color}
                strokeWidth="32"
                strokeDasharray={cashSeg.dasharray}
                strokeDashoffset={cashSeg.dashoffset}
                transform="rotate(-90 110 110)"
              />
            ) : null}
            <text
              x="110"
              y="104"
              textAnchor="middle"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                fill: "rgba(245,240,232,0.55)",
                letterSpacing: "0.18em",
              }}
            className="font-mono" >
              SECTORS
            </text>
            <text
              x="110"
              y="128"
              textAnchor="middle"
              style={{
                fontSize: "var(--pq-text-h3)",
                fill: "var(--pq-ivory)",
                fontWeight: 500,
              }}
            className="font-display" >
              {sectorCount}
            </text>
          </svg>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.55)",
            }}
          >
            Cash buffer {cashPct.toFixed(1)}%
          </div>
        </div>

        {/* Sector leader table */}
        <div
          className="pq-card"
          style={{
            background: "var(--pq-ink-card, rgba(255,255,255,0.02))",
            border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
            borderRadius: 4,
            padding: 24,
            minHeight: 380,
          }}
        >
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 16,
            }}
          >
            Lead names by sector
          </div>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
            }}
          >
            <thead>
              <tr>
                <th
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                    color: "rgba(245,240,232,0.55)",
                    textAlign: "left",
                    padding: "12px 0",
                    fontWeight: 400,
                    borderBottom:
                      "1px solid var(--pq-hairline, var(--pq-ivory-line))",
                  }}
                >
                  Sector
                </th>
                <th
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                    color: "rgba(245,240,232,0.55)",
                    textAlign: "left",
                    padding: "12px 0",
                    fontWeight: 400,
                    borderBottom:
                      "1px solid var(--pq-hairline, var(--pq-ivory-line))",
                  }}
                >
                  Leader
                </th>
                <th
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                    color: "rgba(245,240,232,0.55)",
                    textAlign: "right",
                    padding: "12px 0",
                    fontWeight: 400,
                    borderBottom:
                      "1px solid var(--pq-hairline, var(--pq-ivory-line))",
                  }}
                >
                  Weight
                </th>
              </tr>
            </thead>
            <tbody>
              {sectors.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-body)",
                      color: "rgba(245,240,232,0.55)",
                      padding: "32px 0",
                      textAlign: "center",
                    }}
                  >
                    No sector breakdown available yet.
                  </td>
                </tr>
              ) : (
                sectors.map((s, i) => (
                  <tr key={`${s.name}-${i}`}>
                    <td
                      style={{
                        padding: "14px 0",
                        verticalAlign: "baseline",
                        borderBottom:
                          i < sectors.length - 1
                            ? "1px solid var(--pq-hairline, var(--pq-ivory-line))"
                            : "none",
                      }}
                    >
                      <span
                        className="font-mono uppercase"
                        style={{
                          fontSize: "var(--pq-text-eyebrow)",
                          letterSpacing: "0.22em",
                          color:
                            i < EYEBROW_COLORS.length
                              ? EYEBROW_COLORS[i]
                              : "rgba(245,240,232,0.55)",
                        }}
                      >
                        {s.name}
                      </span>
                    </td>
                    <td
                      style={{
                        padding: "14px 0",
                        verticalAlign: "baseline",
                        borderBottom:
                          i < sectors.length - 1
                            ? "1px solid var(--pq-hairline, var(--pq-ivory-line))"
                            : "none",
                      }}
                    >
                      {/* 종목명 main pattern: name big, ticker small below */}
                      <div
                        className="font-display name"
                        style={{
                          fontWeight: 500,
                          fontSize: 16,
                          color: "var(--pq-ivory)",
                          letterSpacing: "-0.005em",
                        }}
                      >
                        {s.leaderName}
                      </div>
                      <div
                        className="font-mono"
                        style={{
                          fontSize: "var(--pq-text-eyebrow)",
                          color: "rgba(245,240,232,0.55)",
                          letterSpacing: "0.14em",
                          marginTop: 3,
                        }}
                      >
                        {s.leaderTicker}
                      </div>
                    </td>
                    <td
                      className="font-mono"
                      style={{
                        fontVariantNumeric: "tabular-nums",
                        fontSize: "var(--pq-text-body)",
                        color: "rgba(245,240,232,0.82)",
                        textAlign: "right",
                        padding: "14px 0",
                        verticalAlign: "baseline",
                        borderBottom:
                          i < sectors.length - 1
                            ? "1px solid var(--pq-hairline, var(--pq-ivory-line))"
                            : "none",
                      }}
                    >
                      {s.pct.toFixed(1)}%
                    </td>
                  </tr>
                ))
              )}
              {cashPct > 0 ? (
                <tr>
                  <td
                    style={{
                      padding: "14px 0",
                      verticalAlign: "baseline",
                    }}
                  >
                    <span
                      className="font-mono uppercase"
                      style={{
                        fontSize: "var(--pq-text-eyebrow)",
                        letterSpacing: "0.22em",
                        color: "rgba(245,240,232,0.55)",
                      }}
                    >
                      CASH
                    </span>
                  </td>
                  <td
                    style={{
                      padding: "14px 0",
                      verticalAlign: "baseline",
                    }}
                  >
                    <div
                      className="font-display name"
                      style={{
                        fontWeight: 500,
                        fontSize: 16,
                        color: "var(--pq-ivory)",
                      }}
                    >
                      Idle balance
                    </div>
                    <div
                      className="font-mono"
                      style={{
                        fontSize: "var(--pq-text-eyebrow)",
                        color: "rgba(245,240,232,0.55)",
                        letterSpacing: "0.14em",
                        marginTop: 3,
                      }}
                    >
                      USD · KRW
                    </div>
                  </td>
                  <td
                    className="font-mono"
                    style={{
                      fontVariantNumeric: "tabular-nums",
                      fontSize: "var(--pq-text-body)",
                      color: "rgba(245,240,232,0.82)",
                      textAlign: "right",
                      padding: "14px 0",
                      verticalAlign: "baseline",
                    }}
                  >
                    {cashPct.toFixed(1)}%
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <style jsx>{`
        @media (max-width: 1023px) {
          :global(.pq-sector-grid-v2) {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </section>
  );
}

export default SectorExposureBlock;
