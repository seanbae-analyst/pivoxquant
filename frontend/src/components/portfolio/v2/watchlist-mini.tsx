"use client";

/**
 * <WatchlistMini /> — corner card listing top watchlist items (mockup §BLOCK 3b).
 *
 * 종목명 main pattern: Playfair name 15px ivory + mono ticker 10px dim.
 * Reuses `useWatchlist()` (lib/hooks.ts — UNCHANGED).
 */

import * as React from "react";
import Link from "next/link";
import { useWatchlist } from "@/lib/hooks";
import type { WatchlistResponse } from "@/lib/types";
import { normalizeTicker, fmtPctSignedMinus } from "@/lib/format";

interface WatchlistMiniProps {
  limit?: number;
}

// Wave 4-B (2026-05-20): fmtPctSigned migrated to lib/fmtPctSignedMinus.
// fmtMoney KEPT inline — watchlist `last_price` is always non-negative,
// so local toLocaleString-with-raw-n vs lib fmtMoneyPlain(abs + sign)
// produce identical output in practice. Migrating would shift the
// negative-value rendering (legacy "$-50.00" vs lib "-$50.00") which is
// behaviour we don't currently exercise but want to preserve for safety.
function fmtMoney(n: number, currency: "USD" | "KRW"): string {
  if (!Number.isFinite(n)) return "—";
  const dec = currency === "KRW" ? 0 : 2;
  const body = n.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${currency === "KRW" ? "₩" : "$"}${body}`;
}

function fmtPctSigned(n: number): string {
  return fmtPctSignedMinus(n, 2);
}

function pctColor(n: number): string {
  if (!Number.isFinite(n)) return "rgba(245,240,232,0.55)";
  if (n > 0) return "var(--pq-positive, #b8956a)";
  if (n < 0) return "var(--pq-negative, #d18888)";
  return "rgba(245,240,232,0.55)";
}

export function WatchlistMini({ limit = 6 }: WatchlistMiniProps) {
  const { data } = useWatchlist() as { data: WatchlistResponse | undefined };
  const items = (data?.watchlist ?? []).slice(0, limit);
  const total = data?.watchlist?.length ?? 0;
  const more = Math.max(0, total - items.length);

  return (
    <div
      className="pq-card"
      style={{
        background: "var(--pq-card-bg-ink, rgba(255,255,255,0.02))",
        border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
        borderRadius: "var(--pq-radius-card, 4px)",
        padding: 24,
        minHeight: 380,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 20,
        }}
      >
        Watchlist · Tape
      </div>

      {items.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "rgba(245,240,232,0.55)",
            fontSize: "var(--pq-text-body)",
          }}
        className="font-serif" >
          No tickers on watch.
        </div>
      ) : (
        <ul
          style={{
            flex: 1,
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {items.map((w, i) => {
            const price = w.price ?? w.last_price ?? 0;
            const change = w.change_pct ?? w.change_1d_pct ?? 0;
            return (
              <li
                key={w.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto auto",
                  gap: 12,
                  alignItems: "center",
                  padding: "10px 0",
                  borderBottom:
                    i < items.length - 1
                      ? "1px solid var(--pq-hairline-ink, var(--pq-ivory-line-soft))"
                      : "none",
                }}
              >
                {/* 종목명 main pattern */}
                <Link
                  href={`/detail/${encodeURIComponent(w.ticker)}`}
                  style={{
                    display: "block",
                    textDecoration: "none",
                  }}
                >
                  <div
                    className="font-display"
                    style={{
                      fontSize: "var(--pq-text-lead)",
                      fontWeight: 500,
                      color: "var(--pq-ivory)",
                      lineHeight: 1.2,
                    }}
                  >
                    {w.name}
                  </div>
                  <div
                    className="font-mono uppercase"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.18em",
                      color: "rgba(245,240,232,0.55)",
                      marginTop: 2,
                    }}
                  >
                    {normalizeTicker(w.ticker)}
                  </div>
                </Link>
                <span
                  className="font-mono tabular-nums"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "rgba(245,240,232,0.82)",
                  }}
                >
                  {fmtMoney(price, w.currency)}
                </span>
                <span
                  className="font-mono tabular-nums"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    color: pctColor(change),
                  }}
                >
                  {fmtPctSigned(change)}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      <div
        style={{
          marginTop: 16,
          paddingTop: 12,
          borderTop: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
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
          {more > 0 ? `${more} more · ${total} total` : `${total} total`}
        </span>
        <Link
          href="/watchlist"
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.2em",
            color: "var(--pq-bronze)",
            textDecoration: "none",
            borderBottom: "1px solid rgba(184,149,106,0.35)",
            paddingBottom: 1,
          }}
        >
          Open watchlist ›
        </Link>
      </div>
    </div>
  );
}

export default WatchlistMini;
