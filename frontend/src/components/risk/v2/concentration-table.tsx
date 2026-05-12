"use client";

/**
 * <ConcentrationTable /> — Block 3 of /risk v2.
 *
 * Top-5 positions by weight. Each row uses the **종목명 main pattern**
 * (CEO 2026-04-26 directive): the company name is the visual 1순위
 * (Playfair 18px ivory) and the ticker lives BELOW as a small mono
 * caption — never lead with the ticker.
 */

import * as React from "react";
import type { ConcentrationEntry } from "@/lib/hooks";

interface Props {
  entries: ConcentrationEntry[];
  sumPct: number;
}

export function ConcentrationTable({ entries, sumPct }: Props) {
  const maxPct = entries.reduce((a, e) => Math.max(a, e.weightPct), 0);
  return (
    <section style={{ marginBottom: 64 }} aria-label="Top concentration positions">
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
            Concentration · Top 5 positions
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
            Where the weight sits.
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
          Sum of top 5 · {sumPct > 0 ? `${sumPct.toFixed(1)}%` : "—"}
        </span>
      </div>

      <div
        className="pq-card"
        style={{
          background: "var(--pq-ink-card, rgba(255,255,255,0.02))",
          border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
          borderRadius: 4,
          padding: "16px 28px",
        }}
      >
        {entries.length === 0 ? (
          <div
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              color: "rgba(245,240,232,0.55)",
              padding: "32px 0",
              textAlign: "center",
            }}
          >
            No positions on file. Add a holding in Portfolio to populate this view.
          </div>
        ) : (
          entries.map((entry, i) => {
            const barPct =
              maxPct > 0 ? Math.min(100, (entry.weightPct / maxPct) * 100) : 0;
            return (
              <div
                key={`${entry.ticker}-${entry.rank}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "32px 1fr 120px 1fr",
                  alignItems: "center",
                  gap: 16,
                  padding: "18px 0",
                  borderBottom:
                    i < entries.length - 1
                      ? "1px solid var(--pq-hairline, var(--pq-ivory-line))"
                      : "none",
                }}
              >
                <span
                  className="font-display"
                  style={{
                    fontSize: "var(--pq-text-quote)",
                    color: "var(--pq-bronze)",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {String(entry.rank).padStart(2, "0")}
                </span>

                {/* 종목명 main pattern: name as Playfair 18px ivory, ticker
                    below as mono 10.5px ivory-mute. Never lead with ticker. */}
                <div style={{ minWidth: 0 }}>
                  <div
                    className="font-display name"
                    style={{
                      fontSize: "var(--pq-text-h5)",
                      color: "var(--pq-ivory)",
                      letterSpacing: "-0.005em",
                    }}
                  >
                    {entry.name}
                  </div>
                  <div
                    className="font-mono"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      color: "rgba(245,240,232,0.55)",
                      letterSpacing: "0.14em",
                      marginTop: 4,
                    }}
                  >
                    {entry.ticker} · {entry.exchange}
                  </div>
                </div>

                <span
                  className="font-mono"
                  style={{
                    fontVariantNumeric: "tabular-nums",
                    fontSize: "var(--pq-text-h5)",
                    color: "var(--pq-ivory)",
                  }}
                >
                  {entry.weightPct.toFixed(1)}%
                </span>

                <span
                  aria-hidden
                  style={{
                    height: 4,
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
                      width: `${barPct}%`,
                      background:
                        "linear-gradient(90deg, var(--pq-bronze-deep,#6F5636), var(--pq-bronze,#B8956A))",
                    }}
                  />
                </span>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

export default ConcentrationTable;
