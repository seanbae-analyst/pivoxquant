import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the network layer + toast. apiFetch is shared by the Trade modal
// (POST /trades, PATCH /positions) and the friction core (POST /pre-trade/*).
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
import { PORTFOLIO_TRADES, PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { TradeModalV2 } from "@/components/portfolio/v2/trade-modal-v2";
import type { Position } from "@/components/portfolio/types";

const mockedFetch = vi.mocked(apiFetch);

const POSITION: Position = {
  id: "pos-1",
  symbol: "AAPL",
  name: "Apple Inc.",
  shares: 10,
  avgCost: 120,
  current: 150,
  notes: "",
};

const LONG_THESIS =
  "강한 펀더멘털과 모멘텀이 동시에 확인되어 장기 보유 관점에서 진입한다. 밸류에이션도 합리적이며 리스크 대비 보상이 충분하다고 판단한다.";

describe("TradeModalV2 — buy/sell mode split", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    vi.mocked(toast.error).mockReset();
    vi.mocked(toast.success).mockReset();
  });

  it("sell RECORD mode (default): POSTs /trades directly with no friction; empty thesis allowed", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});
    const onSuccess = vi.fn();
    const onClose = vi.fn();

    render(
      <TradeModalV2
        open
        action="sell"
        position={POSITION}
        onClose={onClose}
        onSuccess={onSuccess}
      />,
    );

    // Default mode is RECORD — toggle visible, record CTA.
    expect(screen.getByText("이미 체결됨 · 기록만")).toBeTruthy();

    // sell prefills price with position.current — clear before typing.
    fireEvent.change(screen.getByPlaceholderText("0"), { target: { value: "4" } });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "155" } });
    // No thesis typed — RECORD allows an empty memo.

    await user.click(screen.getByRole("button", { name: /Record · 기록/ }));

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    const [url, opts] = mockedFetch.mock.calls[0];
    expect(url).toBe(PORTFOLIO_TRADES);
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body).toMatchObject({
      position_id: "pos-1",
      action: "sell",
      quantity: 4,
      price: 155,
      note: "",
    });

    // No 7-question reflection appeared.
    expect(screen.queryByText("Seven questions first.")).toBeNull();
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("sell REVIEW mode: requires thesis and opens the 7-question reflection (no direct POST)", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});

    render(
      <TradeModalV2
        open
        action="sell"
        position={POSITION}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("radio", { name: "신규 검토 · 7문항" }));
    fireEvent.change(screen.getByPlaceholderText("0"), { target: { value: "4" } });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "155" } });

    fireEvent.change(
      screen.getByPlaceholderText("왜 지금 이 결정을 하는가? 한 문단으로 정직하게."),
      { target: { value: LONG_THESIS } },
    );

    await user.click(
      screen.getByRole("button", { name: /Continue · 7 questions/ }),
    );

    // Friction modal opens — no trade POST yet.
    await waitFor(() =>
      expect(screen.getByText("Seven questions first.")).toBeTruthy(),
    );
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("buy RECORD mode: POSTs /trades directly with action=buy and no friction", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});

    render(
      <TradeModalV2
        open
        action="buy"
        position={POSITION}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("0"), { target: { value: "5" } });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "160" } });

    await user.click(screen.getByRole("button", { name: /Record · 기록/ }));

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const [url, opts] = mockedFetch.mock.calls[0];
    expect(url).toBe(PORTFOLIO_TRADES);
    expect(JSON.parse((opts as RequestInit).body as string)).toMatchObject({
      action: "buy",
      quantity: 5,
      price: 160,
    });
    expect(screen.queryByText("Seven questions first.")).toBeNull();
  });

  it("sell guard: cannot trim more than shares held (applies in RECORD mode)", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});

    render(
      <TradeModalV2
        open
        action="sell"
        position={POSITION}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("0"), { target: { value: "99" } }); // > 10 held
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "155" } });

    await user.click(screen.getByRole("button", { name: /Record · 기록/ }));

    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(
      "Cannot trim more than 10 shares held.",
    );
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("edit: no mode toggle, commits directly via PATCH (unchanged)", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});
    const onClose = vi.fn();

    render(
      <TradeModalV2
        open
        action="edit"
        position={POSITION}
        onClose={onClose}
        onSuccess={vi.fn()}
      />,
    );

    // edit has no mode concept — toggle hidden.
    expect(screen.queryByText("이미 체결됨 · 기록만")).toBeNull();
    expect(screen.queryByText("신규 검토 · 7문항")).toBeNull();

    await user.click(
      screen.getByRole("button", { name: /Update observation/ }),
    );

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const [url, opts] = mockedFetch.mock.calls[0];
    expect(url).toBe(`${PORTFOLIO_POSITIONS}/pos-1`);
    expect((opts as RequestInit).method).toBe("PATCH");
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body).toHaveProperty("avg_cost", 120);
    expect(screen.queryByText("Seven questions first.")).toBeNull();
  });
});
