import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 2026-09-29 — "신규 진입 검토 · 7문항" is a buy made right after the pause:
// POST /positions carries the reflection id the friction modal just stamped
// (backend writes a linked recorded buy instead of a holding seed).

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

// Stand-in friction modal: one button that proceeds with a stamped id.
vi.mock("@/components/pre-trade/pre-trade-friction-modal", () => ({
  PreTradeFrictionModal: ({
    open,
    onProceed,
  }: {
    open: boolean;
    onProceed: (id: number) => Promise<void> | void;
  }) =>
    open ? (
      <button type="button" onClick={() => void onProceed(42)}>
        mock-proceed
      </button>
    ) : null,
}));

import { apiFetch } from "@/lib/api";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { AddPositionModalV2 } from "@/components/portfolio/v2/add-position-modal-v2";

const mockedFetch = vi.mocked(apiFetch);

describe("AddPositionModalV2 — review entry links the pause", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    mockedFetch.mockResolvedValue({});
  });

  it("sends the stamped reflection_id with the position POST", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<AddPositionModalV2 open onClose={onClose} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("radio", { name: "신규 진입 검토 · 7문항" }));
    await user.type(screen.getByPlaceholderText("AAPL · 005930.KS"), "AAPL");
    await user.type(screen.getByPlaceholderText("0"), "10");
    await user.type(screen.getByPlaceholderText("0.00"), "150");
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
    await user.click(screen.getByRole("button", { name: "mock-proceed" }));

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const [url, opts] = mockedFetch.mock.calls[0];
    expect(url).toBe(PORTFOLIO_POSITIONS);
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body).toMatchObject({ symbol: "AAPL", quantity: 10, price: 150, reflection_id: 42 });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("holding mode sends no reflection_id", async () => {
    const user = userEvent.setup();
    render(<AddPositionModalV2 open onClose={vi.fn()} onSuccess={vi.fn()} />);
    await user.type(screen.getByPlaceholderText("AAPL · 005930.KS"), "AAPL");
    await user.type(screen.getByPlaceholderText("0"), "10");
    await user.type(screen.getByPlaceholderText("0.00"), "150");
    await user.click(screen.getByRole("button", { name: /Record · 기록/ }));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const body = JSON.parse((mockedFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body).not.toHaveProperty("reflection_id");
  });
});
