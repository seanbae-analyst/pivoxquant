import { describe, it, expect } from "vitest";
import { derive } from "@/components/portfolio/v2/positions-table-v2";
import type { Position } from "@/components/portfolio/types";

// Regression for the v52 FX-split bug: `totalNav` from the backend summary
// alias is always USD-unified. When the table renders in KRW the per-position
// market value is normalized to KRW, so the weight denominator must also be in
// KRW — otherwise a KR-only book divided KRW by USD and reported ~138,000%.

function mkPos(over: Partial<Position>): Position {
  return {
    id: over.id ?? "1",
    symbol: over.symbol ?? "X",
    name: over.name ?? "X",
    side: over.side ?? "Long",
    shares: over.shares ?? 0,
    avgCost: over.avgCost ?? 0,
    current: over.current ?? 0,
    sector: over.sector ?? "—",
    purchaseDate: over.purchaseDate ?? "2026-01-01",
    currency: over.currency,
  } as Position;
}

const FX = 1380; // 1 USD = 1380 KRW

describe("derive() weight math — currency consistency (v52 FX-split fix)", () => {
  it("KR-only book in KRW: weight ≈ 100%, NOT ~138,000%", () => {
    // Single KR position worth 13,800,000 KRW. Backend totalNav (USD-unified)
    // = 10,000 USD (= 13,800,000 / 1380).
    const positions = [
      mkPos({ id: "k", currency: "KRW", shares: 100, current: 138_000 }),
    ];
    const totalNavUsd = 10_000;
    const rows = derive(positions, totalNavUsd, FX, "KRW");

    // mvNormalized stays in KRW (13,800,000). denominator must be KRW too.
    expect(rows[0].mvNormalized).toBeCloseTo(13_800_000, 0);
    expect(rows[0].weight).toBeGreaterThan(95);
    expect(rows[0].weight).toBeLessThanOrEqual(100.01);
    // Guard the specific bug: NOT off by the FX factor.
    expect(rows[0].weight).toBeLessThan(1000);
  });

  it("US-only book in USD: unchanged — weight ≈ 100%", () => {
    const positions = [
      mkPos({ id: "u", currency: "USD", shares: 10, current: 1000 }),
    ];
    const totalNavUsd = 10_000;
    const rows = derive(positions, totalNavUsd, FX, "USD");
    expect(rows[0].mvNormalized).toBeCloseTo(10_000, 0);
    expect(rows[0].weight).toBeCloseTo(100, 1);
  });

  it("US-only book displayed in KRW: weight uses KRW denominator", () => {
    // 10,000 USD position; totalNav 10,000 USD. Displayed in KRW.
    const positions = [
      mkPos({ id: "u", currency: "USD", shares: 10, current: 1000 }),
    ];
    const totalNavUsd = 10_000;
    const rows = derive(positions, totalNavUsd, FX, "KRW");
    // mvNormalized converted USD→KRW = 13,800,000; denominator also KRW.
    expect(rows[0].mvNormalized).toBeCloseTo(13_800_000, 0);
    expect(rows[0].weight).toBeCloseTo(100, 1);
  });

  it("mixed US+KR book in USD: weights sum ≈ 100% (no regression)", () => {
    // US: 6,000 USD. KR: 5,520,000 KRW (= 4,000 USD). Total = 10,000 USD.
    const positions = [
      mkPos({ id: "u", currency: "USD", shares: 6, current: 1000 }),
      mkPos({ id: "k", currency: "KRW", shares: 100, current: 55_200 }),
    ];
    const totalNavUsd = 10_000;
    const rows = derive(positions, totalNavUsd, FX, "USD");
    const sum = rows.reduce((a, r) => a + r.weight, 0);
    expect(sum).toBeCloseTo(100, 0);
    // US weight 60%, KR weight 40%.
    expect(rows[0].weight).toBeCloseTo(60, 0);
    expect(rows[1].weight).toBeCloseTo(40, 0);
  });

  it("mixed US+KR book in KRW: weights sum ≈ 100% (no regression)", () => {
    const positions = [
      mkPos({ id: "u", currency: "USD", shares: 6, current: 1000 }),
      mkPos({ id: "k", currency: "KRW", shares: 100, current: 55_200 }),
    ];
    const totalNavUsd = 10_000;
    const rows = derive(positions, totalNavUsd, FX, "KRW");
    const sum = rows.reduce((a, r) => a + r.weight, 0);
    expect(sum).toBeCloseTo(100, 0);
    expect(rows[0].weight).toBeCloseTo(60, 0);
    expect(rows[1].weight).toBeCloseTo(40, 0);
  });

  it("KR-only book in KRW with no FX: weight is finite (degenerate fallback)", () => {
    // Degenerate path: backend FX missing. The prescribed fix only KRW-converts
    // the denominator when FX is present, so this case stays USD-denominated.
    // We only guard that it never produces NaN / Infinity (no crash). FX is
    // present in the realistic prod path, exercised by the cases above.
    const positions = [
      mkPos({ id: "k", currency: "KRW", shares: 100, current: 138_000 }),
    ];
    const rows = derive(positions, 10_000, null, "KRW");
    expect(Number.isFinite(rows[0].weight)).toBe(true);
  });
});
