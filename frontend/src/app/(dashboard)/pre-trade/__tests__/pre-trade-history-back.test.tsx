/**
 * /pre-trade on a phone — the system back gesture (Android back, iOS edge
 * swipe → popstate) steps back through the flow instead of leaving it
 * (lib/use-history-steps, 2026-10-09).
 *
 * Pinned here:
 *   - back from a question returns to the previous question, then to setup,
 *     keeping every answer and tick;
 *   - a step forward ticks a haptic where supported (Android);
 *   - once the reflection is started, back never brings the questions back
 *     (no resubmit) — the flow collapses to the page's own entry;
 *   - md+ pushes no history entries at all.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor, act } from "@testing-library/react";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {}
  return { apiFetch: vi.fn(), ApiError };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/lib/hooks", () => ({
  fetcher: vi.fn(),
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
const REASON = "실적 발표 뒤 가이던스 상향을 확인함";

function stubViewport(phone: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("max-width") ? phone : query.includes("reduced-motion"),
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}


const answerInput = (n: number) =>
  screen.getByTestId(`question-${n}`).querySelector('input:not([type="checkbox"])') as HTMLInputElement;
const box = (n: number) =>
  screen.getByTestId(`question-${n}`).querySelector('input[type="checkbox"]') as HTMLInputElement;

function fillSetup() {
  fireEvent.change(screen.getByLabelText("종목"), { target: { value: "aapl" } });
  fireEvent.change(screen.getByLabelText(/이유/), { target: { value: REASON } });
}

function reflection(status: "ready" | "proceeded") {
  return {
    reflection: {
      id: 42, intended_ticker: "AAPL", intended_side: "ENTRY", intended_shares: null,
      rationale: REASON, cooldown_started_at: "2026-10-09T00:00:00Z",
      cooldown_ends_at: "2026-10-09T00:00:00Z",
      proceeded_at: status === "proceeded" ? "2026-10-09T00:00:01Z" : null,
      cancelled_at: null, auto_extended_reason: null, seconds_remaining: 0, status,
    },
  };
}

/** The JSON body of every POST /start so far. */
function startBodies(): unknown[] {
  return mockedFetch.mock.calls
    .filter((c) => c[0] === API.preTrade.start)
    .map((c) => JSON.parse(String((c[1] as RequestInit).body)));
}

const originalMatchMedia = window.matchMedia;
beforeEach(() => {
  mockedFetch.mockReset();
  mockedFetch.mockImplementation((url: string) => {
    if (url === API.preTrade.start) return Promise.resolve(reflection("ready"));
    if (url === API.preTrade.proceed(42)) return Promise.resolve(reflection("proceeded"));
    return Promise.reject(new Error(`unexpected url ${url}`));
  });
});
afterEach(() => {
  cleanup();
  window.matchMedia = originalMatchMedia;
});

/** jsdom delivers popstate for history.back()/go() on a later task. */
async function systemBack() {
  await act(async () => {
    window.history.back();
    await new Promise((r) => setTimeout(r, 30));
  });
}
const progress = () => screen.getByTestId("questions-progress").textContent ?? "";

describe("/pre-trade · system back (phone)", () => {
  beforeEach(() => {
    window.history.replaceState({ __NA: true }, "", "/pre-trade");
  });

  it("back walks question 2 → question 1 → setup and keeps answers", async () => {
    stubViewport(true);
    render(<PreTradePage />);
    fillSetup();
    fireEvent.click(screen.getByTestId("setup-next-phone"));
    fireEvent.change(answerInput(1), { target: { value: "-8%면 접는다" } });
    fireEvent.click(screen.getByTestId("questions-next"));
    expect(progress()).toContain("질문 2 / 7");

    await systemBack();
    expect(progress()).toContain("질문 1 / 7");
    expect(answerInput(1).value).toBe("-8%면 접는다");
    expect(box(1).checked).toBe(true);

    await systemBack();
    expect(screen.queryByTestId("question-1")).toBeNull();
    expect((screen.getByLabelText("종목") as HTMLInputElement).value).toBe("AAPL");
    expect((screen.getByLabelText(/이유/) as HTMLTextAreaElement).value).toBe(REASON);
    // Nothing was sent by walking back.
    expect(startBodies()).toHaveLength(0);
  });

  it("a step forward gives one haptic tick where vibrate exists", () => {
    stubViewport(true);
    // This file's viewport stub also reports reduced motion, which mutes
    // haptics — answer "no" to that one query here.
    const phoneMedia = window.matchMedia;
    window.matchMedia = ((q: string) =>
      q.includes("reduced-motion")
        ? { ...phoneMedia(q), matches: false }
        : phoneMedia(q)) as typeof window.matchMedia;
    const vibrate = vi.fn();
    Object.defineProperty(navigator, "vibrate", { value: vibrate, configurable: true });
    try {
      render(<PreTradePage />);
      fillSetup();
      fireEvent.click(screen.getByTestId("setup-next-phone"));
      fireEvent.click(screen.getByTestId("questions-next"));
      expect(vibrate).toHaveBeenCalledTimes(2);
      expect(vibrate).toHaveBeenCalledWith(10);
    } finally {
      // @ts-expect-error — test cleanup of the stubbed API
      delete navigator.vibrate;
    }
  });

  it("after the reflection starts, back does not reopen the questions", async () => {
    stubViewport(true);
    render(<PreTradePage />);
    fillSetup();
    fireEvent.click(screen.getByTestId("setup-next-phone"));
    for (let n = 1; n <= 7; n++) fireEvent.click(screen.getByTestId("questions-next"));
    fireEvent.click(screen.getByTestId("questions-start-phone"));
    await waitFor(() => expect(startBodies()).toHaveLength(1));
    await waitFor(() => expect(screen.queryByTestId("questions-progress")).toBeNull());
    // The flow collapsed to the page's own entry.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    const state = window.history.state as { __pqStep?: { idx: number } };
    expect(state.__pqStep?.idx).toBe(0);
    expect(screen.queryByTestId("question-1")).toBeNull();
    expect(startBodies()).toHaveLength(1);
  });

  it("md+ pushes no step entries", () => {
    stubViewport(false);
    const before = window.history.length;
    render(<PreTradePage />);
    fillSetup();
    const desktopNext = screen
      .getAllByRole("button", { name: /다음 · 질문 7개/ })
      .find((b) => !b.dataset.testid) as HTMLButtonElement;
    fireEvent.click(desktopNext);
    expect(window.history.length).toBe(before);
  });
});
