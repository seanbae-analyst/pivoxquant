import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ConcentrationTable } from "@/components/risk/v2/concentration-table";

/**
 * Regression gate (feedback_ticker_display): the /risk concentration table
 * renders the company name as the primary label and the ticker as a mono
 * sub-line. A KR symbol with an exchange suffix ("005930.KS") must NEVER
 * surface in VISIBLE text — neither the primary label nor the sub-line.
 *
 * We assert on `textContent` so the suffix is caught wherever it renders.
 * If a future edit drops displayTicker/normalizeTicker and prints the raw
 * symbol again, this breaks.
 */

const KR_TICKER = "005930.KS";
const KR_NAME = "삼성전자";

function visibleText(container: HTMLElement): string {
  return container.textContent ?? "";
}

describe("ConcentrationTable — no naked KR ticker in visible text", () => {
  it("shows the name and a suffix-stripped code (never '.KS')", () => {
    const { container } = render(
      <ConcentrationTable
        entries={[
          {
            rank: 1,
            name: KR_NAME,
            ticker: KR_TICKER,
            exchange: "KOSPI",
            weightPct: 42.5,
          },
        ]}
        sumPct={42.5}
      />,
    );
    const text = visibleText(container);
    expect(text).not.toContain(".KS");
    expect(text).toContain(KR_NAME);
    // The bare 6-digit code is allowed as the demoted sub-line.
    expect(text).toContain("005930");
  });

  it("falls back to the suffix-stripped code when the name is missing", () => {
    const { container } = render(
      <ConcentrationTable
        entries={[
          {
            rank: 1,
            name: KR_TICKER, // backend echoed the ticker back as the name
            ticker: KR_TICKER,
            exchange: "KOSPI",
            weightPct: 12,
          },
        ]}
        sumPct={12}
      />,
    );
    const text = visibleText(container);
    expect(text).not.toContain(".KS");
    // seed maps 005930 -> 삼성전자 even without a backend name.
    expect(text).toContain(KR_NAME);
  });
});
