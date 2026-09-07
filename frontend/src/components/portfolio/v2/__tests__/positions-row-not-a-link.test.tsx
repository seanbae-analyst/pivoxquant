/**
 * The position rows are not navigation.
 *
 * They used to be: each row pushed `/detail/[ticker]`, carried
 * `role="link"`, `tabIndex={0}`, an Enter/Space handler and `cursor:
 * pointer`. The 2026-08-31 prune deleted that page, and next.config.ts:78
 * permanently redirects `/detail/:path*` → `/portfolio` — so on /portfolio a
 * row click returned the reader to the page they were already on, having
 * announced itself to assistive tech as a link the whole time.
 *
 * Nothing covered this, which is why it survived the prune and turned up in a
 * nightly sweep instead. These tests pin the corrected shape so a future
 * refactor cannot quietly restore a link that leads nowhere.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PositionsTableV2 } from "@/components/portfolio/v2/positions-table-v2";
import type { Position } from "@/components/portfolio/types";

const POS: Position[] = [
  {
    id: "1",
    symbol: "AAPL",
    name: "Apple",
    side: "Long",
    shares: 10,
    avgCost: 100,
    current: 120,
    sector: "Tech",
    purchaseDate: "2026-01-01",
    currency: "USD",
  } as Position,
];

function renderTable(onAction?: (a: never, p: Position) => void) {
  return render(
    <PositionsTableV2
      positions={POS}
      totalNav={1200}
      fxRate={1380}
      onAction={onAction as never}
    />,
  );
}

describe("PositionsTableV2 — rows are not links", () => {
  it("announces no link to assistive technology", () => {
    renderTable();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("does not put the row in the tab order", () => {
    const { container } = renderTable();
    const row = container.querySelector("tr.pq-pos-row");
    expect(row).not.toBeNull();
    expect(row).not.toHaveAttribute("tabindex");
    expect(row).not.toHaveAttribute("role");
  });

  it("does not dress the row as clickable", () => {
    const { container } = renderTable();
    const css = container.textContent ?? "";
    // styled-jsx inlines the rule text into the tree in jsdom.
    expect(css).not.toContain("cursor: pointer");
  });

  it("still runs the real affordances — the action buttons", async () => {
    const onAction = vi.fn();
    renderTable(onAction);
    await userEvent.click(screen.getByRole("button", { name: /add/i }));
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onAction.mock.calls[0][1]).toMatchObject({ symbol: "AAPL" });
  });
});
