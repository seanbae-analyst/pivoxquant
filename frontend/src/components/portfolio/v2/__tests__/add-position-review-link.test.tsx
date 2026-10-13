import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Recording a position bought after a pause links it to that pause.
// 2026-09-29 the in-modal 7-question entry sent the pause it had just stamped
// as `reflection_id` with POST /positions. 2026-10-13 (CEO) that mode is gone
// — the pause lives only on /pre-trade, before buying — so the record-only
// modal offers the most recent linkable pause for the ticker instead
// (<ReflectionLinkLine />, default ON), the same way the trade modal does for
// a buy. Not offered for a purchase date before the pause, nor in onboarding.

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

// Linkable pauses keyed by ticker — empty unless a case seeds one.
const linkable = vi.hoisted(() => ({ byTicker: {} as Record<string, unknown[]> }));
vi.mock("@/lib/hooks", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/hooks")>()),
  useLinkableReflections: (ticker: string | null) => ({
    reflections: (ticker && linkable.byTicker[ticker]) || [],
    isLoading: false,
    error: undefined,
  }),
}));

import { apiFetch } from "@/lib/api";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { AddPositionModalV2 } from "@/components/portfolio/v2/add-position-modal-v2";

const mockedFetch = vi.mocked(apiFetch);
const DAY_MS = 86_400_000;

function pause(id: number, daysAgo: number) {
  return {
    id,
    intended_ticker: "AAPL",
    intended_side: null,
    intended_shares: null,
    rationale: "실적 발표 뒤 가이던스 상향을 확인함",
    devil_advocate_seen: null,
    market_volatility_at_request: null,
    cooldown_started_at: new Date(Date.now() - daysAgo * DAY_MS).toISOString(),
    cooldown_ends_at: null,
    proceeded_at: null,
    cancelled_at: null,
    auto_extended_reason: null,
    seconds_remaining: 0,
    status: "proceeded",
  };
}

// fireEvent (not userEvent typing) keeps these off the wall clock under
// parallel-suite contention.
function fillCore() {
  fireEvent.change(screen.getByPlaceholderText("AAPL · 005930.KS"), { target: { value: "AAPL" } });
  fireEvent.change(screen.getByPlaceholderText("0"), { target: { value: "10" } });
  fireEvent.change(screen.getByPlaceholderText("0.00"), { target: { value: "150" } });
}

function postedBody(): Record<string, unknown> {
  const [url, opts] = mockedFetch.mock.calls[0];
  expect(url).toBe(PORTFOLIO_POSITIONS);
  return JSON.parse((opts as RequestInit).body as string);
}

describe("AddPositionModalV2 — pause link on the position POST", () => {
  beforeEach(() => {
    linkable.byTicker = {};
    mockedFetch.mockReset();
    mockedFetch.mockResolvedValue({});
  });

  it("no pause for the ticker: no line, no reflection_id", async () => {
    const user = userEvent.setup();
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);
    fillCore();
    await user.click(screen.getByRole("button", { name: /기록하기/ }));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("reflection-link-line")).toBeNull();
    const body = postedBody();
    expect(body).toMatchObject({ symbol: "AAPL", quantity: 10, price: 150 });
    expect(body).not.toHaveProperty("reflection_id");
  });

  it("recent pause: the line is offered (checked) and reflection_id is sent", async () => {
    linkable.byTicker.AAPL = [pause(42, 2)];
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<AddPositionModalV2 open onClose={onClose} onSuccess={vi.fn()} />);
    fillCore();
    const line = await screen.findByTestId("reflection-link-line");
    expect((line.querySelector('input[type="checkbox"]') as HTMLInputElement).checked).toBe(true);

    await user.click(screen.getByRole("button", { name: /기록하기/ }));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    expect(postedBody()).toMatchObject({ symbol: "AAPL", reflection_id: 42 });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("unchecked: no reflection_id", async () => {
    linkable.byTicker.AAPL = [pause(42, 2)];
    const user = userEvent.setup();
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);
    fillCore();
    const line = await screen.findByTestId("reflection-link-line");
    await user.click(line.querySelector('input[type="checkbox"]') as HTMLInputElement);

    await user.click(screen.getByRole("button", { name: /기록하기/ }));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    expect(postedBody()).not.toHaveProperty("reflection_id");
  });

  it("purchase date before the pause: line hidden, no reflection_id", async () => {
    linkable.byTicker.AAPL = [pause(42, 2)];
    const user = userEvent.setup();
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);
    fillCore();
    await screen.findByTestId("reflection-link-line");

    fireEvent.change(screen.getByLabelText("매수일"), { target: { value: "2020-01-15" } });
    expect(screen.queryByTestId("reflection-link-line")).toBeNull();

    await user.click(screen.getByRole("button", { name: /기록하기/ }));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const body = postedBody();
    expect(body).toMatchObject({ purchase_date: "2020-01-15" });
    expect(body).not.toHaveProperty("reflection_id");
  });

  it("holdingOnly (onboarding): no line, no reflection_id", async () => {
    linkable.byTicker.AAPL = [pause(42, 2)];
    const user = userEvent.setup();
    render(<AddPositionModalV2 open holdingOnly onClose={vi.fn()} onSuccess={vi.fn()} />);
    fillCore();
    // Past the lookup debounce — still nothing offered.
    await new Promise((r) => setTimeout(r, 400));
    expect(screen.queryByTestId("reflection-link-line")).toBeNull();

    await user.click(screen.getByRole("button", { name: /기록하기/ }));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    expect(postedBody()).not.toHaveProperty("reflection_id");
  });
});
