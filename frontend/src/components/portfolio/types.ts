/* Portfolio-local types. Standalone — does NOT alter src/lib/types.ts. */

export type Side = "Long" | "Short";

export interface Position {
  id: string;
  symbol: string;
  name: string;
  side: Side;
  shares: number;
  avgCost: number;
  current: number;
  notes?: string;
  sector: string;
  purchaseDate: string; // ISO (YYYY-MM-DD)
  /** ISO 8601 timestamp the backend observed the last `current` price. */
  observed_at?: string | null;
  /** Display currency. Defaults to USD when absent. */
  currency?: "USD" | "KRW";
}

export interface Trade {
  id: string;
  date: string;
  symbol: string;
  side: "Bought" | "Sold";
  qty: number;
  price: number;
}

export type TradeAction = "buy" | "sell" | "edit";

/**
 * Backend `/api/portfolio` position row — the snake_case shape actually
 * returned by `usePortfolioPositions()` (routes/portfolio.py:176-204).
 * Only the subset of fields the portfolio UI consumes is declared here.
 */
export interface BackendPositionRow {
  id: number | string;
  ticker: string;
  name?: string;
  shares: number;
  avg_cost: number;
  current_price: number;
  observed_at?: string | null;
  sector?: string;
  currency?: "USD" | "KRW";
  side?: Side;
  purchase_date?: string;
  notes?: string;
}

/**
 * FINDING-021 (design-audit-20260514): adapt a backend position row to the
 * camelCase `Position` shape the portfolio + home components expect.
 *
 * Root cause: every consumer of `usePortfolioPositions()` type-annotated the
 * raw backend payload as the camelCase `Position`, so `p.current` /
 * `p.avgCost` / `p.symbol` typechecked but were `undefined` at runtime —
 * NAV, P/L%, and sector weights all silently computed from 0.
 *
 * `side` / `purchaseDate` / `notes` are not emitted by the backend list
 * endpoint; they default to safe values (components read them defensively).
 */
export function toPosition(row: BackendPositionRow): Position {
  return {
    id: String(row.id),
    symbol: row.ticker,
    name: row.name ?? row.ticker,
    side: row.side ?? "Long",
    shares: row.shares ?? 0,
    avgCost: row.avg_cost ?? 0,
    current: row.current_price ?? 0,
    notes: row.notes,
    sector: row.sector ?? "Unclassified",
    purchaseDate: row.purchase_date ?? "",
    observed_at: row.observed_at ?? null,
    currency: row.currency,
  };
}
