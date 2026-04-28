"use client";

/**
 * <PositionsTopCard /> — Card 4 of /home v2.
 *
 * Top-5 positions by weight (current price × shares) — mini-row markup,
 * no DataTable. Map of v1's row-2 Positions table → editorial card.
 *
 * Each row: company name (Playfair-leaning serif 14px) + ticker code
 * (mono 10px dim) — the "name main, ticker subordinate" pattern locked in
 * design v3 (CEO directive 2026-04-26).
 *
 * Card click goes to /portfolio. Per SPEC §2 the inner ticker links would
 * fight the wrapper anchor, so we render plain spans and let the whole
 * card act as one link. Power-users can still drill into /detail/[ticker]
 * from /portfolio itself.
 */

import * as React from "react";
import { HomeCard } from "./home-card";
import { usePortfolioPositions } from "@/lib/hooks";
import { pctColor } from "@/lib/format";
import type { Position } from "@/components/portfolio/types";

interface PositionsShape {
  positions?: Position[];
}

function fmtMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const dec = currency === "KRW" ? 0 : 2;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${sign}${currency === "KRW" ? "₩" : "$"}${body}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

interface MiniRow {
  id: string;
  ticker: string;
  name: string;
  current: number;
  pnlPct: number;
  currency: "USD" | "KRW";
}

export function PositionsTopCard() {
  const { data: posData } = usePortfolioPositions<PositionsShape>();
  const positions = posData?.positions ?? [];

  const ranked: MiniRow[] = [...positions]
    .sort((a, b) => {
      const av = (a.current ?? 0) * (a.shares ?? 0);
      const bv = (b.current ?? 0) * (b.shares ?? 0);
      return bv - av;
    })
    .slice(0, 5)
    .map((p) => {
      const cur = p.current ?? 0;
      const avg = p.avgCost ?? 0;
      const pnl = avg > 0 ? ((cur - avg) / avg) * 100 : 0;
      return {
        id: p.id,
        ticker: p.symbol,
        name: p.name || p.symbol,
        current: cur,
        pnlPct: pnl,
        currency: (p.currency as "USD" | "KRW") ?? "USD",
      };
    });

  const remaining = Math.max(0, positions.length - ranked.length);

  return (
    <HomeCard href="/portfolio" eyebrow="Positions · Top weight" cornerCta="Open Book ›">
      {ranked.length === 0 ? (
        <div
          className="font-serif"
          style={{
            fontFamily:
              '"Source Serif 4","Iowan Old Style",Georgia,serif',
            fontSize: 14,
            lineHeight: 1.6,
            color: "rgba(245,240,232,0.55)",
            fontStyle: "italic",
          }}
        >
          No positions on file. Add your first holding from the Book.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {ranked.map((r) => (
            <div
              key={r.id}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto auto",
                gap: 10,
                padding: "9px 0",
                borderBottom: "1px solid var(--pq-hairline-ink)",
                alignItems: "baseline",
              }}
            >
              <span
                className="font-serif"
                style={{
                  fontFamily:
                    '"Source Serif 4","Iowan Old Style",Georgia,serif',
                  fontSize: 14,
                  color: "var(--pq-ivory)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {r.name}{" "}
                <small
                  className="font-mono"
                  style={{
                    fontFamily:
                      '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                    fontSize: 10,
                    color: "rgba(245,240,232,0.40)",
                    marginLeft: 8,
                    letterSpacing: "0.12em",
                  }}
                >
                  {r.ticker}
                </small>
              </span>
              <span
                className="font-mono"
                style={{
                  fontFamily:
                    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                  fontVariantNumeric: "tabular-nums",
                  fontSize: 13,
                  color: "rgba(245,240,232,0.82)",
                }}
              >
                {fmtMoney(r.current, r.currency)}
              </span>
              <span
                className="font-mono"
                style={{
                  fontFamily:
                    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                  fontVariantNumeric: "tabular-nums",
                  fontSize: 13,
                  color: pctColor(r.pnlPct),
                }}
              >
                {fmtPct(r.pnlPct)}
              </span>
            </div>
          ))}
        </div>
      )}

      <div
        style={{
          marginTop: 20,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <span
          className="font-mono uppercase"
          style={{
            fontFamily:
              '"JetBrains Mono","SF Mono",ui-monospace,monospace',
            fontSize: 10.5,
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.40)",
            textTransform: "uppercase",
          }}
        >
          {remaining > 0
            ? `${remaining} more · ${positions.length} total`
            : `${positions.length} total`}
        </span>
      </div>
    </HomeCard>
  );
}

export default PositionsTopCard;
