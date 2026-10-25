/**
 * 내가 고른 회사들 (2026-10-25) — the view over GET /api/pick-facts.
 *
 * Pins: three counts out of the picks that had numbers, with the names under
 * each; the "filed before the buy" line, pending / no-number notes and the
 * sources; nothing when nothing was bought; no score / grade / advice words.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { PickFactsView } from "@/components/mirror/pick-facts-panel";
import type { PickFactsResponse } from "@/lib/types";

afterEach(cleanup);

const pick = (ticker: string, name: string | null, f: Partial<PickFactsResponse["picks"][number]> = {}) => ({
  ticker, name, bought_on: "2026-05-01", fiscal_end: "2025-12-31", filed_on: "2026-02-01",
  net_loss: false, revenue_down: false, liabilities_over_equity: false, source: "SEC EDGAR", ...f,
});

const DATA: PickFactsResponse = {
  ok: true, window_days: 365, picked: 4, with_facts: 3, pending: 1, no_facts: 0,
  counts: { net_loss: 1, revenue_down: 0, liabilities_over_equity: 2 },
  sources: ["DART", "SEC EDGAR"],
  picks: [
    pick("JOBY", "Joby Aviation", { net_loss: true, liabilities_over_equity: true }),
    pick("005930.KS", null, { liabilities_over_equity: true, source: "DART" }),
    pick("AAPL", "Apple"),
  ],
};

describe("PickFactsView", () => {
  it("counts out of the picks with numbers and names who is in each", () => {
    render(<PickFactsView data={DATA} />);
    expect(screen.getByText(/최근 1년 처음 산 4종목/)).toBeTruthy();
    const loss = screen.getByTestId("pick-facts-net_loss").textContent ?? "";
    expect(loss).toContain("순손실이었던 곳");
    expect(loss).toContain("1");
    expect(loss).toContain("/ 3곳");
    expect(loss).toContain("Joby Aviation");
    const lev = screen.getByTestId("pick-facts-liabilities_over_equity").textContent ?? "";
    expect(lev).toContain("Joby Aviation, 005930");
    expect(screen.getByTestId("pick-facts-revenue_down").textContent).not.toContain("Apple");
    const blob = screen.getByTestId("pick-facts").textContent ?? "";
    expect(blob).toContain("산 뒤에 나온 숫자는 쓰지 않아요");
    expect(blob).toContain("1곳은 숫자를 받는 중");
    expect(blob).toContain("출처: DART · SEC EDGAR");
    for (const w of ["점수", "등급", "추천", "좋은 회사", "score"]) expect(blob).not.toContain(w);
  });

  it("renders nothing when nothing was bought in the window", () => {
    const { container } = render(<PickFactsView data={{ ...DATA, picked: 0, with_facts: 0, picks: [] }} />);
    expect(container.textContent).toBe("");
  });
});
