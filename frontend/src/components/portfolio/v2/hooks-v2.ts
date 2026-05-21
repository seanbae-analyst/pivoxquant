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

import * as React from "react";
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

/**
 * Period values accepted by GET /api/portfolio/history.
 * Backend whitelist: "5d" | "1mo" | "3mo" | "6mo" | "1y" — anything else
 * silently falls back to "5d" (Bug #8 — frontend "1yr"/"all" had been
 * resolving to a 5-day window). UI exposes "1y" via the "1Y" tab.
 */
export type EquityRange = "1mo" | "3mo" | "6mo" | "1y";

export interface EquityPoint {
  t: string; // ISO date
  nav: number;
  benchmark?: number;
}

/**
 * Raw shape returned by Flask /api/portfolio/history.
 * Each row is `{ date, value }` — NOT `{ t, nav }`. Bug #8 root cause:
 * the consuming component read `series` / `history` and got `[]`,
 * yielding "Not enough history yet." despite 127 backend points.
 */
interface BackendEquityPoint {
  date: string;
  value: number;
  /** KOSPI200 / SPY comparison value the backend adds per point
   *  (routes/portfolio.py `point["benchmark"]`). Was dropped by the mapper
   *  before — equity-curve-block.tsx's benchmark polyline + "vs benchmark"
   *  KPI then read undefined and always rendered "—". */
  benchmark?: number;
}

interface BackendEquityResponse {
  data?: BackendEquityPoint[];
  /** legacy / alternate shapes — kept defensively */
  series?: EquityPoint[];
  history?: EquityPoint[];
  benchmark?: { name?: string };
}

export interface EquityCurveResponse {
  series: EquityPoint[];
  benchmark?: { name?: string };
}

/**
 * useEquityCurve — wraps GET /api/portfolio/history?period=<range>.
 *
 * Backend currently returns `{ data: [{ date, value }, ...] }`. We normalize
 * to `{ series: [{ t, nav }, ...] }` here so downstream components keep a
 * stable shape regardless of which response variant the backend serves.
 * 60s dedupe window — equity curve does not need sub-minute refresh.
 */
export function useEquityCurve(range: EquityRange) {
  const swr = useSWR<BackendEquityResponse>(
    API.portfolio.history(range),
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      revalidateIfStale: false,
      dedupingInterval: 60_000,
      errorRetryCount: 2,
    },
  );

  const normalized: EquityCurveResponse | undefined = React.useMemo(() => {
    const raw = swr.data;
    if (!raw) return undefined;

    // Preferred legacy shapes win if present (defensive — no current backend
    // path emits these, but a future backend change shouldn't break the UI).
    if (Array.isArray(raw.series) && raw.series.length > 0) {
      return { series: raw.series, benchmark: raw.benchmark };
    }
    if (Array.isArray(raw.history) && raw.history.length > 0) {
      return { series: raw.history, benchmark: raw.benchmark };
    }

    // Current backend shape: { data: [{ date, value }] }
    if (Array.isArray(raw.data)) {
      const series: EquityPoint[] = raw.data
        .filter(
          (p): p is BackendEquityPoint =>
            p != null &&
            typeof p.date === "string" &&
            typeof p.value === "number" &&
            Number.isFinite(p.value),
        )
        .map((p) => ({
          t: p.date,
          nav: p.value,
          // Preserve the per-point benchmark when the backend supplies it.
          ...(typeof p.benchmark === "number" && Number.isFinite(p.benchmark)
            ? { benchmark: p.benchmark }
            : {}),
        }));
      return { series, benchmark: raw.benchmark };
    }

    return { series: [], benchmark: raw.benchmark };
  }, [swr.data]);

  return {
    ...swr,
    data: normalized,
  };
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
