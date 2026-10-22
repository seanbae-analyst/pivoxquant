import { describe, expect, it } from "vitest";
import { getMarketStatus } from "@/lib/market-hours";
import { PORTFOLIO_DEDUPE_MS } from "@/lib/hooks";

describe("market-hours — exchange clocks, DST-aware (2026-10-22)", () => {
  it("US session in EDT: 13:30-20:00 UTC", () => {
    expect(getMarketStatus(new Date("2026-10-21T13:29:00Z"))).toBe("closed");
    expect(getMarketStatus(new Date("2026-10-21T13:30:00Z"))).toBe("us-open");
    expect(getMarketStatus(new Date("2026-10-21T19:59:00Z"))).toBe("us-open");
    expect(getMarketStatus(new Date("2026-10-21T20:00:00Z"))).toBe("closed");
  });

  it("US session in EST moves an hour later — 20:30 UTC is still open", () => {
    expect(getMarketStatus(new Date("2026-11-04T14:00:00Z"))).toBe("closed");
    expect(getMarketStatus(new Date("2026-11-04T14:30:00Z"))).toBe("us-open");
    expect(getMarketStatus(new Date("2026-11-04T20:30:00Z"))).toBe("us-open");
    expect(getMarketStatus(new Date("2026-11-04T21:00:00Z"))).toBe("closed");
  });

  it("KR session 09:00-15:30 KST on KST weekdays", () => {
    expect(getMarketStatus(new Date("2026-10-21T23:59:00Z"))).toBe("closed"); // Thu 08:59 KST
    expect(getMarketStatus(new Date("2026-10-22T00:00:00Z"))).toBe("kr-open"); // Thu 09:00 KST
    expect(getMarketStatus(new Date("2026-10-22T06:30:00Z"))).toBe("kr-open"); // 15:30 KST
    expect(getMarketStatus(new Date("2026-10-22T06:31:00Z"))).toBe("closed");
    expect(getMarketStatus(new Date("2026-10-26T00:30:00Z"))).toBe("kr-open");
    expect(getMarketStatus(new Date("2026-10-24T01:00:00Z"))).toBe("closed"); // Sat KST
  });

  it("the portfolio dedupe window is shorter than the open-market poll", () => {
    expect(PORTFOLIO_DEDUPE_MS).toBeLessThan(5_000);
  });
});
