import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock network + toast. The friction core hits /pre-trade/start then
// /pre-trade/<id>/proceed.
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
import { API } from "@/lib/endpoints";
import { PreTradeFrictionModal } from "@/components/pre-trade/pre-trade-friction-modal";

const mockedFetch = vi.mocked(apiFetch);

// A reflection that is already ready (backend cooldown = 0, 2026-05-22).
function readyReflection(status: "ready" | "proceeded") {
  return {
    reflection: {
      id: 42,
      intended_ticker: "AAPL",
      intended_side: "ENTRY",
      intended_shares: 10,
      rationale: "long thesis here, well over fifty characters for the gate.",
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

describe("Pre-Trade Friction — cooldown 0 auto-proceed (FIX 3)", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
  });

  it("skips the countdown screen and auto-proceeds when reflection is immediately ready", async () => {
    const user = userEvent.setup();
    // /start → ready (seconds_remaining 0), /proceed → proceeded.
    mockedFetch.mockImplementation((url: string) => {
      if (url === API.preTrade.start) return Promise.resolve(readyReflection("ready"));
      if (url === API.preTrade.proceed(42)) return Promise.resolve(readyReflection("proceeded"));
      return Promise.reject(new Error(`unexpected url ${url}`));
    });

    const onProceed = vi.fn().mockResolvedValue(undefined);

    render(
      <PreTradeFrictionModal
        open
        side="ENTRY"
        ticker="AAPL"
        shares="10"
        rationale="long thesis here, well over fifty characters for the gate."
        onProceed={onProceed}
        onClose={vi.fn()}
      />,
    );

    // Acknowledge all 7 questions.
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBe(7);
    for (const cb of checkboxes) await user.click(cb);

    await user.click(screen.getByRole("button", { name: /Start cooldown/ }));

    // onProceed (host journal commit) fires automatically — no extra click.
    await waitFor(() => expect(onProceed).toHaveBeenCalledTimes(1));

    // The 00:00 countdown UI must never appear.
    expect(screen.queryByText("00:00")).toBeNull();
    expect(screen.queryByText(/Time remaining/)).toBeNull();

    // Terminal recap is shown instead.
    await waitFor(() => expect(screen.getByText("Close · 닫기")).toBeTruthy());

    // /start and /proceed both called; no /status polling needed.
    const urls = mockedFetch.mock.calls.map((c) => c[0]);
    expect(urls).toContain(API.preTrade.start);
    expect(urls).toContain(API.preTrade.proceed(42));
  });
});
