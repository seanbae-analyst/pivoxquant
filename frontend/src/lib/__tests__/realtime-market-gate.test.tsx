/**
 * RealtimeProvider × market-data display flag (2026-09-19).
 *
 * When vendor price display is off the backend answers /portfolio-stream
 * with a single ``event: error`` (MARKET_DATA_DISPLAY_DISABLED) and closes.
 * Left alone, that fed the transport ``onerror`` → 7-step backoff →
 * ``failed: true`` → the yellow "재연결 중" banner, for a stream nobody
 * wanted. Two guards, both pinned here:
 *
 *   1. Frontend flag off → the provider never constructs an EventSource.
 *   2. Frontend flag on but the backend emits the named error → the
 *      provider closes the stream and never schedules a reconnect, and it
 *      does NOT flag ``limitExceeded`` (that copy is about tab limits).
 *
 * Real timers on purpose: the first backoff step is 1s (×0.5–1.0 jitter),
 * so "still one EventSource after 2s" is a real no-reconnect proof, and
 * fake timers + module resets OOM'd the worker on the first attempt.
 */
import React, { useEffect } from "react";
import { render, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { RealtimeProvider, useRealtimeContext, type RealtimeState } from "@/lib/realtime";

// Same rule as the SWR mock below: the provider keys its connect effect on
// ``user``, so this object must be referentially stable across renders.
const STABLE_AUTH = { user: { id: 1, email: "t@x" }, loading: false };
vi.mock("@/lib/auth", () => ({
  useAuth: () => STABLE_AUTH,
}));

// One position so the positions>0 gate is satisfied — the flag must be the
// only thing standing between the provider and a new EventSource.
//
// The response object MUST be referentially stable: the provider keys an
// effect on the positions payload, so a fresh literal per render re-runs
// it → setState → render → fresh literal … an unbounded loop that hung the
// worker (and OOM'd it under fake timers) on the first two attempts.
const STABLE_PORTFOLIO = {
  data: { positions: [{ ticker: "AAPL", shares: 1, avg_cost: 1 }] },
};
vi.mock("swr", () => ({
  __esModule: true,
  default: () => STABLE_PORTFOLIO,
  mutate: vi.fn(),
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
  emit(type: string, data?: string) {
    for (const fn of this.listeners[type] || []) {
      fn({ data } as MessageEvent);
    }
  }
}

/** Reports every provider state to a spy; the test reads the last call. */
function Probe({ onState }: { onState: (s: RealtimeState) => void }) {
  const ctx = useRealtimeContext();
  useEffect(() => {
    onState(ctx);
  }, [ctx, onState]);
  return null;
}

function mount() {
  const onState = vi.fn<(s: RealtimeState) => void>();
  render(
    <RealtimeProvider>
      <Probe onState={onState} />
    </RealtimeProvider>,
  );
  const latest = (): RealtimeState => {
    const calls = onState.mock.calls;
    if (calls.length === 0) throw new Error("provider never rendered");
    return calls[calls.length - 1][0];
  };
  return latest;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe("RealtimeProvider × market-data display flag", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
    // The provider only connects while the tab is visible.
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("never opens the stream when the frontend flag is off", async () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    const latest = mount();
    await act(async () => {
      await sleep(50);
    });
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(latest().streamActive).toBe(false);
    expect(latest().failed).toBe(false);
  });

  it("treats MARKET_DATA_DISPLAY_DISABLED as terminal: close, no reconnect, no limit copy", async () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    const latest = mount();
    await act(async () => {
      await sleep(50);
    });
    expect(FakeEventSource.instances).toHaveLength(1);
    const es = FakeEventSource.instances[0];

    await act(async () => {
      es.emit(
        "error",
        JSON.stringify({ code: "MARKET_DATA_DISPLAY_DISABLED", market_data_display: false }),
      );
    });
    expect(es.closed).toBe(true);
    expect(latest().streamActive).toBe(false);
    expect(latest().limitExceeded).toBe(false);

    // Past the first backoff step (1s × jitter ≤ 1.0): still exactly one
    // EventSource ever constructed → no reconnect was scheduled.
    await act(async () => {
      await sleep(2_000);
    });
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(latest().failed).toBe(false);
  }, 10_000);
});
