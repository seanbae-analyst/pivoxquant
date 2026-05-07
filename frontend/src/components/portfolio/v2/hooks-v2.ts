/**
 * Portfolio v2 — local SWR hooks.
 *
 * IMPORTANT: defined here, NOT in `lib/hooks.ts`, so the shared dedupe
 * window of usePortfolioSummary / usePortfolioPositions / useWatchlist
 * (used by /home, /risk, /signals, /watchlist) is not destabilized.
 *
 * Endpoints used:
 *   - GET /api/portfolio/history?period=...   (already in lib/endpoints.ts)
 *   - GET /api/portfolio/trades                (already in lib/endpoints.ts)
 *
 * URLs are NOT changed. Only frontend hooks added.
 */

import useSWR from "swr";
import { API, PORTFOLIO_TRADES } from "@/lib/endpoints";

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.error || r.statusText || `HTTP ${r.status}`);
  }
  return r.json();
};

export type EquityRange = "1mo" | "3mo" | "6mo" | "1yr" | "all";

export interface EquityPoint {
  t: string; // ISO date
  nav: number;
  benchmark?: number;
}

export interface EquityCurveResponse {
  series?: EquityPoint[];
  history?: EquityPoint[]; // legacy alias
  benchmark?: { name?: string };
}

/**
 * useEquityCurve — wraps GET /api/portfolio/history?period=<range>.
 *
 * Backend response shape may use `series` or `history`. Caller normalizes.
 * 60s dedupe window — equity curve does not need sub-minute refresh.
 */
export function useEquityCurve(range: EquityRange) {
  return useSWR<EquityCurveResponse>(API.portfolio.history(range), fetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    revalidateIfStale: false,
    dedupingInterval: 60_000,
    errorRetryCount: 2,
  });
}

export interface TransactionRow {
  id?: number | string;
  date?: string;
  symbol?: string;
  name?: string;
  side?: string; // backend may emit "buy"/"sell" — UI maps to add/trim/close
  action?: "add" | "trim" | "close" | "deposit" | "withdraw";
  qty?: number;
  shares?: number;
  price?: number;
  amount?: number;
  currency?: "USD" | "KRW";
}

export interface TransactionsResponse {
  trades?: TransactionRow[];
  transactions?: TransactionRow[];
}

/**
 * useTransactions — wraps GET /api/portfolio/trades.
 *
 * 30s dedupe — trades are append-only, sub-minute refresh not required.
 * `limit` is appended client-side; backend already supports `?limit=`.
 */
export function useTransactions(limit?: number) {
  const url = limit ? `${PORTFOLIO_TRADES}?limit=${limit}` : PORTFOLIO_TRADES;
  return useSWR<TransactionsResponse>(url, fetcher, {
    // Bug #3 (HANDOVER v22): trades are append-only and not push-mutated
    // by SSE. 30s dedupe + reconnect revalidate is enough; focus
    // revalidate would refetch on every tab-switch with no fresh data.
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    revalidateIfStale: false,
    dedupingInterval: 30_000,
    errorRetryCount: 2,
  });
}
