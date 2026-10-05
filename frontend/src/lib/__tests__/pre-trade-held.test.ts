import { describe, expect, it } from "vitest";
import { isHeldTicker } from "@/lib/pre-trade";

describe("isHeldTicker", () => {
  const rows = [
    { ticker: "005930.KS" },
    { ticker: "AAPL", symbol: "AAPL" },
    { ticker: "BRK.B" },
  ];

  it("matches regardless of the KR exchange suffix", () => {
    expect(isHeldTicker("005930", rows)).toBe(true);
    expect(isHeldTicker("005930.ks", rows)).toBe(true);
  });

  it("matches US tickers case-insensitively", () => {
    expect(isHeldTicker(" aapl ", rows)).toBe(true);
  });

  it("keeps US share classes distinct", () => {
    expect(isHeldTicker("BRK.B", rows)).toBe(true);
    expect(isHeldTicker("BRK.A", rows)).toBe(false);
  });

  it("is false for empty input or an unheld ticker", () => {
    expect(isHeldTicker("", rows)).toBe(false);
    expect(isHeldTicker("TSLA", rows)).toBe(false);
    expect(isHeldTicker("TSLA", [])).toBe(false);
  });
});
