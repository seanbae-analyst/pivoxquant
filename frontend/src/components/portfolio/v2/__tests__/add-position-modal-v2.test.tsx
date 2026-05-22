import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the network layer + toast. apiFetch is shared by the Add modal
// (POST /positions) and the friction core (POST /pre-trade/*).
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

import { apiFetch } from "@/lib/api";
import { toast } from "sonner";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { AddPositionModalV2 } from "@/components/portfolio/v2/add-position-modal-v2";

const mockedFetch = vi.mocked(apiFetch);

async function fillCoreFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText("AAPL · 005930.KS"), "AAPL");
  await user.type(screen.getByPlaceholderText("0"), "10");
  await user.type(screen.getByPlaceholderText("0.00"), "150");
}

describe("AddPositionModalV2 — mode split (FIX 1/2)", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    vi.mocked(toast.error).mockReset();
    vi.mocked(toast.success).mockReset();
  });

  it("HOLDING mode (default): POSTs directly with purchase_date and no friction", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});
    const onSuccess = vi.fn();
    const onClose = vi.fn();

    render(<AddPositionModalV2 open onClose={onClose} onSuccess={onSuccess} />);

    // Default mode is HOLDING — record button, optional memo.
    expect(screen.getByText("이미 보유 중 · 기록만")).toBeTruthy();

    await fillCoreFields(user);
    // Backdate the purchase date.
    const dateInput = screen.getByLabelText(
      "매수일 · Purchase date",
    ) as HTMLInputElement;
    // type=date in jsdom: set the value via change rather than keystrokes.
    fireEvent.change(dateInput, { target: { value: "2025-03-15" } });

    await user.click(screen.getByRole("button", { name: /Record · 기록/ }));

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
    expect(screen.queryByText("Seven questions first.")).toBeNull();
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("NEW_ENTRY mode: requires thesis and opens the 7-question reflection (no direct POST)", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});

    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("radio", { name: "신규 진입 검토 · 7문항" }));
    await fillCoreFields(user);

    // Thesis ≥50 chars required in NEW mode (this string is well over 50).
    fireEvent.change(
      screen.getByPlaceholderText("왜 지금 이 종목에 들어가는가? 한 문단으로 정직하게."),
      {
        target: {
          value:
            "강한 펀더멘털과 모멘텀이 동시에 확인되어 장기 보유 관점에서 진입한다. 밸류에이션도 합리적이며 리스크 대비 보상이 충분하다고 판단한다.",
        },
      },
    );

    await user.click(screen.getByRole("button", { name: /Continue · 7 questions/ }));

    // Friction modal opens — no position POST yet.
    await waitFor(() => expect(screen.getByText("Seven questions first.")).toBeTruthy());
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("constrains the purchase date to today (max attr) and defaults to today", () => {
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    const dateInput = screen.getByLabelText(
      "매수일 · Purchase date",
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

  function jsonResponse(results: unknown[]) {
    return {
      ok: true,
      status: 200,
      json: async () => ({ results }),
    } as unknown as Response;
  }

  beforeEach(() => {
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
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("debounced-searches on input and renders suggestion names + tickers", async () => {
    const user = userEvent.setup();
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    await user.type(screen.getByLabelText("Symbol"), "005");

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain("/api/search?q=");
    expect(calledUrl).toContain("limit=6");

    // Suggestion list renders the company name (bold) + ticker.
    await waitFor(() => expect(screen.getByText("삼성전자")).toBeTruthy());
    expect(screen.getByText("Apple Inc.")).toBeTruthy();
    expect(screen.getByRole("listbox", { name: "종목 검색 결과" })).toBeTruthy();
  });

  it("clicking a suggestion fills the canonical ticker and closes the popover", async () => {
    const user = userEvent.setup();
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    const input = screen.getByLabelText("Symbol") as HTMLInputElement;
    await user.type(input, "005");
    const option = await screen.findByRole("option", { name: /삼성전자/ });

    await user.click(option);

    // Canonical ticker is written into the input; popover is gone.
    await waitFor(() => expect(input.value).toBe("005930.KS"));
    expect(screen.queryByRole("listbox", { name: "종목 검색 결과" })).toBeNull();
    // Resolved name confirmation is shown.
    await waitFor(() => expect(screen.getByText("삼성전자")).toBeTruthy());
  });

  it("does not re-search after a pick (picked suppresses the popover)", async () => {
    const user = userEvent.setup();
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);

    await user.type(screen.getByLabelText("Symbol"), "005");
    const option = await screen.findByRole("option", { name: /삼성전자/ });
    await user.click(option);
    await waitFor(() =>
      expect(screen.queryByRole("listbox", { name: "종목 검색 결과" })).toBeNull(),
    );

    const callsAfterPick = fetchMock.mock.calls.length;
    // The setSymbol from the pick must NOT trigger another search.
    await new Promise((r) => setTimeout(r, 400));
    expect(fetchMock.mock.calls.length).toBe(callsAfterPick);
    expect(screen.queryByRole("listbox", { name: "종목 검색 결과" })).toBeNull();
  });
});
