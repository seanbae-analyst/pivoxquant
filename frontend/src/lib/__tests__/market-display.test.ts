/**
 * lib/market-display — the two-signal gate.
 *
 * The rule these cases pin down: a market figure is shown only when the
 * frontend flag is on AND the backend has not said `market_data_display:
 * false`. Unset frontend flag is off; absent backend field is not off.
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import {
  isMarketDataDisplayEnabled,
  resolveMarketDataDisplay,
  routeUsesMarketData,
  MARKET_DATA_NOTIFICATION_EVENTS,
} from "@/lib/market-display";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("isMarketDataDisplayEnabled", () => {
  it("is off when the variable is unset", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "");
    expect(isMarketDataDisplayEnabled()).toBe(false);
  });

  it('is off for anything that is not exactly "1"', () => {
    for (const v of ["0", "true", "yes", "on", " 1"]) {
      vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", v);
      expect(isMarketDataDisplayEnabled()).toBe(false);
    }
  });

  it('is on for "1"', () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    expect(isMarketDataDisplayEnabled()).toBe(true);
  });
});

describe("resolveMarketDataDisplay", () => {
  it("is off when the frontend flag is off, whatever the backend says", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    expect(resolveMarketDataDisplay(true)).toBe(false);
    expect(resolveMarketDataDisplay(false)).toBe(false);
    expect(resolveMarketDataDisplay(undefined)).toBe(false);
  });

  it("is off when the backend says false, even with the flag on", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    expect(resolveMarketDataDisplay(false)).toBe(false);
  });

  it("is on with the flag on and no backend field (pre-contract deploy)", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    expect(resolveMarketDataDisplay(undefined)).toBe(true);
    expect(resolveMarketDataDisplay(null)).toBe(true);
  });

  it("is on only when both signals agree", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    expect(resolveMarketDataDisplay(true)).toBe(true);
  });
});

describe("routeUsesMarketData", () => {
  it("is true for /portfolio and its subpaths", () => {
    expect(routeUsesMarketData("/portfolio")).toBe(true);
    expect(routeUsesMarketData("/portfolio/anything")).toBe(true);
  });

  it("is false for the three record surfaces and for settings", () => {
    for (const p of ["/pre-trade", "/journal", "/mirror", "/settings"]) {
      expect(routeUsesMarketData(p)).toBe(false);
    }
  });

  it("is false for a null pathname", () => {
    expect(routeUsesMarketData(null)).toBe(false);
  });

  it("does not match a route that merely starts with the same letters", () => {
    expect(routeUsesMarketData("/portfolios-elsewhere")).toBe(false);
  });
});

describe("MARKET_DATA_NOTIFICATION_EVENTS", () => {
  it("names the 52-week sweep and nothing that runs off the user's own record", () => {
    expect([...MARKET_DATA_NOTIFICATION_EVENTS]).toEqual(["price_52w"]);
  });
});
