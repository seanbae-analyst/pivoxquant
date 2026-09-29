/**
 * 보유 등록 시드 행은 매수가 아니다 (2026-09-29).
 *
 * 보유 종목을 등록하면 백엔드가 source="holding_seed" 인 BUY 행을 1줄 쓴다
 * (services/position_writes.add_holding_seed). 그 날짜는 등록일이지 매수일이
 * 아니므로, 활동 목록이 이 행을 "Add"(매수)로 적으면 언제 샀는지를 잘못 말한다.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LocaleProvider } from "@/lib/locale";
import type { TransactionRow } from "../hooks-v2";

const rows: TransactionRow[] = [
  {
    id: "1",
    date: "2026-09-20",
    symbol: "AAPL",
    name: "Apple",
    side: "Bought",
    qty: 10,
    price: 100,
    currency: "USD",
    source: "holding_seed",
  },
  {
    id: "2",
    date: "2026-09-21",
    symbol: "MSFT",
    name: "Microsoft",
    side: "Bought",
    qty: 2,
    price: 50,
    currency: "USD",
    source: null,
  },
];

vi.mock("../hooks-v2", () => ({
  useTransactions: () => ({ data: { trades: rows }, isLoading: false, error: undefined }),
}));

import { RecentTransactionsBlock } from "../recent-transactions-block";

describe("RecentTransactionsBlock — holding seed rows", () => {
  it("labels a seed row as a registration, not a buy", () => {
    render(
      <LocaleProvider>
        <RecentTransactionsBlock limit={6} />
      </LocaleProvider>,
    );
    const seedMeta = screen.getByText(/보유 등록 ·/);
    expect(seedMeta.textContent).not.toMatch(/^Add\b/);
    // 체결 행은 그대로 Add.
    expect(screen.getByText(/^Add ·/)).toBeInTheDocument();
    // 시드는 오늘의 현금 유출이 아니다 — 부호 없이.
    expect(screen.queryByText("−USD 1,000.00")).toBeNull();
    expect(screen.getByText("USD 1,000.00")).toBeInTheDocument();
    expect(screen.getByText("−USD 100.00")).toBeInTheDocument();
  });
});
