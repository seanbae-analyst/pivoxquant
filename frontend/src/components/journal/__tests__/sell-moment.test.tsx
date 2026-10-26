/**
 * sell-moment.test.tsx — 매도 순간의 거울 (2026-10-15).
 *
 * The block shows the user's own earlier words (with date + where they came
 * from) and the facts line; it renders nothing when there is nothing; the
 * import inbox shows it for a waiting 매도 row only; the portfolio sell
 * modal shows it once shares and price are typed.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen, fireEvent, act } from "@testing-library/react";

const hooks = vi.hoisted(() => ({
  useSellMomentForPending: vi.fn(),
  useSellMomentForTyped: vi.fn(),
  useLinkableReflections: () => ({ reflections: [], isLoading: false, error: undefined }),
}));
vi.mock("@/lib/hooks", () => hooks);
vi.mock("@/lib/locale", () => ({
  useT: () => (k: string) => k,
  useLocale: () => ({ locale: "ko" }),
}));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status = 0;
  }
  return { apiFetch: vi.fn(), ApiError };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import {
  SellMomentBlock,
  factsLine,
  quoteDate,
  signedPct,
} from "@/components/journal/sell-moment";
import { PendingTradeRow } from "@/components/journal/import-inbox";
import { TradeModalV2 } from "@/components/portfolio/v2/trade-modal-v2";
import type { PendingTradeDTO, SellMomentResponse } from "@/lib/types";
import type { Position } from "@/components/portfolio/types";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

const MOMENT: SellMomentResponse = {
  ok: true,
  ticker: "005930.KS",
  words: [
    {
      source: "fill_reason", ticker: "005930.KS", text: "HBM 공급 계약을 보고 산다",
      invalidation: null, at: "2026-09-01T02:00:00",
    },
    {
      source: "research", ticker: "005930.KS", text: "메모리 가격이 반등한다",
      invalidation: "재고가 두 분기 연속 늘어난다", at: "2025-12-20T03:00:00",
    },
  ],
  held_days: 34,
  vs_cost_pct: -4.04,
  matched_shares: 4,
};

const EMPTY: SellMomentResponse = {
  ok: true, ticker: "005930.KS", words: [], held_days: null, vs_cost_pct: null, matched_shares: 0,
};

describe("<SellMomentBlock />", () => {
  it("shows each quote with its date and source, then the facts", () => {
    render(<SellMomentBlock data={MOMENT} sellShares={4} />);
    expect(screen.getByText("이 종목에 적어 둔 말")).toBeTruthy();
    expect(screen.getAllByTestId("sell-moment-quote")).toHaveLength(2);
    expect(screen.getByText("HBM 공급 계약을 보고 산다")).toBeTruthy();
    expect(screen.getByText(/체결 이유/)).toBeTruthy();
    expect(screen.getByText(/2025년 12월 20일 · 리서치/)).toBeTruthy();
    expect(screen.getByText("재고가 두 분기 연속 늘어난다")).toBeTruthy();
    expect(screen.getByTestId("sell-moment-facts").textContent).toBe("34일 보유 · 산 값 대비 −4.0%");
  });

  it("renders nothing when there is nothing to show", () => {
    const { container } = render(<SellMomentBlock data={EMPTY} />);
    expect(container.innerHTML).toBe("");
    const none = render(<SellMomentBlock data={null} />);
    expect(none.container.innerHTML).toBe("");
    // Demo mode answers `{}` — nothing, not a crash.
    const bare = render(<SellMomentBlock data={{} as SellMomentResponse} />);
    expect(bare.container.innerHTML).toBe("");
  });

  it("facts alone still show, without the quote heading", () => {
    render(<SellMomentBlock data={{ ...EMPTY, held_days: 0 }} />);
    expect(screen.queryByText("이 종목에 적어 둔 말")).toBeNull();
    expect(screen.getByTestId("sell-moment-facts").textContent).toBe("하루 미만 보유");
  });

  it("says when only part of the sell matched recorded lots", () => {
    expect(factsLine({ ...MOMENT, matched_shares: 2.5 }, 4)).toBe(
      "34일 보유 · 산 값 대비 −4.0% · 기록된 2.5주 기준",
    );
  });

  it("formats sign and dates plainly", () => {
    expect(signedPct(12.34)).toBe("+12.3%");
    expect(signedPct(0)).toBe("0.0%");
    // The sign follows the shown value (2026-10-21).
    expect(signedPct(-0.04)).toBe("0.0%");
    expect(signedPct(-0.06)).toBe("−0.1%");
    // 2026-09-30 16:00 UTC is 10월 1일 in KST.
    expect(quoteDate("2026-09-30T16:00:00", 2026)).toBe("10월 1일");
  });
});

function pending(over: Partial<PendingTradeDTO> = {}): PendingTradeDTO {
  return {
    id: 41, batch_id: 7, source: "webhook", needs_confirm: false,
    ticker: "005930.KS", name: "삼성전자", action: "SELL", shares: 4, price: 66500,
    currency: "KRW", traded_at: "2026-10-05T01:00:00", confidence: 1, status: "pending",
    needs_ticker: false, pre_trade_reflection_id: null, raw_snippet: null,
    approved_trade_id: null, approved_at: null,
    ...over,
  } as PendingTradeDTO;
}

describe("import inbox — 매도 row", () => {
  it("shows the block above the reason box for a waiting sell", () => {
    hooks.useSellMomentForPending.mockReturnValue({ data: MOMENT, isLoading: false });
    render(<PendingTradeRow row={pending()} onChanged={() => {}} />);
    expect(hooks.useSellMomentForPending).toHaveBeenCalledWith(41);
    expect(screen.getByTestId("sell-moment")).toBeTruthy();
  });

  it("does not ask for it on a buy row", () => {
    hooks.useSellMomentForPending.mockReturnValue({ data: MOMENT, isLoading: false });
    render(<PendingTradeRow row={pending({ action: "BUY" })} onChanged={() => {}} />);
    expect(hooks.useSellMomentForPending).not.toHaveBeenCalled();
    expect(screen.queryByTestId("sell-moment")).toBeNull();
  });
});

const POSITION: Position = {
  id: "pos-1", symbol: "005930.KS", name: "삼성전자", shares: 10, avgCost: 70000,
  current: 0, notes: "", side: "Long", sector: "Tech", purchaseDate: "2026-09-01", currency: "KRW",
};

describe("portfolio sell modal", () => {
  it("shows the block once shares and price are typed", () => {
    vi.useFakeTimers();
    hooks.useSellMomentForTyped.mockImplementation((sell: unknown) => ({
      data: sell ? MOMENT : null,
      isLoading: false,
    }));
    render(<TradeModalV2 open action="sell" position={POSITION} onClose={() => {}} />);
    expect(screen.queryByTestId("sell-moment")).toBeNull();
    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[0], { target: { value: "4" } });
    fireEvent.change(inputs[1], { target: { value: "66500" } });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.getByTestId("sell-moment")).toBeTruthy();
    const last = hooks.useSellMomentForTyped.mock.calls.at(-1)?.[0];
    expect(last).toMatchObject({ ticker: "005930.KS", shares: 4, price: 66500, currency: "KRW" });
  });

  it("is not on the add-to-position modal", () => {
    hooks.useSellMomentForTyped.mockReturnValue({ data: MOMENT, isLoading: false });
    render(<TradeModalV2 open action="buy" position={POSITION} onClose={() => {}} />);
    expect(screen.queryByTestId("sell-moment")).toBeNull();
  });
});
