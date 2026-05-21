"use client";

/**
 * <ActivityPaper /> — Paper 3 on /portfolio (right column, tilted +4°).
 *
 * Editorial chronology of recent trades. Groups by date, renders as a
 * hairline timeline with bronze accents. Uses the existing Trade shape
 * from @/components/portfolio/types so the parent can feed it straight
 * from the /api/portfolio/trades response.
 *
 * Legal: past events recorded by the user. No prescriptive language.
 * "Bought" / "Sold" labels describe what the user recorded — not a
 * recommendation.
 */

import * as React from "react";
import type { Trade } from "@/components/portfolio/types";
import { displayTicker } from "@/lib/format";

interface Props {
  trades: Trade[];
  /** Book display currency for price formatting. */
  bookCurrency?: "USD" | "KRW";
  limit?: number;
}

function fmtPrice(v: number, cur: "USD" | "KRW"): string {
  if (cur === "KRW") return "\u20A9" + Math.round(v).toLocaleString();
  return (
    "$" +
    v.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

function prettyDate(iso: string): string {
  // Accept "YYYY-MM-DD" or full ISO; fall back to raw.
  try {
    const d = new Date(iso);
    if (!Number.isNaN(d.getTime())) {
      return d
        .toLocaleDateString("en-US", {
          weekday: "short",
          month: "short",
          day: "2-digit",
        })
        .toUpperCase();
    }
  } catch {
    /* noop */
  }
  return iso;
}

export function ActivityPaper({ trades, bookCurrency = "USD", limit = 10 }: Props) {
  const rows = trades.slice(0, limit);

  // Group by date string.
  const grouped = rows.reduce<Record<string, Trade[]>>((acc, t) => {
    (acc[t.date] ||= []).push(t);
    return acc;
  }, {});
  const dateKeys = Object.keys(grouped);

  return (
    <div
      style={{
        padding: "clamp(22px, 2.5vw, 36px)",
        display: "flex",
        flexDirection: "column",
        gap: 18,
        minHeight: 360,
        position: "relative",
      }}
    >
      <div className="pq-paper-kicker">Activity · Chronology</div>

      <h2
        style={{
          fontSize: "clamp(1.5rem, 2.4vw, 1.9rem)",
          lineHeight: 1.05,
          color: "#1a1a1a",
          letterSpacing: "-0.02em",
          marginTop: -4,
        }}
      className="font-serif" >
        Recent entries.
      </h2>

      {rows.length === 0 ? (
        <p
          className="pq-paper-body"
          style={{
            color: "rgba(20,20,20,0.55)",
            fontSize: "var(--pq-text-body)",
          }}
        >
          No transactions recorded yet. Activity surfaces once buys and sales
          are logged.
        </p>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 18,
            marginTop: 4,
          }}
        >
          {dateKeys.map((dk) => (
            <div key={dk}>
              <div
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.26em",
                  textTransform: "uppercase",
                  color: "#B8956A",
                  fontWeight: 600,
                  marginBottom: 8,
                  paddingBottom: 6,
                  borderBottom: "0.5px solid rgba(184,149,106,0.22)",
                }}
              className="font-sans" >
                {prettyDate(dk)}
              </div>
              <ul
                style={{
                  listStyle: "none",
                  margin: 0,
                  padding: 0,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                {grouped[dk].map((t) => {
                  const isBuy = t.side === "Bought";
                  const sign = isBuy ? "+" : "−";
                  const tone = isBuy ? "#4a7a52" : "#a34a4a";
                  return (
                    <li
                      key={t.id}
                      className="pq-activity-row font-mono"
                      style={{
                        display: "flex",
                        alignItems: "baseline",
                        gap: 10,
                        padding: "4px 2px",
                        position: "relative",
                        fontSize: "var(--pq-text-eyebrow)",
                        fontVariantNumeric: "tabular-nums",
                        color: "rgba(20,20,20,0.78)",
                      }}
                    >
                      <span
                        style={{
                          display: "inline-block",
                          width: 14,
                          color: tone,
                          fontWeight: 700,
                          textAlign: "center",
                        }}
                      >
                        {sign}
                      </span>
                      <span
                        style={{
                          color: "#1a1a1a",
                          fontWeight: 600,
                          letterSpacing: "0.04em",
                        }}
                      >
                        {displayTicker(t.symbol)}
                      </span>
                      <span style={{ color: "rgba(20,20,20,0.58)" }}>
                        {t.qty.toLocaleString("en-US")} sh
                      </span>
                      <span
                        style={{
                          color: "rgba(20,20,20,0.45)",
                          }}
                      className="font-serif" >
                        @
                      </span>
                      <span style={{ color: "rgba(20,20,20,0.78)" }}>
                        {fmtPrice(t.price, bookCurrency)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}

      {/* Editorial italic footer */}
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
        · observed ·
      </div>
    </div>
  );
}

export default ActivityPaper;
