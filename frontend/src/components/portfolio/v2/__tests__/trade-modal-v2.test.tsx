import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the network layer + toast. apiFetch is the Trade modal's POST /trades
// and PATCH /positions.
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

// Linkable pauses for the buy link line (useReflectionLink). Empty by
// default; the link test seeds one.
const linkable = vi.hoisted(() => ({ list: [] as unknown[] }));
vi.mock("@/lib/hooks", () => ({
  useLinkableReflections: (symbol: string | null) => ({
    reflections: symbol ? linkable.list : [],
    isLoading: false,
    error: undefined,
  }),
  // 매도 순간의 거울 — empty here; sell-moment.test.tsx covers the block.
  useSellMomentForTyped: () => ({ data: null, isLoading: false }),
}));

import { apiFetch } from "@/lib/api";
import { toast } from "sonner";
import { PORTFOLIO_TRADES, PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { TradeModalV2 } from "@/components/portfolio/v2/trade-modal-v2";
import type { Position } from "@/components/portfolio/types";
import { PRE_TRADE_FIRST_COPY } from "@/components/portfolio/v2/pre-trade-first-link";

const mockedFetch = vi.mocked(apiFetch);

const POSITION: Position = {
  id: "pos-1",
  symbol: "AAPL",
  name: "Apple Inc.",
  shares: 10,
  avgCost: 120,
  current: 150,
  notes: "",
  side: "Long",
  sector: "Technology",
  purchaseDate: "2024-01-01",
};

describe("TradeModalV2 — buy/sell record-only (2026-10-13)", () => {
  beforeEach(() => {
    linkable.list = [];
    mockedFetch.mockReset();
    vi.mocked(toast.error).mockReset();
    vi.mocked(toast.success).mockReset();
  });

  it("sell: POSTs /trades directly with no friction; empty thesis allowed", async () => {
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

    // sell prefills price with position.current — clear before typing.
    fireEvent.change(screen.getByPlaceholderText("0"), { target: { value: "4" } });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "155" } });
    // No thesis typed — the memo is optional.

    await user.click(screen.getByRole("button", { name: /기록하기/ }));

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
    expect(screen.queryByText("먼저, 질문 일곱 개.")).toBeNull();
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("buy: POSTs /trades directly with action=buy and no friction", async () => {
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

    await user.click(screen.getByRole("button", { name: /기록하기/ }));

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const [url, opts] = mockedFetch.mock.calls[0];
    expect(url).toBe(PORTFOLIO_TRADES);
    expect(JSON.parse((opts as RequestInit).body as string)).toMatchObject({
      action: "buy",
      quantity: 5,
      price: 160,
    });
    expect(screen.queryByText("먼저, 질문 일곱 개.")).toBeNull();
  });

  it("sell guard: cannot trim more than shares held", async () => {
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

    await user.click(screen.getByRole("button", { name: /기록하기/ }));

    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(
      "보유 수량(10주)보다 많이 정리할 수 없습니다.",
    );
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("edit: commits directly via PATCH (unchanged)", async () => {
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

    await user.click(
      screen.getByRole("button", { name: /기록 수정/ }),
    );

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const [url, opts] = mockedFetch.mock.calls[0];
    expect(url).toBe(`${PORTFOLIO_POSITIONS}/pos-1`);
    expect((opts as RequestInit).method).toBe("PATCH");
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body).toHaveProperty("avg_cost", 120);
    expect(screen.queryByText("먼저, 질문 일곱 개.")).toBeNull();
  });

  it("buy: a recent pause on the ticker is linked by default (reflection_id)", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue({});
    linkable.list = [
      {
        id: 7,
        intended_ticker: "AAPL",
        intended_side: null,
        intended_shares: null,
        rationale: "실적 발표 뒤 가이던스 상향을 확인함",
        devil_advocate_seen: null,
        market_volatility_at_request: null,
        cooldown_started_at: new Date().toISOString(),
        cooldown_ends_at: null,
        proceeded_at: null,
        cancelled_at: null,
        auto_extended_reason: null,
        seconds_remaining: 0,
        status: "proceeded",
      },
    ];

    render(
      <TradeModalV2
        open
        action="buy"
        position={POSITION}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    expect(screen.getByTestId("reflection-link-line")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("0"), { target: { value: "5" } });
    fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "160" } });
    await user.click(screen.getByRole("button", { name: /기록하기/ }));

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const body = JSON.parse((mockedFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body).toMatchObject({ action: "buy", reflection_id: 7 });
  });
});

describe("TradeModalV2 — no mode toggle; /pre-trade link on buy only", () => {
  beforeEach(() => {
    linkable.list = [];
  });

  it("buy: no toggle, one link to /pre-trade", () => {
    render(
      <TradeModalV2 open action="buy" position={POSITION} onClose={vi.fn()} onSuccess={vi.fn()} />,
    );
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(screen.queryByRole("radio")).toBeNull();
    const link = screen.getByRole("link", { name: PRE_TRADE_FIRST_COPY });
    expect(link.getAttribute("href")).toBe("/pre-trade");
  });

  it.each(["sell", "edit"] as const)("%s: no toggle and no /pre-trade link", (action) => {
    render(
      <TradeModalV2 open action={action} position={POSITION} onClose={vi.fn()} onSuccess={vi.fn()} />,
    );
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByTestId("pre-trade-first-link")).toBeNull();
  });
});
