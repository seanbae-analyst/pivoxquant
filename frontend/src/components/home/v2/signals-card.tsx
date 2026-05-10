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
import { PRICE_COLOR_HEX } from "@/lib/format";

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

function colorForLabel(label: string): string {
  if (label === "POSITIVE") return PRICE_COLOR_HEX.up;
  if (label === "NEGATIVE") return PRICE_COLOR_HEX.down;
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
            fontSize: 14,
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
            // 으로 backfill 하므로 KRX/US 모두 회사명이 들어온다. 미해석 종목은
            // 안전하게 ticker 로 떨어진다.
            const display = s.name || ticker;
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
                    className="font-display"
                    style={{
                      fontWeight: 500,
                      fontSize: 24,
                      letterSpacing: "-0.01em",
                      color: "var(--pq-ivory)",
                    }}
                  >
                    {display}
                  </span>
                  <span
                    className="font-mono uppercase"
                    style={{
                      fontSize: 12,
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
                    fontSize: 14,
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
