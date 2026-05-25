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
  symbol?: string;
  name?: string;
  shares: number;
  // 2026-05-15 (P0 bug-hunter live-prod finding): the production
  // `/api/portfolio/positions` GET handler (routes/portfolio.py
  // _build_positions_list, line 814) emits the camelCase shape
  // `{avgCost, current, purchaseDate, isKorean}` while this adapter
  // (FINDING-021, 2026-05-14 design-audit) reads the snake_case shape
  // `{avg_cost, current_price, purchase_date, is_korean}`. The legacy
  // snake_case shape is still emitted by `GET /api/portfolio` (line
  // 227) — the original endpoint the adapter was written against —
  // but no production consumer hits that legacy route any more.
  //
  // The mismatch produced `undefined` for every numeric field; the
  // `?? 0` fallback then silently zeroed avgCost + current, which
  // cascaded into KRW 0/USD 0 for every Holdings row, NAV → 0, weights →
  // 0%, and Sectors → "No allocation yet". All 4 positions on every
  // user's portfolio rendered as zero in prod 2026-05-15. Holding
  // both shapes here keeps both endpoints working.
  avg_cost?: number;
  avgCost?: number;
  current_price?: number;
  current?: number;
  observed_at?: string | null;
  sector?: string;
  currency?: "USD" | "KRW";
  side?: Side;
  purchase_date?: string;
  purchaseDate?: string;
  notes?: string;
  is_korean?: boolean;
  isKorean?: boolean;
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
 * 2026-05-15 (P0 follow-up): the adapter itself had a snake_case-only read
 * path, while the actual `/api/portfolio/positions` endpoint emits
 * camelCase. Both shapes are now accepted (camelCase first, snake_case
 * fallback) so the adapter is correct whether wired to the new alias
 * route or the legacy `/api/portfolio` GET. Confirmed against prod
 * payload sample: `{avgCost: 15630, current: 22550, isKorean: true}`.
 *
 * `side` / `purchaseDate` / `notes` are not emitted by the backend list
 * endpoint; they default to safe values (components read them defensively).
 */
export function toPosition(row: BackendPositionRow): Position {
  return {
    id: String(row.id),
    symbol: row.symbol ?? row.ticker,
    name: row.name ?? row.ticker,
    side: row.side ?? "Long",
    shares: row.shares ?? 0,
    avgCost: row.avgCost ?? row.avg_cost ?? 0,
    current: row.current ?? row.current_price ?? 0,
    notes: row.notes,
    sector: row.sector ?? "Unclassified",
    purchaseDate: row.purchaseDate ?? row.purchase_date ?? "",
    observed_at: row.observed_at ?? null,
    currency: row.currency,
  };
}
