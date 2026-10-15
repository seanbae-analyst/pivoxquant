/**
 * Pre-Trade Friction — cooldown 0 auto-proceed (FIX 3), on the /pre-trade
 * route. 2026-10-13: the inline portfolio modal that used to host this test
 * is gone (/pre-trade is the only pause), so the shared-core behavior is
 * pinned through the page instead:
 *   - /start returns an already-ready reflection → the core calls /proceed
 *     on its own (no extra click) and lands on the terminal recap;
 *   - the 00:00 countdown never renders;
 *   - nothing but /start and /proceed is called — the pause writes no ledger
 *     row, so the recap says "stamped only", not "recorded".
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  }
  return { apiFetch: vi.fn(), ApiError };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/lib/hooks", () => ({
  fetcher: vi.fn(),
  useResearchByTicker: () => ({ note: null, count: 0, isLoading: false }),
  useObservationNotesByTicker: () => ({
    notes: [], count: 0, disclaimer: null, isLoading: false, error: undefined, mutate: vi.fn(),
  }),
}));
// The real field queries /api/search on a debounce; a plain input is enough.
vi.mock("@/components/shared/ticker-search", () => ({
  TickerSearch: (p: { id?: string; value: string; onChange: (v: string) => void; ariaLabel?: string }) => (
    <input
      id={p.id}
      aria-label={p.ariaLabel}
      value={p.value}
      onChange={(e) => p.onChange(e.target.value.toUpperCase())}
    />
  ),
}));

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import PreTradePage from "@/app/(dashboard)/pre-trade/page";

const mockedFetch = vi.mocked(apiFetch);
const REASON = "long thesis here, well over the minimum for the gate.";

// A reflection that is already ready (backend cooldown = 0, 2026-05-22).
function readyReflection(status: "ready" | "proceeded") {
  return {
    reflection: {
      id: 42,
      intended_ticker: "AAPL",
      intended_side: "ENTRY",
      intended_shares: 10,
      rationale: REASON,
      cooldown_started_at: "2026-05-22T00:00:00Z",
      cooldown_ends_at: "2026-05-22T00:00:00Z",
      proceeded_at: status === "proceeded" ? "2026-05-22T00:00:01Z" : null,
      cancelled_at: null,
      auto_extended_reason: null,
      seconds_remaining: 0,
      status,
    },
  };
}

// md+ viewport: the seven questions render as one list with a footer start.
function stubDesktop() {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("reduced-motion"),
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

const box = (n: number) =>
  screen.getByTestId(`question-${n}`).querySelector('input[type="checkbox"]') as HTMLInputElement;

const originalMatchMedia = window.matchMedia;
beforeEach(() => {
  mockedFetch.mockReset();
  stubDesktop();
});
afterEach(() => {
  cleanup();
  window.matchMedia = originalMatchMedia;
});

describe("Pre-Trade Friction — cooldown 0 auto-proceed (FIX 3)", () => {
  it("skips the countdown screen and auto-proceeds when reflection is immediately ready", async () => {
    // /start → ready (seconds_remaining 0), /proceed → proceeded.
    mockedFetch.mockImplementation((url: string) => {
      if (url === API.preTrade.start) return Promise.resolve(readyReflection("ready"));
      if (url === API.preTrade.proceed(42)) return Promise.resolve(readyReflection("proceeded"));
      return Promise.reject(new Error(`unexpected url ${url}`));
    });

    render(<PreTradePage />);
    fireEvent.change(screen.getByLabelText("종목"), { target: { value: "aapl" } });
    fireEvent.change(screen.getByLabelText(/이유/), { target: { value: REASON } });
    const desktopNext = screen
      .getAllByRole("button", { name: /다음 · 질문 7개/ })
      .find((b) => !b.dataset.testid) as HTMLButtonElement;
    fireEvent.click(desktopNext);

    // Acknowledge all 7 questions.
    for (let n = 1; n <= 7; n++) fireEvent.click(box(n));
    fireEvent.click(screen.getByTestId("questions-start"));

    // /proceed fires automatically — no extra click.
    await waitFor(() =>
      expect(mockedFetch.mock.calls.map((c) => c[0])).toContain(API.preTrade.proceed(42)),
    );

    // Terminal recap is shown instead of a countdown. (Tests run without the
    // message catalog, so useT() renders keys.)
    await waitFor(() => expect(screen.getByText("preTrade.done.proceededHead")).toBeTruthy());
    expect(screen.queryByText("00:00")).toBeNull();
    expect(screen.queryByText(/남은 시간/)).toBeNull();
    // No host commit on /pre-trade: the recap says the pause was stamped only
    // (not "recorded"), and points to journaling the fill afterwards.
    expect(screen.getByText(/preTrade\.done\.stampedOnly/)).toBeTruthy();
    expect(screen.queryByText(/preTrade\.done\.recorded/)).toBeNull();
    expect(screen.getByText("preTrade.done.importHint")).toBeTruthy();

    // Exactly /start then /proceed — no /status polling, no ledger write.
    expect(mockedFetch.mock.calls.map((c) => c[0])).toEqual([
      API.preTrade.start,
      API.preTrade.proceed(42),
    ]);
  });
});
