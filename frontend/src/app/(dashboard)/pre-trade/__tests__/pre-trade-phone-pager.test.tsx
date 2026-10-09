/**
 * /pre-trade on a phone (CEO 2026-10-09 — "멈춤부분도 … 화면 넘기는 식으로
 * 앱처럼"): setup → seven questions → review are screens you swipe between.
 *
 * Page-level guarantees pinned here:
 *   - setup only pages forward once ticker + reason are filled (swipe = the
 *     button's gate);
 *   - going back to setup and forward again keeps every answer and tick;
 *   - the /start payload from the phone flow is byte-identical to the one
 *     the md+ list produces for the same answers.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

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
import { SWIPE_MIN_PX } from "@/lib/use-swipe-pager";
import { sideToWire } from "@/lib/pre-trade";
import PreTradePage from "@/app/(dashboard)/pre-trade/page";

const mockedFetch = vi.mocked(apiFetch);
const FAR = SWIPE_MIN_PX + 24;
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

function swipe(el: Element, dx: number) {
  const base = { pointerId: 1, pointerType: "touch", clientX: 200, clientY: 300 };
  fireEvent.pointerDown(el, base);
  fireEvent.pointerUp(el, { ...base, clientX: 200 + dx });
}
function tap(el: Element) {
  const base = { pointerId: 2, pointerType: "touch", clientX: 10, clientY: 10 };
  fireEvent.pointerDown(el, base);
  fireEvent.pointerUp(el, base);
  fireEvent.click(el);
}

const setupSurface = () => screen.getByText("수량 (선택)");
const questionText = (n: number) =>
  screen.getByTestId(`question-${n}`).querySelector("p") as HTMLElement;
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

describe("/pre-trade · phone pager", () => {
  it("setup pages forward by swipe only once ticker and reason are filled", () => {
    stubViewport(true);
    render(<PreTradePage />);
    swipe(setupSurface(), -FAR);
    expect(screen.queryByTestId("question-1")).toBeNull();
    expect((screen.getByTestId("setup-next-phone") as HTMLButtonElement).disabled).toBe(true);

    fillSetup();
    swipe(setupSurface(), -FAR);
    expect(screen.getByTestId("question-1")).toBeTruthy();
    expect(screen.getByTestId("questions-progress").textContent).toContain("질문 1 / 7");
  });

  it("back to setup and forward again keeps answers, ticks and setup fields", () => {
    stubViewport(true);
    render(<PreTradePage />);
    fillSetup();
    fireEvent.click(screen.getByTestId("setup-next-phone"));
    fireEvent.change(answerInput(1), { target: { value: "-8%면 접는다" } });
    fireEvent.click(screen.getByTestId("questions-next"));
    tap(box(2));

    // Q2 → Q1 → setup, by swipe.
    swipe(questionText(2), FAR);
    swipe(questionText(1), FAR);
    expect(screen.queryByTestId("question-1")).toBeNull();
    expect((screen.getByLabelText("종목") as HTMLInputElement).value).toBe("AAPL");
    expect((screen.getByLabelText(/이유/) as HTMLTextAreaElement).value).toBe(REASON);

    swipe(setupSurface(), -FAR);
    expect(answerInput(1).value).toBe("-8%면 접는다");
    expect(box(1).checked).toBe(true);
    expect(box(2).checked).toBe(true);
    expect(screen.getByTestId("questions-progress").textContent).toContain("검토 2 / 7");
  });

  it("the phone flow sends the same /start payload as the md+ list", async () => {
    // Phone: buttons, swipes and a detour back, ending on the review screen.
    stubViewport(true);
    const phone = render(<PreTradePage />);
    fillSetup();
    swipe(setupSurface(), -FAR);
    fireEvent.change(answerInput(1), { target: { value: "-8%면 접는다" } });
    fireEvent.click(screen.getByTestId("questions-next"));
    tap(box(2));
    swipe(questionText(2), -FAR);
    swipe(questionText(3), FAR); // back to Q2, then on
    swipe(questionText(2), -FAR);
    for (let n = 3; n <= 7; n++) {
      if (n === 5) fireEvent.change(answerInput(5), { target: { value: "  두려움 3/10  " } });
      fireEvent.click(screen.getByTestId("questions-next"));
    }
    fireEvent.click(screen.getByTestId("questions-start-phone"));
    await waitFor(() => expect(startBodies()).toHaveLength(1));
    phone.unmount();

    // md+: the list, every box ticked by hand, the footer start.
    stubViewport(false);
    render(<PreTradePage />);
    fillSetup();
    const desktopNext = screen
      .getAllByRole("button", { name: /다음 · 질문 7개/ })
      .find((b) => !b.dataset.testid) as HTMLButtonElement;
    fireEvent.click(desktopNext);
    fireEvent.change(answerInput(1), { target: { value: "-8%면 접는다" } });
    fireEvent.change(answerInput(5), { target: { value: "  두려움 3/10  " } });
    for (let n = 1; n <= 7; n++) fireEvent.click(box(n));
    fireEvent.click(screen.getByTestId("questions-start"));
    await waitFor(() => expect(startBodies()).toHaveLength(2));

    const [fromPhone, fromDesktop] = startBodies();
    expect(fromPhone).toEqual(fromDesktop);
    expect(fromPhone).toMatchObject({ ticker: "AAPL", side: sideToWire("ENTRY"), rationale: REASON });
  });
});
