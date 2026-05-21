import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FundamentalsPanel } from "@/components/detail/FundamentalsPanel";
import type { SignalDetail, Snapshot } from "@/components/detail/types";

// #4: KR tickers surface 3 license-bounded "—" rows (margin / rev growth /
// D-E). The backend flags `fundamentals_limited` so we render an honest note
// rather than leaving bare em-dashes that look like a bug.

function sig(snapshot: Snapshot): SignalDetail {
  return { snapshot } as unknown as SignalDetail;
}

describe("FundamentalsPanel — fundamentals_limited note", () => {
  it("shows the KIS-license note when limited (KR ticker with PER but no margin/growth/D-E)", () => {
    const { container } = render(
      <FundamentalsPanel
        signal={sig({
          pe_ratio: 45.5,
          eps: 6400,
          profit_margin: null,
          revenue_growth: null,
          debt_equity: null,
          fundamentals_limited: true,
        })}
        mcap={1.7e15}
        krw
      />,
    );
    expect(screen.getByText(/오류가 아닙니다/)).toBeInTheDocument();
    expect(screen.getByText(/not an error/i)).toBeInTheDocument();
    // PER still renders (KIS provides it); the 3 limited rows render "—".
    expect(container.textContent).toContain("45.5");
    expect(container.textContent).toContain("—");
  });

  it("does NOT show the note for a US ticker with full data", () => {
    render(
      <FundamentalsPanel
        signal={sig({
          pe_ratio: 36.2,
          eps: 6.1,
          profit_margin: 0.271,
          revenue_growth: 0.064,
          debt_equity: 0.79,
          fundamentals_limited: false,
        })}
        mcap={3.2e12}
        krw={false}
      />,
    );
    expect(screen.queryByText(/오류가 아닙니다/)).not.toBeInTheDocument();
    expect(screen.getByText("27.1%")).toBeInTheDocument(); // profit margin shown
  });

  it("does NOT show the note when the flag is absent (no false positive)", () => {
    render(
      <FundamentalsPanel
        signal={sig({ pe_ratio: 10, profit_margin: null })}
        mcap={1e9}
        krw={false}
      />,
    );
    expect(screen.queryByText(/오류가 아닙니다/)).not.toBeInTheDocument();
  });

  it("collapses to the empty note when the snapshot has no data at all", () => {
    render(<FundamentalsPanel signal={sig({})} mcap={null} krw={false} />);
    expect(screen.getByText(/Financials pending next filing/i)).toBeInTheDocument();
    expect(screen.queryByText(/오류가 아닙니다/)).not.toBeInTheDocument();
  });
});
