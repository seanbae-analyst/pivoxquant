"use client";

/**
 * <PositionsLedgerPaper /> — Paper 2 (ledger).
 *
 * Editorial positions table on ivory paper. Same data shape as the
 * canonical /portfolio positions endpoint. Each row is a hairline
 * separator on paper, hovers up 2px.
 *
 * Handles KRW/USD display via the position.currency field (falls back
 * to USD if missing). Real-time updates flow through the underlying
 * TickNumber on each price cell.
 *
 * Legal: read-only display. No BUY/SELL/HOLD labels.
 */

import * as React from "react";
import Link from "next/link";
import { TickNumber } from "@/components/ui/tick-number";
import type { Position } from "@/components/portfolio/types";

interface Props {
  positions: Position[];
  /** Limit rows displayed. Defaults to 12 so all typical books fit without hiding KRW positions. */
  limit?: number;
}

export function PositionsLedgerPaper({ positions, limit = 12 }: Props) {
  // Sort: USD first by abs(pnl%), then KRW — keeps KR positions always visible
  // without burying USD positions that matter most. Both present.
  const sorted = [...positions].sort((a, b) => {
    if (a.currency !== b.currency) return a.currency === "KRW" ? 1 : -1;
    return Math.abs(b.pnlPct ?? 0) - Math.abs(a.pnlPct ?? 0);
  });
  const rows = sorted.slice(0, limit);
  const hidden = positions.length - rows.length;

  return (
    <div
      style={{
        padding: "clamp(24px, 3vw, 40px)",
        display: "flex",
        flexDirection: "column",
        gap: 16,
        minHeight: 420,
      }}
    >
      <div
        className="flex items-center justify-between"
        style={{ marginBottom: 4 }}
      >
        <div className="pq-paper-kicker">Positions · Ledger</div>
        <Link
          href="/portfolio"
          className="pq-paper-kicker"
          style={{
            fontSize: 9,
            letterSpacing: "0.22em",
            color: "rgba(20,20,20,0.55)",
            textDecoration: "none",
          }}
        >
          {hidden > 0 ? `+${hidden} more · Full ledger →` : "Full ledger →"}
        </Link>
      </div>

      {rows.length === 0 ? (
        <p
          className="pq-paper-body"
          style={{
            fontStyle: "italic",
            color: "rgba(20,20,20,0.55)",
            fontSize: 13.5,
          }}
        >
          No positions observed in this book yet.
        </p>
      ) : (
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            tableLayout: "fixed",
          }}
        >
          <colgroup>
            <col style={{ width: "34%" }} />
            <col style={{ width: "11%" }} />
            <col style={{ width: "18%" }} />
            <col style={{ width: "18%" }} />
            <col style={{ width: "19%" }} />
          </colgroup>
          <thead>
            <tr>
              {["Name", "Qty", "Avg cost", "Current", "Δ"].map((h, i) => (
                <th
                  key={h}
                  className="pq-paper-kicker"
                  style={{
                    textAlign: i === 0 ? "left" : "right",
                    padding: "0 0 10px 0",
                    borderBottom: "0.5px solid rgba(184,149,106,0.32)",
                    fontSize: 9,
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const pnlPct =
                p.avgCost > 0 ? ((p.current - p.avgCost) / p.avgCost) * 100 : 0;
              const tone =
                pnlPct > 0.01
                  ? "pq-paper-pos"
                  : pnlPct < -0.01
                  ? "pq-paper-neg"
                  : "pq-paper-neu";
              const cur: "USD" | "KRW" = p.currency === "KRW" ? "KRW" : "USD";
              return (
                <tr key={p.id} className="pq-paper-row">
                  <td style={{ padding: "14px 8px 14px 0" }}>
                    <div
                      style={{
                        fontFamily: "var(--font-serif), Georgia, serif",
                        fontSize: 14.5,
                        color: "#1a1a1a",
                        fontWeight: 500,
                        letterSpacing: "-0.005em",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {p.name}
                    </div>
                    <div
                      style={{
                        fontFamily: "var(--font-mono), ui-monospace, monospace",
                        fontSize: 10,
                        color: "rgba(20,20,20,0.48)",
                        letterSpacing: "0.04em",
                        marginTop: 2,
                      }}
                    >
                      {p.symbol} · {cur}
                    </div>
                  </td>
                  <td
                    style={{
                      padding: "14px 0",
                      textAlign: "right",
                      fontFamily: "var(--font-mono), ui-monospace, monospace",
                      fontSize: 12.5,
                      fontVariantNumeric: "tabular-nums",
                      color: "rgba(20,20,20,0.75)",
                    }}
                  >
                    {p.shares}
                  </td>
                  <td
                    style={{
                      padding: "14px 0",
                      textAlign: "right",
                      fontFamily: "var(--font-mono), ui-monospace, monospace",
                      fontSize: 12.5,
                      fontVariantNumeric: "tabular-nums",
                      color: "rgba(20,20,20,0.6)",
                    }}
                  >
                    {cur === "KRW"
                      ? "\u20A9" + Math.round(p.avgCost).toLocaleString()
                      : "$" +
                        p.avgCost.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                  </td>
                  <td
                    style={{
                      padding: "14px 0",
                      textAlign: "right",
                      fontFamily: "var(--font-mono), ui-monospace, monospace",
                      fontSize: 13,
                      fontVariantNumeric: "tabular-nums",
                      color: "#1a1a1a",
                      fontWeight: 600,
                    }}
                  >
                    <TickNumber
                      value={p.current}
                      currency={cur}
                      decimals={cur === "KRW" ? 0 : 2}
                    />
                  </td>
                  <td
                    style={{
                      padding: "14px 0 14px 0",
                      textAlign: "right",
                      fontFamily: "var(--font-mono), ui-monospace, monospace",
                      fontSize: 12.5,
                      fontVariantNumeric: "tabular-nums",
                      fontWeight: 600,
                    }}
                    className={tone}
                  >
                    {pnlPct >= 0 ? "+" : ""}
                    {pnlPct.toFixed(2)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {positions.length > limit && (
        <p
          style={{
            marginTop: 8,
            fontFamily: "var(--font-serif), Georgia, serif",
            fontStyle: "italic",
            fontSize: 11.5,
            color: "rgba(20,20,20,0.48)",
            letterSpacing: "0.01em",
          }}
        >
          {positions.length - limit} further position
          {positions.length - limit === 1 ? "" : "s"} on the full ledger.
        </p>
      )}
    </div>
  );
}

export default PositionsLedgerPaper;
