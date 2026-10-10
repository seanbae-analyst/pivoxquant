/**
 * Holdings on a phone (2026-10-07): one card per holding instead of a table
 * that scrolls sideways. Same values (shares, average cost, weight) and the
 * same row actions. Desktop and SSR keep the table.
 * 2026-10-10: the cards became native list rows (monogram, chevron) under one
 * column label, and the sheet a row opens shows the holding's figures.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PositionsTableV2 } from "@/components/portfolio/v2/positions-table-v2";
import type { Position } from "@/components/portfolio/types";

vi.mock("@/lib/locale", () => ({ useT: () => (k: string) => k }));

const POS: Position[] = [
  { id: "1", symbol: "AAPL", name: "Apple", side: "Long", shares: 10, avgCost: 100, current: 120,
    sector: "Tech", purchaseDate: "2026-01-01", currency: "USD" } as Position,
];
const POS2: Position[] = [
  ...POS,
  { id: "2", symbol: "005930", name: "삼성전자", side: "Long", shares: 2, avgCost: 70_000, current: 80_000,
    sector: "Tech", purchaseDate: "2026-01-01", currency: "KRW" } as Position,
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
});

describe("PositionsTableV2 on a phone", () => {
  it("renders cards, not a table, with the row actions", async () => {
    setPhone(true);
    const onAction = vi.fn();
    render(<PositionsTableV2 positions={POS} totalNav={1200} fxRate={1380} onAction={onAction} marketDataDisplay={false} />);
    expect(screen.queryByRole("table")).toBeNull();
    const cards = screen.getAllByTestId("position-card");
    expect(cards).toHaveLength(1);
    expect(cards[0].textContent).toContain("10주");
    expect(cards[0].textContent).toContain("평균");
    // 2026-10-09: the card is one tap target that opens an action sheet with
    // the same four actions (was four 36px buttons on the card).
    expect(screen.queryByRole("button", { name: "AAPL 정리 기록" })).toBeNull();
    await userEvent.click(screen.getByTestId("position-card-open"));
    await userEvent.click(screen.getByRole("button", { name: "AAPL 정리 기록" }));
    expect(onAction).toHaveBeenCalledWith("sell", expect.objectContaining({ symbol: "AAPL" }));
  });

  it("labels the weight cost-basis when vendor quotes are off — once, as the list's column label", () => {
    setPhone(true);
    render(<PositionsTableV2 positions={POS2} totalNav={1200} fxRate={1380} marketDataDisplay={false} />);
    // 2026-10-10: one column label for the list, not repeated on every row.
    const labels = screen.getAllByTestId("position-card-weight-basis");
    expect(labels).toHaveLength(1);
    expect(labels[0].textContent).toBe("비중 · 취득가 기준");
    expect(screen.getByTestId("positions-cost-basis-note")).toBeInTheDocument();
    // Each row: weight + its own cost (10 × 100), never a market value.
    const row = screen.getAllByTestId("position-card")[0];
    expect(row.textContent).toContain("USD 1,000.00");
    expect(row.textContent).not.toContain("USD 1,200.00"); // 10 × the vendor quote 120
    expect(row.textContent).not.toMatch(/[▲▼]/);
  });

  it("shows no basis label when vendor quotes are on, and the P/L % carries a glyph", () => {
    setPhone(true);
    render(<PositionsTableV2 positions={POS} totalNav={1200} fxRate={1380} marketDataDisplay />);
    expect(screen.queryByTestId("position-card-weight-basis")).toBeNull();
    const row = screen.getAllByTestId("position-card")[0];
    expect(row.textContent).toContain("USD 1,200.00");
    expect(row.textContent).toContain("▲ +20.00%");
  });

  it("the sheet shows the holding's figures by gate: cost only when off", async () => {
    setPhone(true);
    render(<PositionsTableV2 positions={POS} totalNav={1200} fxRate={1380} onAction={vi.fn()} marketDataDisplay={false} />);
    await userEvent.click(screen.getByTestId("position-card-open"));
    const figures = screen.getByTestId("position-sheet-figures");
    expect(figures.textContent).toContain("취득금액");
    expect(figures.textContent).toContain("USD 1,000.00");
    expect(figures.textContent).not.toContain("현재가");
    expect(figures.textContent).not.toContain("평가액");
  });

  it("the sheet adds 현재가 / 평가액 / 손익률 when the gate is on", async () => {
    setPhone(true);
    render(<PositionsTableV2 positions={POS} totalNav={1200} fxRate={1380} onAction={vi.fn()} marketDataDisplay />);
    await userEvent.click(screen.getByTestId("position-card-open"));
    const figures = screen.getByTestId("position-sheet-figures");
    expect(figures.textContent).toContain("현재가");
    expect(figures.textContent).toContain("USD 120.00");
    expect(figures.textContent).toContain("평가액");
  });

  it("empty book on a phone: an app empty state with the add action", async () => {
    setPhone(true);
    const onAdd = vi.fn();
    render(<PositionsTableV2 positions={[]} totalNav={0} fxRate={1380} onAddPosition={onAdd} marketDataDisplay={false} />);
    expect(screen.getByText("아직 기록된 보유 종목이 없습니다")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "보유종목 추가" }));
    expect(onAdd).toHaveBeenCalled();
  });

  it("loading on a phone: skeleton rows with a status for screen readers", () => {
    setPhone(true);
    render(<PositionsTableV2 positions={[]} totalNav={0} fxRate={1380} loading marketDataDisplay={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("보유 종목을 불러오는 중");
    expect(screen.queryByTestId("position-card")).toBeNull();
  });

  it("keeps the table on desktop", () => {
    setPhone(false);
    render(<PositionsTableV2 positions={POS} totalNav={1200} fxRate={1380} />);
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.queryByTestId("positions-cards")).toBeNull();
  });
});
