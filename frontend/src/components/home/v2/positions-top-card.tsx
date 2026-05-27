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
import { pctColor, displayName, normalizeTicker, isKrTicker, fmtPct, fmtMoneyPlain } from "@/lib/format";
// FINDING-021: the SWR payload from /api/portfolio carries the BACKEND
// position shape (snake_case: ticker / avg_cost / current_price), NOT the
// camelCase `@/components/portfolio/types` Position. Importing the wrong
// type let `p.symbol` / `p.avgCost` / `p.current` typecheck while being
// `undefined` at runtime → cur=0, avg=0, pnl=0. Use the real backend type.
import type { Position } from "@/lib/types";

interface PositionsShape {
  positions?: Position[];
}

// Currency is derived from the TICKER, not the position.currency field —
// audit FINDING-021: a KOSPI holding (005930) was rendered with a "USD " prefix
// because position.currency leaked "USD" from seed data. The ticker shape is
// the trustworthy signal: a 6-digit / .KS|.KQ symbol is always KRW-quoted.
//
// Wave 4-B (2026-05-20): migrated to lib/fmtMoneyPlain — byte-identical
// (abs + ASCII "-" sign + KRW round / USD 2dp + "—" sentinel).
function fmtMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  return fmtMoneyPlain(n, currency, currency === "KRW" ? 0 : 2);
}

// fmtPct migrated to @/lib/format (2026-05-19 Wave 2 sweep).
// lib/format.ts `fmtPct` is byte-identical for finite inputs.
//
// fmtMoney NOT migrated: ASCII hyphen vs lib/fmtUsd sign-implicit/U+2212
// behaviour delta — kept inline to avoid regression.

interface MiniRow {
  id: string;
  ticker: string;
  name: string;
  current: number;
  pnlPct: number;
  currency: "USD" | "KRW";
}

export function PositionsTopCard() {
  const { data: posData, isLoading: posLoading } = usePortfolioPositions<PositionsShape>();
  const positions = posData?.positions ?? [];
  // Empty-state flash guard (parity with portfolio/_v2 B-11 fix): SWR may
  // surface `data === undefined` / `isLoading` before the first response
  // resolves, so an actual holder briefly sees the "Add your first holding"
  // empty state. Treat the absence of a response as still-loading regardless
  // of the SWR flag.
  const isInitialLoad = posData === undefined || (posLoading && !posData);

  // 2026-05-15 (bug-hunter P0 + verify-ux fail on PR #383 follow-up):
  // /api/portfolio/positions emits **camelCase** (avgCost / current /
  // purchaseDate / isKorean — routes/portfolio.py:826
  // _build_positions_list). The earlier FINDING-021 comment claimed
  // backend was snake_case — true of the legacy /api/portfolio endpoint
  // (line 227), false of the new /positions alias the frontend now
  // hits. Reading current_price / avg_cost only yielded undefined →
  // cur=0, avg=0, pnl=0 → every row rendered KRW 0/USD 0/0.00% in prod.
  // verify-ux 2026-05-15 confirmed PR #383 fixed /portfolio but this
  // home card was the unaddressed sibling. Read camelCase first,
  // snake_case fallback for legacy compat — same defensive pattern as
  // toPosition() in components/portfolio/types.ts.
  const _curPx = (
    p: Position & { current?: number; avgCost?: number },
  ): number => p.current ?? p.current_price ?? 0;
  const _avgCost = (
    p: Position & { current?: number; avgCost?: number },
  ): number => p.avgCost ?? p.avg_cost ?? 0;

  const ranked: MiniRow[] = [...positions]
    .sort((a, b) => {
      const av = _curPx(a as never) * (a.shares ?? 0);
      const bv = _curPx(b as never) * (b.shares ?? 0);
      return bv - av;
    })
    .slice(0, 5)
    .map((p) => {
      const cur = _curPx(p as never);
      const avg = _avgCost(p as never);
      const pnl = avg > 0 ? ((cur - avg) / avg) * 100 : 0;
      // Name-first (FINDING-011): backend name → static seed → raw ticker.
      // Currency from the ticker shape, not the (seed-leaky) p.currency.
      return {
        id: String(p.id),
        ticker: p.ticker,
        name: displayName(p.ticker, p.name),
        current: cur,
        pnlPct: pnl,
        currency: (isKrTicker(p.ticker) ? "KRW" : "USD") as "USD" | "KRW",
      };
    });

  const remaining = Math.max(0, positions.length - ranked.length);

  return (
    <HomeCard href="/portfolio" eyebrow="Positions · Top weight" cornerCta="Open Book ›">
      {isInitialLoad ? (
        /* Skeleton while the first positions response is in flight — avoids
           flashing the empty state to a user who actually holds positions. */
        <div style={{ display: "flex", flexDirection: "column" }} aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
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
                style={{
                  height: 12,
                  width: "55%",
                  background: "rgba(245,240,232,0.08)",
                  borderRadius: 2,
                }}
              />
              <span
                style={{
                  height: 12,
                  width: 56,
                  background: "rgba(245,240,232,0.08)",
                  borderRadius: 2,
                }}
              />
              <span
                style={{
                  height: 12,
                  width: 40,
                  background: "rgba(245,240,232,0.08)",
                  borderRadius: 2,
                }}
              />
            </div>
          ))}
        </div>
      ) : ranked.length === 0 ? (
        /* P1-5 (2026-05-20 ux-flow fix): old copy ("Add your first holding
           from the Book") leaned on the internal "Book" metaphor and offered
           no visible action. The whole card is already a <Link href="/portfolio">
           (see HomeCard), so we render a button-styled affordance span — it
           inherits the card's navigation, no nested anchor (invalid HTML),
           with a direct, metaphor-free label. */
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.55)",
              margin: 0,
            }}
          >
            No positions yet. Add your first holding to start tracking value,
            P/L, and risk.
          </p>
          <span
            className="font-mono uppercase"
            style={{
              alignSelf: "flex-start",
              display: "inline-flex",
              padding: "10px 18px",
              background: "var(--pq-bronze)",
              color: "var(--pq-ink, #050505)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              borderRadius: "var(--pq-radius-cta, 2px)",
            }}
          >
            Add your first position →
          </span>
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
                  fontSize: "var(--pq-text-body)",
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
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "rgba(245,240,232,0.55)",
                    marginLeft: 8,
                    letterSpacing: "0.12em",
                  }}
                >
                  {normalizeTicker(r.ticker)}
                </small>
              </span>
              <span
                className="font-mono"
                style={{
                  fontVariantNumeric: "tabular-nums",
                  fontSize: "var(--pq-text-body)",
                  color: "rgba(245,240,232,0.82)",
                }}
              >
                {fmtMoney(r.current, r.currency)}
              </span>
              <span
                className="font-mono"
                style={{
                  fontVariantNumeric: "tabular-nums",
                  fontSize: "var(--pq-text-body)",
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
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.55)",
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
