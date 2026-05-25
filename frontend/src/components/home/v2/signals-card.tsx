"use client";

/**
 * <SignalsCard /> — Card 5 of /home v2.
 *
 * Top-3 signals from /api/signals. Inline `useSWR` (no new lib/hooks.ts
 * entry — preserves the rule that existing 14 hooks remain untouched).
 *
 * Each signal: ticker (Playfair 22px) + label (POSITIVE/NEGATIVE/NEUTRAL,
 * mono uppercase eyebrow, KR price convention colors) + rationale paragraph.
 *
 * Locked vocabulary: POSITIVE / NEGATIVE / NEUTRAL only — no BUY/SELL/HOLD.
 */

import * as React from "react";
import useSWR from "swr";
import { HomeCard } from "./home-card";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { displayName, isNakedTicker } from "@/lib/format";

interface SignalItem {
  id?: number | string;
  ticker?: string;
  symbol?: string;
  /**
   * 회사명 — backfilled by routes/signals.py via resolve_stock_name().
   * Always present; falls back to ticker when resolver lacks the listing.
   * Surfaced in the home hero so users see "삼성전자" not "005930".
   */
  name?: string;
  /**
   * Backend `engine.py` historically returns "signal" only; the home v2
   * card used to read `s.label` and always fell through to "NEUTRAL"
   * (root cause of the home/signals-page divergence reported 2026-04-28).
   * Both keys accepted now.
   */
  signal?: string;
  label?: string;
  rationale?: string;
  reason?: string;
  strength?: number;
}
interface SignalsResponse {
  signals?: SignalItem[];
  items?: SignalItem[];
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

// Exported for unit testing the evaluation-token color mapping.
export function colorForLabel(label: string): string {
  // Signal *evaluation* labels use the dedicated evaluation tokens
  // (--pq-positive bronze / --pq-negative carmine), NOT price-direction tokens.
  // Using PRICE_COLOR_HEX.up/down here mislabeled signal sentiment as price
  // movement (2026-05-24 reversal bug; sibling signal-card.tsx is correct).
  if (label === "POSITIVE") return "var(--pq-positive, #b8956a)";
  if (label === "NEGATIVE") return "var(--pq-negative, #d18888)";
  return "rgba(245,240,232,0.55)";
}

export function SignalsCard() {
  const { data } = useSWR<SignalsResponse>(API.signals.all, fetcher, {
    refreshInterval: 30_000,
    // Bug #3 (HANDOVER v22): the home signals card already polls every
    // 30s. Keep behaviour consistent with `useSignals` in hooks.ts — focus
    // revalidate disabled to avoid duplicate fetches during nav.
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 10_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  });

  const items = (data?.signals ?? data?.items ?? []).slice(0, 3);

  return (
    <HomeCard href="/signals" eyebrow="Signals · Today's three" cornerCta="All signals ›">
      {items.length === 0 ? (
        <div
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.6,
            color: "rgba(245,240,232,0.55)",
            fontStyle: "italic",
          }}
        >
          No signals observed in this session.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {items.map((s, i) => {
            const ticker = s.ticker || s.symbol || "—";
            // 회사명 우선, ticker 폴백 — routes/signals.py 가 resolve_stock_name()
            // 으로 backfill 하지만, 미해석/콜드캐시 종목은 ticker 가 그대로 온다.
            // displayName() 이 정적 시드(삼성전자 등)로 한 번 더 메운다 (FINDING-011).
            const display = displayName(ticker, s.name);
            // FINDING-012: a real company name belongs in Playfair; a bare
            // 6-digit / all-caps code does NOT — render it in mono tabular-nums
            // so editorial weight is never wasted on an illegible ID.
            const displayIsTicker = isNakedTicker(display);
            // Backend engine.py:420 returns "signal" key only; "label" is undefined.
            // Read both fields so home card matches signals page (v1 used `s.signal`,
            // v2 uses `s.label ?? s.signal`). Without this every ticker rendered NEUTRAL.
            const label = (s.label ?? s.signal ?? "NEUTRAL").toString().toUpperCase();
            const rationale =
              s.rationale ||
              s.reason ||
              "Model state observed; rationale unavailable.";
            return (
              <div
                key={s.id ?? `${ticker}-${i}`}
                style={
                  i === 0
                    ? {}
                    : {
                        borderTop: "1px solid var(--pq-hairline-ink)",
                        paddingTop: 18,
                      }
                }
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                    marginBottom: 6,
                  }}
                >
                  <span
                    className={displayIsTicker ? "font-mono tabular-nums" : "font-display"}
                    style={{
                      fontWeight: 500,
                      fontSize: "var(--pq-text-quote)",
                      letterSpacing: displayIsTicker ? "0.04em" : "-0.01em",
                      color: "var(--pq-ivory)",
                    }}
                  >
                    {display}
                  </span>
                  <span
                    className="font-mono uppercase"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.22em",
                      textTransform: "uppercase",
                      color: colorForLabel(label),
                    }}
                  >
                    {label}
                  </span>
                </div>
                <p
                  className="font-serif"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    lineHeight: 1.5,
                    color: "rgba(245,240,232,0.82)",
                    margin: 0,
                  }}
                >
                  {rationale}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </HomeCard>
  );
}

export default SignalsCard;
