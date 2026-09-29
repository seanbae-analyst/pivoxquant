/**
 * RealtimeProvider reads the PORTFOLIO_POSITIONS cache (2026-09-29).
 *
 * The provider only needs "does the user hold ≥1 position?" before opening
 * the SSE stream, and SSE prices must land in the cache the /portfolio page
 * reads. It used to fetch the legacy GET /api/portfolio (API.portfolio.list)
 * for the gate and also merge every tick into that cache, which nothing
 * read. That route is gone; this pins the provider to PORTFOLIO_POSITIONS
 * for both the gate read and the SSE merge.
 */
import React from "react";
import { render, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { RealtimeProvider } from "@/lib/realtime";
import { PORTFOLIO_POSITIONS, PORTFOLIO_SUMMARY } from "@/lib/endpoints";

const STABLE_AUTH = { user: { id: 1, email: "t@x" }, loading: false };
vi.mock("@/lib/auth", () => ({
  useAuth: () => STABLE_AUTH,
}));

// Referentially stable (see realtime-market-gate.test.tsx for why).
const STABLE_POSITIONS = {
  data: { positions: [{ symbol: "AAPL", ticker: "AAPL", shares: 1 }] },
};
const swrKeys: unknown[] = [];
const mutateSpy = vi.fn();
vi.mock("swr", () => ({
  __esModule: true,
  default: (key: unknown) => {
    swrKeys.push(key);
    return STABLE_POSITIONS;
  },
  mutate: (...args: unknown[]) => mutateSpy(...args),
}));

type Listener = (ev: MessageEvent) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  listeners: Record<string, Listener[]> = {};
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(type: string, fn: Listener) {
    (this.listeners[type] ||= []).push(fn);
  }
  close() {
    this.closed = true;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe("RealtimeProvider × PORTFOLIO_POSITIONS", () => {
  beforeEach(() => {
    swrKeys.length = 0;
    mutateSpy.mockReset();
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("gates the stream on the positions cache, and SSE ticks only touch live keys", async () => {
    render(
      <RealtimeProvider>
        <span />
      </RealtimeProvider>,
    );
    await act(async () => {
      await sleep(50);
    });
    expect(swrKeys.length).toBeGreaterThan(0);
    expect(new Set(swrKeys)).toEqual(new Set([PORTFOLIO_POSITIONS]));
    // The positions>0 gate passed off that read.
    expect(FakeEventSource.instances).toHaveLength(1);

    const es = FakeEventSource.instances[0];
    await act(async () => {
      es.onmessage?.({
        data: JSON.stringify({
          prices: { AAPL: 200 },
          details: { AAPL: { price: 200, price_display: "$200.00" } },
        }),
      } as MessageEvent);
    });
    const mutatedKeys = mutateSpy.mock.calls.map((c) => c[0]);
    expect(mutatedKeys).toContain(PORTFOLIO_POSITIONS);
    expect(mutatedKeys).not.toContain("/api/portfolio");
    for (const k of mutatedKeys) {
      expect([PORTFOLIO_POSITIONS, PORTFOLIO_SUMMARY]).toContain(k);
    }
  });
});
