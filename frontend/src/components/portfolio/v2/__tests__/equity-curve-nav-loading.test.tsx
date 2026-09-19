import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Same mocking convention as equity-curve-benchmark.test.tsx — the NAV KPI is
// fed by props, so the curve hook only has to stay quiet.
vi.mock("@/components/portfolio/v2/hooks-v2", () => ({
  useEquityCurve: vi.fn(),
}));

import { useEquityCurve } from "@/components/portfolio/v2/hooks-v2";
import { EquityCurveBlock } from "@/components/portfolio/v2/equity-curve-block";
import { PortfolioHeroV2 } from "@/components/portfolio/v2/portfolio-hero-v2";

const mockedHook = vi.mocked(useEquityCurve);

function mkEmpty(isLoading: boolean) {
  return {
    data: undefined,
    isLoading,
    error: undefined,
  } as unknown as ReturnType<typeof useEquityCurve>;
}

/** Text of the NAV KPI cell (label div + value div share a parent). */
function navCellText(): string {
  const label = screen.getByText("NAV");
  return label.parentElement?.textContent ?? "";
}

describe("EquityCurveBlock — NAV KPI while the portfolio is still loading", () => {
  beforeEach(() => {
    mockedHook.mockReset();
  });

  it("renders an em-dash, not 'USD 0', before the NAV is known", () => {
    mockedHook.mockReturnValue(mkEmpty(true));
    // What /portfolio passes on the first frame: positions haven't arrived, so
    // every NAV figure is still 0/undefined. Pre-fix this printed "USD 0" on an
    // account holding ₩4,420,000.
    render(
      <EquityCurveBlock
        currency="USD"
        currentNav={0}
        navUsd={0}
        navKrw={0}
        hasPositions={false}
        loading
      />,
    );
    expect(navCellText()).toContain("—");
    expect(navCellText()).not.toContain("USD 0");
  });

  it("uses the same placeholder the hero uses on the same screen", () => {
    // Two placeholders on one screen is the bug behind the bug. Render both
    // loading states and compare the characters that actually reach the DOM,
    // so a future change to either side has to change both.
    const hero = render(
      <PortfolioHeroV2 nav={0} loading onAddPosition={() => {}} />,
    );
    expect(hero.container.textContent ?? "").toContain("— of capital");
    hero.unmount();

    mockedHook.mockReturnValue(mkEmpty(true));
    render(<EquityCurveBlock currency="USD" currentNav={0} loading />);
    expect(navCellText()).toContain("—");
  });

  it("still shows a real zero for a LOADED book with no positions", () => {
    // A measured zero is not a placeholder — an account that has recorded
    // nothing genuinely holds USD 0, and the panel below tells it to add a
    // position. Only ignorance gets the dash.
    mockedHook.mockReturnValue(mkEmpty(false));
    render(
      <EquityCurveBlock
        currency="USD"
        currentNav={0}
        navUsd={0}
        navKrw={0}
        hasPositions={false}
        loading={false}
      />,
    );
    expect(navCellText()).toContain("USD 0");
  });

  it("leaves the loaded single-market (KRW) subtotal untouched", () => {
    // v52 regression guard: a KR-only book must print its native KRW subtotal,
    // never the USD-unified `currentNav` labeled KRW (~1380x wrong).
    mockedHook.mockReturnValue(mkEmpty(false));
    render(
      <EquityCurveBlock
        currency="KRW"
        currentNav={3200}
        navKrw={4_420_000}
        hasPositions
      />,
    );
    expect(navCellText()).toContain("KRW 4,420,000");
  });

  it("leaves the loaded dual-market stack untouched", () => {
    mockedHook.mockReturnValue(mkEmpty(false));
    render(
      <EquityCurveBlock
        currency="USD"
        currentNav={10_000}
        navUsd={6_800}
        navKrw={4_420_000}
        hasPositions
      />,
    );
    const text = navCellText();
    expect(text).toContain("USD 6,800");
    expect(text).toContain("KRW 4,420,000");
  });
});
