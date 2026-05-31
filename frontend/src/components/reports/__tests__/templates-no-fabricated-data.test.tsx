/**
 * Templates: no fabricated data, honest empty state.
 *
 * CEO 2026-05-31 직격: the 18 PDF report templates must never fabricate a
 * sample portfolio. When there is no real artifact `data`, each template
 * renders the shared <EmptyState /> instead of a hardcoded fixture. When real
 * `data` is provided, the template renders those exact values.
 *
 * This suite replaces the deleted sample-data-badge.test.tsx — labelling fake
 * data was rejected; the fix is to remove the fake data entirely.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { WeeklyMemo, type WeeklyMemoData } from "../templates/weekly-memo";
import { KpiDashboard, type KpiDashboardData } from "../templates/kpi-dashboard";
import { RiskBoard as RiskBoardReal, type RiskBoardData } from "../templates/risk-board";
import { MonthlyFinance as MonthlyFinanceReal, type MonthlyFinanceData } from "../templates/monthly-finance";
import { YearEndLetter, type YearEndLetterData } from "../templates/year-end-letter";
import { BragCard, type BragCardData } from "../templates/brag-card";
import { DdChecklist } from "../templates/dd-checklist";
import { CreditRating } from "../templates/credit-rating";
import { EarningsPrebrief } from "../templates/earnings-prebrief";
import { RiskBoard } from "../templates/risk-board";
import { DividendIncome } from "../templates/dividend-income";
import { MonthlyFinance } from "../templates/monthly-finance";
import { SelfAudit } from "../templates/self-audit";
import { InsiderMirror } from "../templates/insider-mirror";
import { PortfolioSegment } from "../templates/portfolio-segment";
import { CapitalAllocation } from "../templates/capital-allocation";
import { BurnRate } from "../templates/burn-rate";
import { Sp500Backtest } from "../templates/sp500-backtest";
import { QuarterlySelfReport } from "../templates/quarterly-self-report";
import { MorningBriefPlus } from "../templates/morning-brief-plus";

/** Every template renders <EmptyState> (role=status) when given no data. */
const NO_DATA_TEMPLATES: Array<[string, React.ComponentType<{ data?: unknown }>]> = [
  ["WeeklyMemo", WeeklyMemo as never],
  ["KpiDashboard", KpiDashboard as never],
  ["YearEndLetter", YearEndLetter as never],
  ["BragCard", BragCard as never],
  ["DdChecklist", DdChecklist as never],
  ["CreditRating", CreditRating as never],
  ["EarningsPrebrief", EarningsPrebrief as never],
  ["RiskBoard", RiskBoard as never],
  ["DividendIncome", DividendIncome as never],
  ["MonthlyFinance", MonthlyFinance as never],
  ["SelfAudit", SelfAudit as never],
  ["InsiderMirror", InsiderMirror as never],
  ["PortfolioSegment", PortfolioSegment as never],
  ["CapitalAllocation", CapitalAllocation as never],
  ["BurnRate", BurnRate as never],
  ["Sp500Backtest", Sp500Backtest as never],
  ["QuarterlySelfReport", QuarterlySelfReport as never],
  ["MorningBriefPlus", MorningBriefPlus as never],
];

describe("report templates — no fabricated data, honest empty state", () => {
  it.each(NO_DATA_TEMPLATES)(
    "%s renders the empty state (not a sample) when data is undefined",
    (_name, Template) => {
      const { container } = render(<Template />);
      // <EmptyState> sets role="status" with a data-pq-empty-reason attribute.
      const empty = container.querySelector("[data-pq-empty-reason]");
      expect(empty).not.toBeNull();
      // None of the deleted fabricated fixtures' tells should appear.
      expect(container.textContent).not.toContain("홍길동");
      expect(container.textContent).not.toContain("Palantir");
    },
  );
});

describe("WeeklyMemo — real data render", () => {
  const data: WeeklyMemoData = {
    asOf: "2026-05-31",
    weekTag: "WK-2026-22",
    portfolioReturn: "+0.9%",
    benchmarkReturn: "vs S&P +0.4%",
    portfolioValue: "USD 100",
    portfolioDelta: "▲ USD 1",
    ytdReturn: "+3.0%",
    ytdDetail: "Sharpe 0.5",
    threeChecks: [{ body: "REAL_CHECK_ROW", meta: "+0.1%", checked: true }],
    trajectory: { portfolio: [0, 0.9], benchmark: [0, 0.4] },
    decision: "REAL_DECISION_TEXT",
    memoToSelf: "REAL_MEMO_TEXT",
  };

  it("renders the provided values, not the old +2.4% sample", () => {
    render(<WeeklyMemo data={data} />);
    expect(screen.getByText("+0.9%")).toBeInTheDocument();
    expect(screen.getByText("REAL_CHECK_ROW")).toBeInTheDocument();
    expect(screen.getByText("REAL_DECISION_TEXT")).toBeInTheDocument();
    // No empty state when real data is present.
    expect(document.querySelector("[data-pq-empty-reason]")).toBeNull();
  });
});

