import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OverviewPaper } from "@/components/market/overview-paper";

// Regression: the /market region tabs use SWR keepPreviousData, so flipping
// US↔KR briefly hands the board the prior region's payload, which the page
// filters to []. Before this fix the empty board always read "No observation
// available for this region" — a misleading "no data" message that flashed on
// every tab switch even though data was seconds away. With `loading`, the
// empty board distinguishes still-loading from genuinely-empty.

const baseProps = {
  quotes: [] as never[],
  marketOpen: false,
  liveLabel: "Last observed 18:00 KST",
  weekTag: "2026 · W21",
};

describe("OverviewPaper — loading vs empty board", () => {
  it("shows a loading message (not 'No observation') while transitioning", () => {
    render(<OverviewPaper region="KR" {...baseProps} loading />);
    expect(screen.getByText(/Loading Korea observations/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/No observation available/i),
    ).not.toBeInTheDocument();
  });

  it("shows 'No observation available' only when genuinely empty (not loading)", () => {
    render(<OverviewPaper region="KR" {...baseProps} loading={false} />);
    expect(
      screen.getByText(/No observation available for this region/i),
    ).toBeInTheDocument();
  });

  it("uses the US region label in the loading copy", () => {
    render(<OverviewPaper region="US" {...baseProps} loading />);
    expect(
      screen.getByText(/Loading United States observations/i),
    ).toBeInTheDocument();
  });
});
