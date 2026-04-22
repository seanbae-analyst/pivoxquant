/**
 * Mock index quotes for the Market page — US + KR tabs.
 * Hand-crafted deterministic 30-point sparklines.
 */

import type { IndexQuote } from "./index-card";

/** Generate a deterministic 30-point wobble anchored at `base`. */
function wobble(base: number, amp: number, seed: number): number[] {
  const pts: number[] = [];
  for (let i = 0; i < 30; i++) {
    const a = Math.sin((i + seed) / 3.1) * amp;
    const b = Math.cos((i + seed) / 4.7) * amp * 0.6;
    pts.push(base + a + b);
  }
  return pts;
}

export const US_INDICES: IndexQuote[] = [
  {
    symbol: "SPX",
    name: "S&P 500",
    level: 5218.42,
    changePct: 0.31,
    weekHigh52: 5264.85,
    weekLow52: 4103.78,
    spark: wobble(5200, 24, 1),
    format: "en",
  },
  {
    symbol: "NDX",
    name: "Nasdaq Composite",
    level: 16342.18,
    changePct: 0.58,
    weekHigh52: 16538.86,
    weekLow52: 12543.86,
    spark: wobble(16250, 120, 2),
    format: "en",
  },
  {
    symbol: "DJI",
    name: "Dow Jones",
    level: 38912.55,
    changePct: -0.12,
    weekHigh52: 39889.05,
    weekLow52: 32327.2,
    spark: wobble(38900, 180, 3),
    format: "en",
  },
  {
    symbol: "RUT",
    name: "Russell 2000",
    level: 2042.18,
    changePct: -0.28,
    weekHigh52: 2134.2,
    weekLow52: 1636.94,
    spark: wobble(2038, 18, 4),
    format: "en",
  },
  {
    symbol: "VIX",
    name: "CBOE Volatility",
    level: 15.8,
    changePct: -2.14,
    weekHigh52: 28.32,
    weekLow52: 11.81,
    spark: wobble(16, 0.8, 5),
    format: "en",
  },
];

export const KR_INDICES: IndexQuote[] = [
  {
    symbol: "KOSPI",
    name: "KOSPI",
    level: 2612.34,
    changePct: 0.42,
    weekHigh52: 2780.14,
    weekLow52: 2280.63,
    spark: wobble(2605, 18, 6),
    format: "kr",
  },
  {
    symbol: "KOSDAQ",
    name: "KOSDAQ",
    level: 847.91,
    changePct: -0.18,
    weekHigh52: 932.4,
    weekLow52: 782.17,
    spark: wobble(848, 6, 7),
    format: "kr",
  },
  {
    symbol: "KOSPI200",
    name: "KOSPI 200",
    level: 355.2,
    changePct: 0.35,
    weekHigh52: 378.12,
    weekLow52: 308.44,
    spark: wobble(354, 3, 8),
    format: "kr",
  },
  {
    symbol: "KOSDAQ150",
    name: "KOSDAQ 150",
    level: 1248.6,
    changePct: -0.24,
    weekHigh52: 1382.45,
    weekLow52: 1108.92,
    spark: wobble(1250, 10, 9),
    format: "kr",
  },
  {
    symbol: "USDKRW",
    name: "USD / KRW",
    level: 1342.5,
    changePct: 0.12,
    weekHigh52: 1398.8,
    weekLow52: 1264.2,
    spark: wobble(1340, 8, 10),
    format: "kr",
    unit: "KRW",
  },
];

/** Simple domestic futures/options summary rows. */
export interface DerivativeRow {
  label: string;
  value: string;
  note: string;
}

export const KR_DERIVATIVES: DerivativeRow[] = [
  {
    label: "KOSPI 200 Futures (front month)",
    value: "356.45",
    note: "basis +1.25 vs spot",
  },
  {
    label: "KOSPI 200 Call OI (ATM)",
    value: "42,184",
    note: "strike 355",
  },
  {
    label: "KOSPI 200 Put OI (ATM)",
    value: "38,902",
    note: "strike 355",
  },
  {
    label: "V-KOSPI (implied vol)",
    value: "14.62",
    note: "-0.18 vs yesterday",
  },
];