describe("KpiDashboard — real data render", () => {
  const data: KpiDashboardData = {
    doc: "REAL_DOC_TAG",
    navEom: "USD 999",
    navEomDelta: "▲",
    ytdReturn: "+1.1%",
    ytdDelta: "+1.1%",
    sharpe: "0.42",
    sharpeDelta: "+0.0",
    status: "OK",
    statusDelta: "—",
    issued: "REAL_ISSUED",
    scorecard: [
      {
        kpi: "REAL_KPI",
        mtd: "+1%",
        ytd: "+1%",
        m12: "+1%",
        target: ">0",
        status: { tone: "green", label: "OK" },
      },
    ],
    decisions: [
      {
        date: "2026-05-31",
        decision: "REAL_DECISION",
        thesis: "REAL_THESIS",
        size: "1%",
        result: "+1%",
        verdict: { tone: "low", label: "OK" },
      },
    ],
    decisionCards: [
      {
        priority: "P1",
        title: "REAL_CARD",
        body: "REAL_CARD_BODY",
        badge: { tone: "info", label: "INFO" },
      },
    ],
  };

  it("renders provided cover values and no empty state", () => {
    render(<KpiDashboard data={data} />);
    expect(screen.getByText("USD 999")).toBeInTheDocument();
    expect(screen.getByText("REAL_KPI")).toBeInTheDocument();
    expect(document.querySelector("[data-pq-empty-reason]")).toBeNull();
  });
});

describe("YearEndLetter — empty state reason", () => {
  it("uses insufficient_history when no data", () => {
    const { container } = render(<YearEndLetter />);
    expect(
      container.querySelector('[data-pq-empty-reason="insufficient_history"]'),
    ).not.toBeNull();
  });
});

