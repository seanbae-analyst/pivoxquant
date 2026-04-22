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
