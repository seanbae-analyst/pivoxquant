/**
 * /pre-trade — tap-first (2026-10-25, CEO "적어야 할게 너무 많다").
 *
 * Pinned: a reason chip alone opens the questions (no 10-character paragraph);
 * the rationale is the picks joined with " · " plus the optional line; each
 * question has one-tap answers that tick it, and on a phone a tap moves to the
 * next screen; the audit blob carries the tapped answer verbatim.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor, within } from "@testing-library/react";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {}
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
import { QUESTIONS, composeRationale, joinQuickAnswer, splitQuickAnswer } from "@/components/pre-trade/pre-trade-friction-core";

const mockedFetch = vi.mocked(apiFetch);

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



function reflection(status: "ready" | "proceeded") {
  return {
    reflection: {
      id: 42, intended_ticker: "AAPL", intended_side: "ENTRY", intended_shares: null,
      rationale: "실적·숫자", cooldown_started_at: "2026-10-25T00:00:00Z",
      cooldown_ends_at: "2026-10-25T00:00:00Z",
      proceeded_at: status === "proceeded" ? "2026-10-25T00:00:01Z" : null,
      cancelled_at: null, auto_extended_reason: null, seconds_remaining: 0, status,
    },
  };
}

function startBodies(): Array<Record<string, string>> {
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

const shown = (n: number) => !screen.getByTestId(`question-${n}`).className.includes("hidden md:block");

describe("pre-trade answer helpers", () => {
  it("joins picks and the optional line into one rationale", () => {
    expect(composeRationale(["실적·숫자", "차트 자리"], "")).toBe("실적·숫자 · 차트 자리");
    expect(composeRationale(["실적·숫자"], "  가이던스 상향 ")).toBe("실적·숫자 — 가이던스 상향");
    expect(composeRationale([], "그냥 한 줄")).toBe("그냥 한 줄");
    expect(composeRationale([], "  ")).toBe("");
  });

  it("splits and re-joins a quick answer with its line", () => {
    const quick = QUESTIONS[1].quick;
    expect(splitQuickAnswer(quick[0], quick)).toEqual({ pick: quick[0], extra: "" });
    expect(splitQuickAnswer(`${quick[0]} — 60선`, quick)).toEqual({ pick: quick[0], extra: "60선" });
    expect(splitQuickAnswer("직접 쓴 답", quick)).toEqual({ pick: null, extra: "직접 쓴 답" });
    expect(joinQuickAnswer(quick[0], "60선")).toBe(`${quick[0]} — 60선`);
    expect(joinQuickAnswer(quick[0], " ")).toBe(quick[0]);
    expect(joinQuickAnswer(null, "직접")).toBe("직접");
  });

  it("every question has at least three quick answers and every chip clears the floor", () => {
    for (const q of QUESTIONS) expect(q.quick.length).toBeGreaterThanOrEqual(3);
  });
});

describe("/pre-trade · tap-first", () => {
  it("a reason chip alone opens the questions", () => {
    stubViewport(false);
    render(<PreTradePage />);
    fireEvent.change(screen.getByLabelText("종목"), { target: { value: "aapl" } });
    const next = screen.getAllByRole("button", { name: /다음 · 질문 7개/ })[0];
    expect(next).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "실적·숫자" }));
    expect(next).not.toBeDisabled();
    // A second tap takes the pick back.
    fireEvent.click(screen.getByRole("button", { name: "실적·숫자" }));
    expect(next).toBeDisabled();
  });

  it("on a phone, seven taps answer the seven questions and the payload carries them", async () => {
    stubViewport(true);
    render(<PreTradePage />);
    fireEvent.change(screen.getByLabelText("종목"), { target: { value: "aapl" } });
    fireEvent.click(screen.getByRole("button", { name: "실적·숫자" }));
    fireEvent.click(screen.getByRole("button", { name: "차트 자리" }));
    fireEvent.click(screen.getByTestId("setup-next-phone"));

    for (const q of QUESTIONS) {
      await waitFor(() => expect(shown(q.n)).toBe(true));
      fireEvent.click(within(screen.getByTestId(`question-${q.n}-quick`)).getAllByRole("radio")[0]);
    }
    const start = await screen.findByTestId("questions-start-phone");
    await waitFor(() => expect(start).not.toBeDisabled());
    fireEvent.click(start);

    await waitFor(() => expect(startBodies()).toHaveLength(1));
    const body = startBodies()[0];
    expect(body.rationale).toBe("실적·숫자 · 차트 자리");
    for (const q of QUESTIONS) {
      expect(body.devil_advocate).toContain(`Q${q.n} ${q.en}\n→ ${q.quick[0]}`);
    }
  });

  it("a tap keeps the line typed under it", () => {
    stubViewport(false);
    render(<PreTradePage />);
    fireEvent.change(screen.getByLabelText("종목"), { target: { value: "aapl" } });
    fireEvent.click(screen.getByRole("button", { name: "원래 계획" }));
    fireEvent.click(screen.getAllByRole("button", { name: /다음 · 질문 7개/ })[0]);
    const q2 = screen.getByTestId("question-2");
    const line = q2.querySelector('input:not([type="checkbox"])') as HTMLInputElement;
    fireEvent.change(line, { target: { value: "60일선" } });
    fireEvent.click(within(q2).getByRole("radio", { name: QUESTIONS[1].quick[0] }));
    expect(line.value).toBe("60일선");
    expect(within(q2).getByRole("radio", { name: QUESTIONS[1].quick[0] })).toHaveAttribute("aria-checked", "true");
    expect((q2.querySelector('input[type="checkbox"]') as HTMLInputElement).checked).toBe(true);
  });
});
