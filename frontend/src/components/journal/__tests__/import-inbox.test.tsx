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
import { render, cleanup, screen, within, fireEvent } from "@testing-library/react";

const hooks = vi.hoisted(() => ({
  usePendingImports: vi.fn(),
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

import { ImportInbox, thesisOk, fmtPrice } from "@/components/journal/import-inbox";
import type { PendingTradeDTO } from "@/lib/types";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

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
    expect(within(rows[0]).getByText("journal.import.buy")).toBeInTheDocument();
    expect(within(rows[0]).getByText(fmtPrice(71200, "KRW"))).toBeInTheDocument();
    expect(within(rows[0]).getByText("journal.import.reflectionMatched")).toBeInTheDocument();

    // Row 2 — USD sell, no pause.
    expect(within(rows[1]).getByText("journal.import.sell")).toBeInTheDocument();
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

  it("thesisOk enforces the 3~500 window on trimmed length", () => {
    expect(thesisOk("")).toBe(false);
    expect(thesisOk("  ab ")).toBe(false);
    expect(thesisOk("abc")).toBe(true);
    expect(thesisOk("a".repeat(500))).toBe(true);
    expect(thesisOk("a".repeat(501))).toBe(false);
  });
});
