/**
 * 최근 활동 on a phone (2026-10-10, CEO "앱처럼"): no boxed card — the trades
 * grouped under KST day headers, like a banking statement. Same labels
 * (legal-safe 추가 / 정리 vocabulary, holding-seed label), same signed
 * amounts. Desktop keeps the card.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import { LocaleProvider } from "@/lib/locale";
import type { TransactionRow } from "../hooks-v2";

const rows = vi.hoisted(() => ({
  value: [] as Array<Record<string, unknown>>,
  loading: false,
}));

vi.mock("../hooks-v2", () => ({
  useTransactions: () => ({
    data: rows.loading ? undefined : { trades: rows.value },
    isLoading: rows.loading,
    error: undefined,
  }),
}));

import { RecentTransactionsBlock, groupByDay, kstDayKey } from "../recent-transactions-block";

const TRADES: TransactionRow[] = [
  // 2026-06-15 01:05Z and 06:00Z are both 2026-06-15 in Seoul.
  { id: 3, date: "2026-06-15T01:05:00Z", symbol: "NVDA", name: "NVIDIA", side: "buy", shares: 15, price: 176.2, amount: 2643, currency: "USD" },
  { id: 2, date: "2026-06-15T06:00:00Z", symbol: "AAPL", name: "Apple", side: "sell", shares: 2, price: 200, amount: 400, currency: "USD" },
  // 2026-06-10 16:30Z is already 2026-06-11 01:30 in Seoul.
  { id: 1, date: "2026-06-10T16:30:00Z", symbol: "005930", name: "삼성전자", side: "buy", shares: 50, price: 81000, amount: 4_050_000, currency: "KRW" },
];

function setPhone(on: boolean) {
  window.matchMedia = ((q: string) => ({
    matches: on && q === "(max-width: 767px)",
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia;
}
const original = window.matchMedia;

afterEach(() => {
  cleanup();
  window.matchMedia = original;
  rows.loading = false;
});

describe("groupByDay / kstDayKey", () => {
  it("groups consecutive rows by their Seoul calendar day", () => {
    expect(kstDayKey("2026-06-10T16:30:00Z")).toBe("2026-06-11");
    expect(groupByDay(TRADES).map((g) => [g.key, g.rows.length])).toEqual([
      ["2026-06-15", 2],
      ["2026-06-11", 1],
    ]);
  });
});

describe("RecentTransactionsBlock on a phone", () => {
  it("renders day groups with the same labels and signed amounts", () => {
    setPhone(true);
    rows.value = TRADES as Array<Record<string, unknown>>;
    render(
      <LocaleProvider>
        <RecentTransactionsBlock limit={6} />
      </LocaleProvider>,
    );
    const groups = within(screen.getByTestId("activity-phone")).getAllByRole("group");
    expect(groups).toHaveLength(2);
    expect(groups[0]).toHaveAccessibleName("6월 15일 (월)");
    expect(groups[1]).toHaveAccessibleName("6월 11일 (목)");

    const all = screen.getAllByTestId("activity-row");
    expect(all).toHaveLength(3);
    expect(all[0].textContent).toContain("추가");
    expect(all[0].textContent).toContain("−USD 2,643.00");
    expect(all[1].textContent).toContain("정리");
    expect(all[1].textContent).toContain("+USD 400.00");
    expect(all[2].textContent).toContain("삼성전자");
    // Never the banned trade verbs.
    expect(screen.getByTestId("activity-phone").textContent).not.toMatch(/매수|매도|BUY|SELL/); // legal-ok
  });

  it("loading shows skeleton rows and a status", () => {
    setPhone(true);
    rows.loading = true;
    render(
      <LocaleProvider>
        <RecentTransactionsBlock limit={6} />
      </LocaleProvider>,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByTestId("activity-row")).toBeNull();
  });

  it("desktop keeps the card (no day groups)", () => {
    setPhone(false);
    rows.value = TRADES as Array<Record<string, unknown>>;
    render(
      <LocaleProvider>
        <RecentTransactionsBlock limit={6} />
      </LocaleProvider>,
    );
    expect(screen.queryByTestId("activity-phone")).toBeNull();
    expect(screen.getByText("최근 활동")).toBeInTheDocument();
  });
});
