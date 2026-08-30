/**
 * Market index helpers extracted from components/market/index-card.tsx
 * (2026-05-19 Wave 3 — IndexCard component itself was dead code; helpers
 * remain in use across discover / market / indices-detail-paper /
 * overview-paper). Pure TS, no React-DOM dependency aside from `useState`
 * / `useEffect` for the timer hook.
 *
 * Signatures preserved 1:1 — callers should see no behavioural change.
 */

import { useEffect, useState } from "react";

export interface IndexQuote {
  symbol: string;
  name: string;
  level: number;
  /**
   * Daily change. Null when the upstream cannot derive it (live quote
   * succeeded but the history window was empty or discarded as stale —
   * routes/market.py::_etf_snapshot). Renderers MUST show "—" and never
   * 0: a fabricated "+0.00%" reads as a real "no change" datapoint
   * (lib/format.ts::fmtPct, 자본시장법 §101 guard).
   */
  changePct: number | null;
  /**
   * 52-week extremes. Null when the upstream source cannot be trusted
   * (e.g. KIS daily-history endpoint lagging the live level by more
   * than 15% — see routes/market.py _kis_index_snapshot 2026-05-15).
   * Renderers MUST treat null as "—" and never as 0.
   */
  weekHigh52: number | null;
  weekLow52: number | null;
  /** 30-point mini series (relative movement) */
  spark: number[];
  /** How to display the level (e.g. 2_612.34 → "2,612.34") */
  format?: "en" | "kr" | "int";
  /** Unit suffix (e.g. " KRW") */
  unit?: string;
  /** ISO8601 from backend — last observation time for this level */
  observed_at?: string;
  /** Backend-flagged stale (quote older than freshness policy) */
  is_stale?: boolean;
  /**
   * Liquid ETF proxy used to source the level when the caret-prefixed
   * index symbol (e.g. ^GSPC) is gated on the FMP Starter tier.
   * Present ONLY for US indices served via ETF proxy
   * (SPY for ^GSPC, QQQ for ^IXIC, DIA for ^DJI, IWM for ^RUT, VIXY for ^VIX).
   * KR indices and FX pairs do NOT carry this field.
   *
   * When present, the UI MUST surface the proxy so the user does not
   * mistake SPY ($708) for S&P 500 level (7108). The level itself is
   * NEVER converted — a ratio would drift. See routes/market.py:529.
   */
  proxy_ticker?: string;
}

/**
 * Short descriptor text for the ETF proxy badge.
 * Example: `proxyLabel("SPY") === "via SPY · ETF proxy"`.
 * Returns empty string when no proxy (caller guards on truthiness).
 */
export function proxyLabel(proxy: string | undefined): string {
  if (!proxy) return "";
  return `via ${proxy} · ETF proxy`;
}

/**
 * Render an ISO8601 timestamp as a short relative string.
 * Observational language only — "Xs ago", "Xm ago", "just now".
 * Returns "—" when no timestamp is present.
 */
export function relativeTime(iso: string | undefined, nowMs?: number): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const now = nowMs ?? Date.now();
  const diff = Math.max(0, Math.floor((now - t) / 1000));
  if (diff < 3) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/** 1s tick for re-rendering relative timestamps. */
export function useNowTick(intervalMs = 1000): number {
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
