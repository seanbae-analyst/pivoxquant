/**
 * Phone /portfolio large title (2026-10-10): one figure per currency, never
 * summed; folds to one line when the page scrolls; no zero money slot.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PortfolioPhoneSummary, summaryAmounts } from "../portfolio-phone-summary";

vi.mock("motion/react", () => ({ useReducedMotion: () => false }));

afterEach(cleanup);

const base = {
  marketDataDisplay: false,
  positionCount: 2,
  costUsd: 1000,
  costKrw: 1_200_000,
  navUsd: 1500,
  navKrw: 1_400_000,
  onAddPosition: () => {},
};

describe("PortfolioPhoneSummary", () => {
  it("prints each currency on its own figure, cost basis with the gate off", () => {
    render(<PortfolioPhoneSummary {...base} />);
    expect(screen.getByTestId("portfolio-phone-summary")).toHaveTextContent("보유 2종목 · 취득가 기준");
    const figures = screen.getByTestId("portfolio-phone-summary-amount").querySelectorAll(".pq-pf-summary-figure");
    expect(Array.from(figures).map((f) => f.textContent)).toEqual(["USD 1,000", " · KRW 1,200,000"]);
  });

  it("marks itself collapsed so the figures fold into one line", () => {
    const { rerender } = render(<PortfolioPhoneSummary {...base} />);
    expect(screen.getByTestId("portfolio-phone-summary")).not.toHaveAttribute("data-collapsed");
    rerender(<PortfolioPhoneSummary {...base} collapsed />);
    expect(screen.getByTestId("portfolio-phone-summary")).toHaveAttribute("data-collapsed", "true");
    // Same text either way — only the layout changes.
    expect(screen.getByTestId("portfolio-phone-summary-amount").textContent).toBe("USD 1,000 · KRW 1,200,000");
  });

  it("drops a currency with nothing in it — never 'KRW 0'", () => {
    expect(summaryAmounts({ ...base, costKrw: 0 })).toEqual(["USD 1,000"]);
    expect(summaryAmounts({ ...base, costUsd: 0, costKrw: 0 })).toBeNull();
  });

  it("keeps the add action, and shows a skeleton while loading", async () => {
    const onAdd = vi.fn();
    const { rerender } = render(<PortfolioPhoneSummary {...base} onAddPosition={onAdd} loading />);
    expect(screen.getByRole("status", { name: "불러오는 중" })).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-phone-summary-amount")).toBeNull();
    rerender(<PortfolioPhoneSummary {...base} onAddPosition={onAdd} />);
    await userEvent.click(screen.getByTestId("portfolio-phone-add"));
    expect(onAdd).toHaveBeenCalled();
  });
});
