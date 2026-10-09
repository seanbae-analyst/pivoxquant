/**
 * Holdings on a phone (2026-10-07): one card per holding instead of a table
 * that scrolls sideways. Same values (shares, average cost, weight) and the
 * same row actions. Desktop and SSR keep the table.
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
    await userEvent.click(screen.getByRole("button", { name: "AAPL 정리 기록" }));
    expect(onAction).toHaveBeenCalledWith("sell", expect.objectContaining({ symbol: "AAPL" }));
  });

  it("labels the card weight cost-basis when vendor quotes are off", () => {
    setPhone(true);
    render(<PositionsTableV2 positions={POS} totalNav={1200} fxRate={1380} marketDataDisplay={false} />);
    expect(screen.getByTestId("position-card-weight-basis").textContent).toBe("비중 · 취득가 기준");
  });

  it("shows no basis label when vendor quotes are on", () => {
    setPhone(true);
    render(<PositionsTableV2 positions={POS} totalNav={1200} fxRate={1380} marketDataDisplay />);
    expect(screen.queryByTestId("position-card-weight-basis")).toBeNull();
  });

  it("keeps the table on desktop", () => {
    setPhone(false);
    render(<PositionsTableV2 positions={POS} totalNav={1200} fxRate={1380} />);
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.queryByTestId("positions-cards")).toBeNull();
  });
});
