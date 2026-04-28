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
    revalidateOnFocus: true,
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
            fontFamily:
              '"Source Serif 4","Iowan Old Style",Georgia,serif',
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
                    className="font-serif"
                    style={{
                      fontFamily:
                        '"Playfair Display","Source Serif 4",Georgia,serif',
                      fontWeight: 500,
                      fontSize: 22,
                      letterSpacing: "-0.01em",
                      color: "var(--pq-ivory)",
                    }}
                  >
                    {ticker}
                  </span>
                  <span
                    className="font-mono uppercase"
                    style={{
                      fontFamily:
                        '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                      fontSize: 10.5,
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
                    fontFamily:
                      '"Source Serif 4","Iowan Old Style",Georgia,serif',
                    fontSize: 13,
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
