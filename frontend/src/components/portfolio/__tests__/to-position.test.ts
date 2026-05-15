// frontend/src/components/portfolio/__tests__/to-position.test.ts
// -----------------------------------------------------------------
// Regression guard for the 2026-05-15 P0 bug-hunter live-prod
// finding: /api/portfolio/positions emits camelCase
// ({avgCost, current, isKorean}) but the toPosition adapter was
// reading the snake_case shape ({avg_cost, current_price,
// is_korean}). The mismatch silently zeroed every Holdings price
// column in prod for every user, cascading to NAV / weights /
// sector allocation = 0.
//
// These tests pin down the shape contract on both directions so the
// adapter cannot regress to a single-shape read path again.

import { describe, it, expect } from "vitest";
import { toPosition, type BackendPositionRow } from "../types";

describe("toPosition — camelCase / snake_case shape contract", () => {
  it("reads the production camelCase shape (avgCost, current)", () => {
    // Mirrors the actual payload from routes/portfolio.py
    // _build_positions_list line 814 (GET /api/portfolio/positions).
    const row: BackendPositionRow = {
      id: 42,
      ticker: "005930.KS",
      symbol: "005930.KS",
      name: "삼성전자",
      side: "Long",
      shares: 10,
      avgCost: 15_630,
      current: 22_550,
      purchaseDate: "2026-01-15",
      sector: "Technology",
      currency: "KRW",
      isKorean: true,
    };
    const out = toPosition(row);
    expect(out.avgCost).toBe(15_630);
    expect(out.current).toBe(22_550);
    expect(out.symbol).toBe("005930.KS");
    expect(out.name).toBe("삼성전자");
    expect(out.purchaseDate).toBe("2026-01-15");
  });

  it("reads the legacy snake_case shape (avg_cost, current_price)", () => {
    // The /api/portfolio (no /positions) GET still emits this shape
    // — routes/portfolio.py line 227. The adapter must keep working
    // against it for any non-list consumer that still uses it.
    const row: BackendPositionRow = {
      id: "7",
      ticker: "AAPL",
      shares: 5,
      avg_cost: 180.5,
      current_price: 198.3,
      purchase_date: "2025-09-01",
      sector: "Technology",
      currency: "USD",
      is_korean: false,
    };
    const out = toPosition(row);
    expect(out.avgCost).toBe(180.5);
    expect(out.current).toBe(198.3);
    expect(out.symbol).toBe("AAPL");
    expect(out.purchaseDate).toBe("2025-09-01");
  });

  it("prefers camelCase when both shapes are present (defensive)", () => {
    const row: BackendPositionRow = {
      id: 1,
      ticker: "AAPL",
      shares: 1,
      avgCost: 200,
      avg_cost: 100, // should lose to camelCase
      current: 220,
      current_price: 110, // should lose
    };
    const out = toPosition(row);
    expect(out.avgCost).toBe(200);
    expect(out.current).toBe(220);
  });

  it("falls back to 0 only when BOTH shapes are absent", () => {
    const row: BackendPositionRow = {
      id: 1,
      ticker: "AAPL",
      shares: 0,
    };
    const out = toPosition(row);
    // The fallback exists for safety but should NOT be hit by any
    // healthy backend response — both endpoints emit one shape or the
    // other. If this test ever fails it means the API stopped
    // emitting position prices entirely (a separate bug).
    expect(out.avgCost).toBe(0);
    expect(out.current).toBe(0);
  });

  it("symbol uses explicit `symbol` field when present (otherwise ticker)", () => {
    expect(
      toPosition({
        id: 1,
        ticker: "AAPL",
        symbol: "AAPL.NASDAQ",
        shares: 1,
        avgCost: 1,
        current: 1,
      }).symbol,
    ).toBe("AAPL.NASDAQ");
    expect(
      toPosition({
        id: 1,
        ticker: "AAPL",
        shares: 1,
        avgCost: 1,
        current: 1,
      }).symbol,
    ).toBe("AAPL");
  });
});
