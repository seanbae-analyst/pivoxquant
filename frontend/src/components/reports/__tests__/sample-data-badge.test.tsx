/**
 * Regression guard — SAMPLE data labelling on the 18 PDF report templates.
 * ----------------------------------------------------------------------
 * CEO 직격 버그 (2026-05-31): the public /sample-reports/[slug] routes render
 * each template with its hardcoded DEFAULT fixture (concrete-looking
 * performance numbers like "+18.4% FY RETURN", "NVDA +22.4% RIGHT").
 * Before this fix only 3 of 18 templates carried a "SAMPLE" banner, so a
 * public visitor could mistake illustrative numbers for real product
 * performance (trust + 표시·광고법 허위 성과표시 risk).
 *
 * Invariants locked in here:
 *   1. The shared <SampleDataBadge /> renders the bilingual KR+EN copy and
 *      carries the `data-pq-sample-badge` hook (used by the assertions and
 *      any future print/QA tooling).
 *   2. Every template, in SAMPLE mode (no `data` prop → DEFAULT fixture),
 *      renders exactly one sample badge.
 *   3. In REAL-DATA mode (a non-DEFAULT `data` object), the badge must NOT
 *      render — a member viewing their own report never sees "SAMPLE".
 */
import { describe, expect, it } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { SampleDataBadge } from "../sample-data-badge";

import { WeeklyMemo } from "../templates/weekly-memo";
import { BragCard } from "../templates/brag-card";
import { MorningBriefPlus } from "../templates/morning-brief-plus";
import { EarningsPrebrief } from "../templates/earnings-prebrief";
import { RiskBoard } from "../templates/risk-board";
import { QuarterlySelfReport } from "../templates/quarterly-self-report";
import { SelfAudit } from "../templates/self-audit";
import { DdChecklist } from "../templates/dd-checklist";
import { DividendIncome } from "../templates/dividend-income";
import { InsiderMirror } from "../templates/insider-mirror";
import { Sp500Backtest } from "../templates/sp500-backtest";
import { PortfolioSegment } from "../templates/portfolio-segment";
import { CapitalAllocation } from "../templates/capital-allocation";
import { CreditRating } from "../templates/credit-rating";
import { BurnRate } from "../templates/burn-rate";
import { MonthlyFinance } from "../templates/monthly-finance";
import { KpiDashboard } from "../templates/kpi-dashboard";
import { YearEndLetter } from "../templates/year-end-letter";

afterEach(() => cleanup());

const BADGE = "[data-pq-sample-badge='true']";

const ALL_TEMPLATES: { name: string; Comp: React.ComponentType }[] = [
  { name: "weekly-memo", Comp: WeeklyMemo },
  { name: "brag-card", Comp: BragCard },
  { name: "morning-brief-plus", Comp: MorningBriefPlus },
  { name: "earnings-prebrief", Comp: EarningsPrebrief },
  { name: "risk-board", Comp: RiskBoard },
  { name: "quarterly-self-report", Comp: QuarterlySelfReport },
  { name: "self-audit", Comp: SelfAudit },
  { name: "dd-checklist", Comp: DdChecklist },
  { name: "dividend-income", Comp: DividendIncome },
  { name: "insider-mirror", Comp: InsiderMirror },
  { name: "sp500-backtest", Comp: Sp500Backtest },
  { name: "portfolio-segment", Comp: PortfolioSegment },
  { name: "capital-allocation", Comp: CapitalAllocation },
  { name: "credit-rating", Comp: CreditRating },
  { name: "burn-rate", Comp: BurnRate },
  { name: "monthly-finance", Comp: MonthlyFinance },
  { name: "kpi-dashboard", Comp: KpiDashboard },
  { name: "year-end-letter", Comp: YearEndLetter },
];

describe("SampleDataBadge (shared component)", () => {
  it("renders bilingual KR+EN sample copy with the print-safe hook", () => {
    const { container } = render(<SampleDataBadge />);
    const badge = container.querySelector(BADGE);
    expect(badge).not.toBeNull();
    // KR + EN both present so neither audience can miss it.
    expect(badge!.textContent).toContain("예시");
    expect(badge!.textContent).toContain("가상 포트폴리오");
    expect(badge!.textContent).toContain("실제 보유");
    expect(badge!.textContent).toContain("SAMPLE");
    expect(badge!.textContent).toContain("illustrative data");
  });

  it("is NOT hidden from print (must appear on exported sample PDFs)", () => {
    const { container } = render(<SampleDataBadge />);
    const badge = container.querySelector(BADGE) as HTMLElement;
    // No data-print-hidden — saved sample PDFs must still carry the label.
    expect(badge.getAttribute("data-print-hidden")).toBeNull();
  });
});

describe("all 18 templates — SAMPLE mode renders the badge", () => {
  it.each(ALL_TEMPLATES)(
    "$name shows exactly one sample badge with no data prop",
    ({ Comp }) => {
      const { container } = render(<Comp />);
      const badges = container.querySelectorAll(BADGE);
      expect(badges.length).toBe(1);
    },
  );
});

describe("real-data mode does NOT render the badge", () => {
  it("WeeklyMemo with a real WeeklyMemoData object hides the badge", () => {
    const realMemo = {
      asOf: "2026-05-31",
      weekTag: "WK-2026-22",
      portfolioReturn: "+1.2%",
      benchmarkReturn: "vs S&P +0.8%",
      portfolioValue: "USD 100,000",
      portfolioDelta: "▲ USD 1,200",
      ytdReturn: "+5.0%",
      ytdDetail: "Sharpe 0.50",
      threeChecks: [{ body: "Real check", meta: "+0.3%", checked: true }],
      trajectory: { portfolio: [0, 0.5, 1.2], benchmark: [0, 0.3, 0.8] },
      decision: "Real decision text.",
      memoToSelf: "Real memo text.",
    };
    const { container } = render(<WeeklyMemo data={realMemo} />);
    expect(container.querySelectorAll(BADGE).length).toBe(0);
    // Real value is actually rendered (proves we're on the real-data path).
    expect(container.textContent).toContain("USD 100,000");
  });

  it("BragCard with a real backend payload hides the badge", () => {
    // normalizeBragCardData() returns a NON-DEFAULT object for any payload
    // carrying backend fields → isSample === false.
    const realPayload = {
      best_ticker: "AAPL",
      best_return_pct: 5.2,
      return_pct: 3.1,
      month_label: "May 2026",
      trade_count: 4,
    };
    const { container } = render(<BragCard data={realPayload} />);
    expect(container.querySelectorAll(BADGE).length).toBe(0);
    expect(container.textContent).toContain("AAPL");
  });
});
