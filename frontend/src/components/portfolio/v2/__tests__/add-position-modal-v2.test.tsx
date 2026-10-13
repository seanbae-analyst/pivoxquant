import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the network layer + toast. apiFetch is the Add modal's POST /positions.
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

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// No linkable pauses here (the pause link has its own file,
// add-position-review-link.test.tsx). Keeps the linkable lookup off the
// stubbed global fetch the autocomplete cases count.
vi.mock("@/lib/hooks", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/hooks")>()),
  useLinkableReflections: () => ({ reflections: [], isLoading: false, error: undefined }),
}));

import { apiFetch } from "@/lib/api";
import { toast } from "sonner";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { AddPositionModalV2 } from "@/components/portfolio/v2/add-position-modal-v2";
import { PRE_TRADE_FIRST_COPY } from "@/components/portfolio/v2/pre-trade-first-link";

const mockedFetch = vi.mocked(apiFetch);

async function fillCoreFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText("AAPL · 005930.KS"), "AAPL");
  await user.type(screen.getByPlaceholderText("0"), "10");
  await user.type(screen.getByPlaceholderText("0.00"), "150");
}

describe("AddPositionModalV2 — record-only (2026-10-13)", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    vi.mocked(toast.error).mockReset();
    vi.mocked(toast.success).mockReset();
  });

  it("POSTs directly with purchase_date and no friction", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});
    const onSuccess = vi.fn();
    const onClose = vi.fn();

    render(<AddPositionModalV2 open onClose={onClose} onSuccess={onSuccess} />);

    await fillCoreFields(user);
    // Backdate the purchase date.
    const dateInput = screen.getByLabelText(
      "매수일",
    ) as HTMLInputElement;
    // type=date in jsdom: set the value via change rather than keystrokes.
    fireEvent.change(dateInput, { target: { value: "2025-03-15" } });

    await user.click(screen.getByRole("button", { name: /기록하기/ }));

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    const [url, opts] = mockedFetch.mock.calls[0];
    expect(url).toBe(PORTFOLIO_POSITIONS);
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body).toMatchObject({
      symbol: "AAPL",
      quantity: 10,
      price: 150,
      purchase_date: "2025-03-15",
    });

    // No 7-question reflection appeared.
    expect(screen.queryByText("먼저, 질문 일곱 개.")).toBeNull();
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("has no mode toggle and points to /pre-trade with one link", () => {
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(screen.queryByRole("radio")).toBeNull();
    const link = screen.getByRole("link", { name: PRE_TRADE_FIRST_COPY });
    expect(link.getAttribute("href")).toBe("/pre-trade");
    // The holdings-capture entry is still offered.
    expect(screen.getByTestId("open-holdings-import")).toBeTruthy();
  });

  it("holdingOnly (onboarding): no /pre-trade link and no capture entry", () => {
    render(<AddPositionModalV2 open holdingOnly onClose={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.queryByTestId("pre-trade-first-link")).toBeNull();
    expect(screen.queryByTestId("open-holdings-import")).toBeNull();
    expect(screen.queryByRole("radio")).toBeNull();
  });

  it("constrains the purchase date to today (max attr) and defaults to today", () => {
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    const dateInput = screen.getByLabelText(
      "매수일",
    ) as HTMLInputElement;
    const d = new Date();
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`;

    // Browser-level guard: future dates unselectable. (A redundant JS check in
    // handleSubmit also toasts "매수일은 미래일 수 없습니다." for non-picker input.)
    expect(dateInput.max).toBe(today);
    // Defaults to today.
    expect(dateInput.value).toBe(today);
  });
});

describe("AddPositionModalV2 — Symbol autocomplete dropdown", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let user: ReturnType<typeof userEvent.setup>;

  function jsonResponse(results: unknown[]) {
    return {
      ok: true,
      status: 200,
      json: async () => ({ results }),
    } as unknown as Response;
  }

  // The Symbol field debounces /api/search by 300ms (real setTimeout in the
  // component). Driving that on the wall clock under parallel-suite worker
  // contention made these cases flake on testing-library's 1000ms waitFor
  // timeout. We pin time with fake timers and advance the debounce + fetch
  // microtasks explicitly, then assert with synchronous queries — fully
  // deterministic and independent of CPU load. (We deliberately avoid
  // waitFor/findBy here: vitest fake timers also fake the poller's interval,
  // and testing-library only auto-advances *jest* fake timers, so waitFor
  // would hang. Explicit advanceTimersByTimeAsync is the correct tool.)
  beforeEach(() => {
    // shouldAdvanceTime auto-ticks the fake clock by real elapsed time, which
    // keeps userEvent's internal scheduling from hanging (plain
    // vi.useFakeTimers() — with or without an advanceTimers callback — deadlocks
    // user.type under vitest 4). We still drive the component's 300ms debounce
    // deterministically with advanceTimersByTimeAsync() in flushSearch().
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockedFetch.mockReset();
    vi.mocked(toast.error).mockReset();
    vi.mocked(toast.success).mockReset();
    fetchMock = vi.fn().mockResolvedValue(
      jsonResponse([
        { ticker: "005930.KS", name: "삼성전자", exchange: "KRX", is_korean: true },
        { ticker: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" },
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    user = userEvent.setup();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  // Flush the 300ms debounce timeout AND the chained fetch()/res.json()
  // microtasks that populate `suggestions`, then let React commit the render.
  async function flushSearch() {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
  }

  it("debounced-searches on input and renders suggestion names + tickers", async () => {
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    await user.type(screen.getByLabelText("종목 코드"), "005");
    await flushSearch();

    expect(fetchMock).toHaveBeenCalled();
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain("/api/search?q=");
    expect(calledUrl).toContain("limit=6");

    // Suggestion list renders the company name (bold) + ticker.
    expect(screen.getByText("삼성전자")).toBeTruthy();
    expect(screen.getByText("Apple Inc.")).toBeTruthy();
    expect(screen.getByRole("listbox", { name: "종목 검색 결과" })).toBeTruthy();
  });

  it("clicking a suggestion fills the canonical ticker and closes the popover", async () => {
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    const input = screen.getByLabelText("종목 코드") as HTMLInputElement;
    await user.type(input, "005");
    await flushSearch();

    const option = screen.getByRole("option", { name: /삼성전자/ });
    await user.click(option);

    // Canonical ticker is written into the input; popover is gone.
    expect(input.value).toBe("005930.KS");
    expect(screen.queryByRole("listbox", { name: "종목 검색 결과" })).toBeNull();
    // Resolved name confirmation is shown.
    expect(screen.getByText("삼성전자")).toBeTruthy();
  });

  it("does not re-search after a pick (picked suppresses the popover)", async () => {
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    await user.type(screen.getByLabelText("종목 코드"), "005");
    await flushSearch();

    const option = screen.getByRole("option", { name: /삼성전자/ });
    await user.click(option);
    expect(screen.queryByRole("listbox", { name: "종목 검색 결과" })).toBeNull();

    const callsAfterPick = fetchMock.mock.calls.length;
    // Advance well past the debounce — the setSymbol from the pick must NOT
    // trigger another search (picked=true short-circuits the effect).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAfterPick);
    expect(screen.queryByRole("listbox", { name: "종목 검색 결과" })).toBeNull();
  });
});