describe("BragCard — real data, empty data, no fabricated narrative", () => {
  it("renders empty state for no data (reason no_trades)", () => {
    const { container } = render(<BragCard />);
    expect(
      container.querySelector('[data-pq-empty-reason="no_trades"]'),
    ).not.toBeNull();
  });

  it("renders the backend numeric payload without borrowing a fake PLTR story", () => {
    render(
      <BragCard
        data={
          {
            month_label_long: "May 2026",
            month_start: "2026-05-01",
            return_pct: 1.5,
            trade_count: 2,
            best_ticker: "REALTICKER",
            best_return_pct: 4.0,
          } as never
        }
      />,
    );
    // Real ticker shows; fabricated PLTR narrative is gone.
    expect(screen.getByText("REALTICKER")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("Palantir");
    expect(document.body.textContent).not.toContain("운이 아니라");
    expect(document.querySelector("[data-pq-empty-reason]")).toBeNull();
  });

  it("renders the template-shape payload values", () => {
    const data: BragCardData = {
      monthLabel: "May 2026",
      reportTag: "BC-2026-05",
      bestDecisionPct: "+9.9%",
      contribution: "",
      hitRate: "3 건",
      hitRateDetail: "",
      monthReturn: "+2.0%",
      benchmark: "",
      hero: {
        ticker: "REALHERO",
        name: "",
        title: "REAL_HERO_TITLE",
        body: "REAL_HERO_BODY",
        entry: "—",
        mark: "—",
        pnl: "+9.9%",
      },
      whyItWorked: [],
      lessonForNext: [],
      pullquote: "",
    };
    render(<BragCard data={data} />);
    expect(screen.getByText("REALHERO")).toBeInTheDocument();
    expect(screen.getByText("REAL_HERO_TITLE")).toBeInTheDocument();
  });
});

describe("DdChecklist — backend pending-review render + empty state", () => {
  it("renders the honest empty state when no data (not a PLTR sample)", () => {
    const { container } = render(<DdChecklist />);
    expect(
      container.querySelector('[data-pq-empty-reason="no_trades"]'),
    ).not.toBeNull();
    expect(container.textContent).not.toContain("Palantir");
    expect(container.textContent).not.toContain("PLTR");
  });

  it("renders the real backend T+3 pending positions", () => {
    render(
      <DdChecklist
        data={
          {
            as_of: "2026-05-31",
            user_name: "REAL_USER",
            pending: [
              { ticker: "REALTKR", companyName: "Real Co", shares: 5, avg_cost: 10, days_since: 3 },
            ],
          } as never
        }
      />,
    );
    expect(screen.getByText("Real Co")).toBeInTheDocument();
    expect(screen.getByText("REALTKR")).toBeInTheDocument();
    expect(document.querySelector("[data-pq-empty-reason]")).toBeNull();
  });
});

describe("RiskBoard — reduced real-data render (option-b, no beta)", () => {
  const data: RiskBoardData = {
    weekTag: "RB-M · May 2026",
    asOfStamp: "As of May 2026",
    var95: { value: "-2.7%", nav: "≈$33,333 NAV", tone: "amber" },
    maxDD: { value: "-8.3%", limit: "Peak-to-trough", tone: "green" },
    sharpe: { value: "1.42", vsPrior: "Risk-adj. · annual", tone: "green" },
    vix: { value: "18.6", band: "Volatility regime", tone: "green" },
    pairwiseCorr: { value: "0.56", gauge: 56, verdict: "REAL_CORR_VERDICT" },
  };

  it("renders the four real KPIs + corr card, never the removed Beta", () => {
    render(<RiskBoardReal data={data} />);
    expect(screen.getByText("-2.7%")).toBeInTheDocument();
    expect(screen.getByText("1.42")).toBeInTheDocument();
    expect(screen.getByText("18.6")).toBeInTheDocument();
    expect(screen.getByText("REAL_CORR_VERDICT")).toBeInTheDocument();
    // `beta` was dropped from the interface — no Beta card label.
    expect(document.body.textContent).not.toContain("Beta vs S&P");
    expect(document.querySelector("[data-pq-empty-reason]")).toBeNull();
  });

  it("elides the correlation card when pairwiseCorr is absent (no throw)", () => {
    const { pairwiseCorr: _omit, ...noCorr } = data;
    render(<RiskBoardReal data={noCorr} />);
    expect(screen.getByText("-2.7%")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("Pairwise Corr");
  });
});

describe("MonthlyFinance — reduced real-data render (option-b, no P&L/BS/CF)", () => {
  const data: MonthlyFinanceData = {
    doc: "2026-04 · MF",
    coverMonth: "2026-04",
    asOf: "2026-04-30",
    issued: "Issued · 2026-05-01",
    navEom: "₩25.00M",
    navEomKpi: { value: "₩25.00M", delta: "EOM 합산 (KRW)" },
    cashKpi: { value: "₩5.00M", delta: "현금 합산" },
    liquidityKpi: { value: "0.20", delta: "Cash / (Cash + MV)" },
    runwayKpi: { value: "8.5", delta: "현재 burn 기준" },
    costRows: [
      { label: "REAL_COST_ITEM", amount: "₩40k", detail: "증권거래세 추정" },
    ],
    taxRows: [
      { label: "REAL_TAX_ITEM", amount: "₩220k", detail: "해외주식 양도세 추정" },
    ],
  };

  it("renders NAV/cost/tax, never the removed P&L / balance sheet", () => {
    render(<MonthlyFinanceReal data={data} />);
    expect(screen.getAllByText("₩25.00M").length).toBeGreaterThan(0);
    expect(screen.getByText("REAL_COST_ITEM")).toBeInTheDocument();
    expect(screen.getByText("REAL_TAX_ITEM")).toBeInTheDocument();
    // Removed corporate-statement headers must be gone.
    expect(document.body.textContent).not.toContain("Income Statement");
    expect(document.body.textContent).not.toContain("Balance Sheet");
    expect(document.body.textContent).not.toContain("Cash Flow");
    expect(document.querySelector("[data-pq-empty-reason]")).toBeNull();
  });

  it("elides KPI cards that are absent without throwing", () => {
    const minimal: MonthlyFinanceData = {
      doc: "2026-04 · MF",
      asOf: "2026-04-30",
      issued: "Issued · 2026-05-01",
      navEom: "—",
      costRows: [],
      taxRows: [],
    };
    render(<MonthlyFinanceReal data={minimal} />);
    expect(document.querySelector("[data-pq-empty-reason]")).toBeNull();
  });
});
