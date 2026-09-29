/**
 * import-inbox.test.tsx — DOM render coverage for the Import Inbox card.
 *
 * Mirrors the mocking approach in mirror-render.test.tsx: the SWR hook and
 * the locale are mocked so the test drives the component's branches directly
 * (`useT` is a passthrough, so assertions target i18n keys + data-derived
 * output, not copy). `apiFetch` is mocked so no request leaves the test.
 *
 * Covers the two contract points from docs/product/IMPORT_INBOX_DESIGN.md
 * §테스트: (1) pending rows render, (2) approve is disabled until the thesis
 * has at least 3 characters.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen, within, fireEvent, act } from "@testing-library/react";

const hooks = vi.hoisted(() => ({
  usePendingImports: vi.fn(),
  useLinkableReflections: vi.fn(),
}));
vi.mock("@/lib/hooks", () => hooks);
vi.mock("@/lib/locale", () => ({
  useT: () => (k: string) => k,
  useLocale: () => ({ locale: "ko" }),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { ImportInbox, thesisOk, fmtPrice } from "@/components/journal/import-inbox";
import { sideLabel } from "@/lib/pre-trade";

const apiFetchMock = vi.mocked(apiFetch);
import type { PendingTradeDTO, PreTradeReflection } from "@/lib/types";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  hooks.useLinkableReflections.mockReset();
});

function linkable(reflections: PreTradeReflection[] = []) {
  hooks.useLinkableReflections.mockImplementation((ticker: string | null) => ({
    reflections: ticker ? reflections : [],
    isLoading: false,
    error: undefined,
  }));
}

function refl(id: number, over: Partial<PreTradeReflection> = {}): PreTradeReflection {
  return {
    id,
    intended_ticker: "005930.KS",
    intended_side: null,
    intended_shares: null,
    rationale: "반도체 업황 회복을 보고 들어간다",
    devil_advocate_seen: null,
    market_volatility_at_request: null,
    cooldown_started_at: new Date(Date.now() - 2 * 86_400_000).toISOString(),
    cooldown_ends_at: null,
    proceeded_at: null,
    cancelled_at: null,
    auto_extended_reason: null,
    seconds_remaining: 0,
    status: "proceeded",
    ...over,
  };
}

const ROWS: PendingTradeDTO[] = [
  {
    id: 11,
    batch_id: 1,
    ticker: "005930.KS",
    name: "삼성전자",
    action: "BUY",
    shares: 10,
    price: 71200,
    currency: "KRW",
    traded_at: "2026-09-12T00:31:00Z",
    confidence: 0.9,
    status: "pending",
    needs_ticker: false,
    pre_trade_reflection_id: 7,
    raw_snippet: "삼성전자 10주 매수 체결 71,200원",
    approved_trade_id: null,
    approved_at: null,
  },
  {
    id: 12,
    batch_id: 1,
    ticker: "AAPL",
    name: "Apple Inc.",
    action: "SELL",
    shares: 3,
    price: 189.2,
    currency: "USD",
    traded_at: "2026-09-11T14:05:00Z",
    confidence: 0.8,
    status: "pending",
    needs_ticker: false,
    pre_trade_reflection_id: null,
    raw_snippet: "Sold 3 AAPL @ $189.20",
    approved_trade_id: null,
    approved_at: null,
  },
];

function loaded(pending: PendingTradeDTO[]) {
  if (!hooks.useLinkableReflections.getMockImplementation()) linkable([]);
  hooks.usePendingImports.mockReturnValue({
    pending,
    count: pending.length,
    isLoading: false,
    error: undefined,
    mutate: vi.fn(),
  });
}

describe("ImportInbox", () => {
  it("renders nothing on a hard error (never breaks the journal)", () => {
    hooks.usePendingImports.mockReturnValue({
      pending: [],
      count: 0,
      isLoading: false,
      error: new Error("5xx"),
      mutate: vi.fn(),
    });
    const { container } = render(<ImportInbox />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the one-line import link when nothing is pending", () => {
    loaded([]);
    render(<ImportInbox />);
    expect(screen.queryAllByTestId("pending-trade-row")).toHaveLength(0);
    expect(screen.getByRole("link", { name: "journal.import.importLink" })).toHaveAttribute(
      "href",
      "/journal/import",
    );
  });

  it("renders two pending rows with facts and the pause status", () => {
    loaded(ROWS);
    const { container } = render(<ImportInbox />);
    const rows = screen.getAllByTestId("pending-trade-row");
    expect(rows).toHaveLength(2);

    // Row 1 — KRW buy with a matching pause record.
    expect(within(rows[0]).getByText("삼성전자")).toBeInTheDocument();
    expect(within(rows[0]).getByText(sideLabel("BUY"))).toBeInTheDocument();
    expect(within(rows[0]).getByText(fmtPrice(71200, "KRW"))).toBeInTheDocument();
    expect(within(rows[0]).getByText("journal.import.reflectionMatched")).toBeInTheDocument();

    // Row 2 — USD sell, no pause.
    expect(within(rows[1]).getByText(sideLabel("SELL"))).toBeInTheDocument();
    expect(within(rows[1]).getByText(fmtPrice(189.2, "USD"))).toBeInTheDocument();
    expect(within(rows[1]).getByText("journal.import.reflectionNone")).toBeInTheDocument();

    // Raw side codes never reach the screen; no degenerate numbers leak.
    expect(container.textContent ?? "").not.toMatch(/\bBUY\b|\bSELL\b|NaN|undefined|null/);
  });

  it("keeps approve disabled until the thesis is at least 3 characters", () => {
    loaded(ROWS);
    render(<ImportInbox />);
    const row = screen.getAllByTestId("pending-trade-row")[0];
    const approve = within(row).getByRole("button", { name: "journal.import.approve" });
    const thesis = within(row).getByLabelText("journal.import.thesisLabel");

    expect(approve).toBeDisabled();

    fireEvent.change(thesis, { target: { value: "ab" } });
    expect(approve).toBeDisabled();

    fireEvent.change(thesis, { target: { value: "실적 발표 전 분할 매수" } });
    expect(approve).toBeEnabled();

    // Whitespace does not count.
    fireEvent.change(thesis, { target: { value: "   " } });
    expect(approve).toBeDisabled();
  });

  it("does not search /api/search on mount — only after the user focuses or types", async () => {
    vi.useFakeTimers();
    try {
      apiFetchMock.mockResolvedValue({ results: [] });
      loaded([{ ...ROWS[0], id: 13, ticker: null, needs_ticker: true }]);
      render(<ImportInbox />);
      const input = screen.getByLabelText("journal.import.tickerPlaceholder");

      // Mounted with `initialQuery` prefilled: the debounce window passes, nothing fires.
      await act(async () => {
        vi.advanceTimersByTime(1_000);
      });
      expect(apiFetchMock).not.toHaveBeenCalled();

      fireEvent.focus(input);
      fireEvent.change(input, { target: { value: "삼성" } });
      await act(async () => {
        vi.advanceTimersByTime(400);
      });
      expect(apiFetchMock).toHaveBeenCalledTimes(1);
      expect(apiFetchMock.mock.calls[0][0]).toBe(API.market.search("삼성"));
    } finally {
      vi.useRealTimers();
    }
  });

  it("thesisOk enforces the 3~500 window on trimmed length", () => {
    expect(thesisOk("")).toBe(false);
    expect(thesisOk("  ab ")).toBe(false);
    expect(thesisOk("abc")).toBe(true);
    expect(thesisOk("a".repeat(500))).toBe(true);
    expect(thesisOk("a".repeat(501))).toBe(false);
  });
});

describe("ImportInbox — buy ↔ pause link (2026-09-29)", () => {
  async function approveRow(row: HTMLElement) {
    fireEvent.change(within(row).getByLabelText("journal.import.thesisLabel"), {
      target: { value: "반도체 업황 회복" },
    });
    await act(async () => {
      fireEvent.click(within(row).getByRole("button", { name: "journal.import.approve" }));
    });
    const call = apiFetchMock.mock.calls.find(([url]) => url === API.imports.approve(11));
    return JSON.parse((call?.[1] as RequestInit).body as string) as Record<string, unknown>;
  }

  it("shows the link line for a matched buy (default ON) and sends its id", async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    linkable([refl(9), refl(7)]);
    loaded(ROWS);
    render(<ImportInbox />);
    const rows = screen.getAllByTestId("pending-trade-row");
    const line = within(rows[0]).getByTestId("reflection-link-line");
    expect(within(line).getByRole("checkbox")).toBeChecked();
    // The import-time match (7) is preferred over the newest candidate (9).
    const body = await approveRow(rows[0]);
    expect(body).toMatchObject({ thesis: "반도체 업황 회복", reflection_id: 7 });
    // Sell rows never fetch or show a link line.
    expect(within(rows[1]).queryByTestId("reflection-link-line")).toBeNull();
    expect(hooks.useLinkableReflections).not.toHaveBeenCalledWith("AAPL");
  });

  it("unchecking sends reflection_id: null + reflection_declined (don't link, don't infer)", async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    linkable([refl(7)]);
    loaded([ROWS[0]]);
    render(<ImportInbox />);
    const row = screen.getByTestId("pending-trade-row");
    fireEvent.click(within(row).getByRole("checkbox"));
    const body = await approveRow(row);
    expect(body).toHaveProperty("reflection_id", null);
    expect(body).toHaveProperty("reflection_declined", true);
  });

  it("offers a linkable pause even without an import-time match", async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    linkable([refl(5)]);
    loaded([{ ...ROWS[0], pre_trade_reflection_id: null }]);
    render(<ImportInbox />);
    const row = screen.getByTestId("pending-trade-row");
    expect(within(row).getByTestId("reflection-link-line")).toBeInTheDocument();
    const body = await approveRow(row);
    expect(body).toMatchObject({ reflection_id: 5 });
  });

  it("without a candidate the caption stays and the key is omitted", async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    linkable([]);
    loaded([ROWS[0]]);
    render(<ImportInbox />);
    const row = screen.getByTestId("pending-trade-row");
    expect(within(row).getByText("journal.import.reflectionMatched")).toBeInTheDocument();
    const body = await approveRow(row);
    expect(body).not.toHaveProperty("reflection_id");
    expect(body).not.toHaveProperty("reflection_declined");
  });
});
