import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SwotPanel } from "@/components/detail/SwotPanel";
import { CompanionCta } from "@/components/detail/CompanionCta";
import { EarningsPanel } from "@/components/detail/EarningsPanel";

/**
 * Regression gate (feedback_ticker_display): the detail-page panels that were
 * fixed in commit 4b156e1b must never surface a naked KR ticker code in
 * VISIBLE text. We assert on `textContent` (not innerHTML) so a ticker that
 * legitimately lives in an href attribute — e.g. CompanionCta's deep link —
 * does not trip the guard, while a raw "005930.KS" rendered as copy would.
 *
 * If a future edit drops `displayName` and renders the raw symbol again,
 * these break.
 */

const KR_TICKER = "005930.KS";
const KR_NAME = "삼성전자";

function visibleText(container: HTMLElement): string {
  return container.textContent ?? "";
}

describe("detail panels — no naked KR ticker in visible text", () => {
  it("SwotPanel (empty/generate state) shows the name, not the code", () => {
    const { container } = render(
      <SwotPanel
        ticker={KR_TICKER}
        displayName={KR_NAME}
        swot={null}
        loading={false}
        error={null}
        onGenerate={() => {}}
      />,
    );
    expect(visibleText(container)).not.toContain(KR_TICKER);
    expect(visibleText(container)).toContain(KR_NAME);
  });

  it("CompanionCta heading shows the name; the code is href-only", () => {
    const { container } = render(
      <CompanionCta ticker={KR_TICKER} displayName={KR_NAME} />,
    );
    expect(visibleText(container)).not.toContain(KR_TICKER);
    expect(visibleText(container)).toContain(KR_NAME);
    // The ticker is still allowed in the deep-link href (not visible text).
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toContain(KR_TICKER);
  });

  it("EarningsPanel empty-state shows the name, not the code", () => {
    const { container } = render(
      <EarningsPanel displayName={KR_NAME} items={[]} />,
    );
    expect(visibleText(container)).not.toContain(KR_TICKER);
    expect(visibleText(container)).toContain(KR_NAME);
  });

  it("falls back to a generic noun (never the raw code) when name is absent", () => {
    const { container: c1 } = render(
      <SwotPanel
        ticker={KR_TICKER}
        swot={null}
        loading={false}
        error={null}
        onGenerate={() => {}}
      />,
    );
    const { container: c2 } = render(<EarningsPanel items={[]} />);
    expect(visibleText(c1)).not.toContain(KR_TICKER);
    expect(visibleText(c2)).not.toContain(KR_TICKER);
  });
});
