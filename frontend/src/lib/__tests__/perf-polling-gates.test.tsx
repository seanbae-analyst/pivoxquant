/**
 * Polling / background reads gated on vendor market-data display
 * (2026-10-09 perf audit). With display off (the default):
 *   - /portfolio summary + positions do not poll at all (cost-basis only;
 *     every writer revalidates them);
 *   - alerts poll at the 60 s closed-market cadence, not every 10 s;
 *   - RealtimeProvider does not read positions on every page just to decide
 *     on a stream it will never open.
 * With display on, the previous cadences are untouched.
 */
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";

const swrKeys: unknown[] = [];
vi.mock("swr", async (orig) => {
  const actual = await orig<typeof import("swr")>();
  return {
    ...actual,
    __esModule: true,
    default: (key: unknown) => {
      swrKeys.push(key);
      return { data: undefined };
    },
  };
});
vi.mock("@/lib/auth", () => ({
  useAuth: () => STABLE_AUTH,
}));
const STABLE_AUTH = { user: { id: 1, email: "t@x" }, loading: false };

import { ALERTS_IDLE_REFRESH_MS, portfolioRefreshInterval } from "@/lib/hooks";
import { RealtimeProvider } from "@/lib/realtime";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { liveRefresh } from "@/lib/market-hours";

afterEach(() => {
  vi.unstubAllEnvs();
  swrKeys.length = 0;
});

describe("portfolio polling", () => {
  it("is off when vendor display is off", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    expect(portfolioRefreshInterval()).toBe(0);
  });

  it("keeps the market-hours cadence when display is on", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    expect(portfolioRefreshInterval()).toBe(liveRefresh(5_000, 60_000));
  });

  it("alerts idle cadence is the closed-market minute", () => {
    expect(ALERTS_IDLE_REFRESH_MS).toBe(60_000);
  });
});

describe("RealtimeProvider positions read", () => {
  it("is skipped when vendor display is off", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    render(<RealtimeProvider><div /></RealtimeProvider>);
    expect(swrKeys).not.toContain(PORTFOLIO_POSITIONS);
    expect(swrKeys.every((k) => k === null)).toBe(true);
  });

  it("still reads positions when display is on", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    render(<RealtimeProvider><div /></RealtimeProvider>);
    expect(swrKeys).toContain(PORTFOLIO_POSITIONS);
  });
});
