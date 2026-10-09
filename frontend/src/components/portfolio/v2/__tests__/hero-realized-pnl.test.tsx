/**
 * 올해 실현 손익 — a currency with nothing realized has no line (2026-10-09).
 * A mixed book that sold only US stock printed "+USD 3,180" over "KRW 0".
 * The two currencies are never summed.
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { LocaleProvider } from "@/lib/locale";
import { PortfolioHeroV2 } from "../portfolio-hero-v2";

function realizedKpi() {
  const label = screen.getByText("올해 실현 손익");
  return label.parentElement as HTMLElement;
}

function renderHero(p: { realizedUsd?: number; realizedKrw?: number; realizedYtd?: number }) {
  return render(
    <LocaleProvider>
      <PortfolioHeroV2
        marketDataDisplay={false}
        costUsd={12_000}
        costKrw={3_000_000}
        positionCount={4}
        onAddPosition={() => {}}
        {...p}
      />
    </LocaleProvider>,
  );
}

describe("PortfolioHeroV2 — realized P&L lines", () => {
  it("mixed book, KRW nothing realized: only the USD line", () => {
    renderHero({ realizedUsd: 3180, realizedKrw: 0, realizedYtd: 3180 });
    const kpi = realizedKpi();
    expect(within(kpi).getByText("+USD 3,180")).toBeInTheDocument();
    expect(within(kpi).queryByText(/KRW/)).toBeNull();
  });

  it("both currencies realized: two lines, never one summed figure", () => {
    renderHero({ realizedUsd: -40, realizedKrw: 125_000, realizedYtd: 50 });
    const kpi = realizedKpi();
    expect(within(kpi).getByText("−USD 40")).toBeInTheDocument();
    expect(within(kpi).getByText("+KRW 125,000")).toBeInTheDocument();
    expect(within(kpi).queryByText(/50/)).toBeNull();
  });

  it("nothing realized in either currency: a single plain 0", () => {
    renderHero({ realizedUsd: 0, realizedKrw: 0, realizedYtd: 0 });
    const kpi = realizedKpi();
    expect(within(kpi).queryByText(/KRW|USD/)).toBeNull();
    expect(within(kpi).getByText("0")).toBeInTheDocument();
  });
});
