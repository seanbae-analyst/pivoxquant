/**
 * /sample-reports/[slug] — public preview route for the 18 PDF report designs.
 *
 * This route lives outside the (dashboard) auth layout so the new PDF design
 * system can be reviewed and printed without logging in. The dashboard
 * `/reports/preview/{slug}` routes are auth-gated copies of the same templates.
 *
 * URL examples:
 *   /sample-reports/weekly-memo
 *   /sample-reports/kpi-dashboard
 *   /sample-reports/year-end-letter
 */

import { notFound } from "next/navigation";
import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";

import { WeeklyMemo } from "@/components/reports/templates/weekly-memo";
import { BragCard } from "@/components/reports/templates/brag-card";
import { MorningBriefPlus } from "@/components/reports/templates/morning-brief-plus";
import { EarningsPrebrief } from "@/components/reports/templates/earnings-prebrief";
import { RiskBoard } from "@/components/reports/templates/risk-board";
import { QuarterlySelfReport } from "@/components/reports/templates/quarterly-self-report";
import { SelfAudit } from "@/components/reports/templates/self-audit";
import { DdChecklist } from "@/components/reports/templates/dd-checklist";
import { DividendIncome } from "@/components/reports/templates/dividend-income";
import { InsiderMirror } from "@/components/reports/templates/insider-mirror";
import { Sp500Backtest } from "@/components/reports/templates/sp500-backtest";
import { PortfolioSegment } from "@/components/reports/templates/portfolio-segment";
import { CapitalAllocation } from "@/components/reports/templates/capital-allocation";
import { CreditRating } from "@/components/reports/templates/credit-rating";
import { BurnRate } from "@/components/reports/templates/burn-rate";
import { MonthlyFinance } from "@/components/reports/templates/monthly-finance";
import { KpiDashboard } from "@/components/reports/templates/kpi-dashboard";
import { YearEndLetter } from "@/components/reports/templates/year-end-letter";

const TEMPLATES = {
  "weekly-memo": { component: WeeklyMemo, title: "Weekly Memo" },
  "brag-card": { component: BragCard, title: "Brag Card" },
  "morning-brief-plus": { component: MorningBriefPlus, title: "Morning Brief Plus" },
  "earnings-prebrief": { component: EarningsPrebrief, title: "Earnings Pre-Brief" },
  "risk-board": { component: RiskBoard, title: "Risk Board" },
  "quarterly-self-report": { component: QuarterlySelfReport, title: "Quarterly Self Report" },
  "self-audit": { component: SelfAudit, title: "Self Audit" },
  "dd-checklist": { component: DdChecklist, title: "DD Checklist" },
  "dividend-income": { component: DividendIncome, title: "Dividend Income" },
  "insider-mirror": { component: InsiderMirror, title: "Insider Mirror" },
  "sp500-backtest": { component: Sp500Backtest, title: "S&P 500 Backtest" },
  "portfolio-segment": { component: PortfolioSegment, title: "Portfolio Segment" },
  "capital-allocation": { component: CapitalAllocation, title: "Capital Allocation" },
  "credit-rating": { component: CreditRating, title: "Credit Rating" },
  "burn-rate": { component: BurnRate, title: "Burn Rate" },
  "monthly-finance": { component: MonthlyFinance, title: "Monthly Finance" },
  "kpi-dashboard": { component: KpiDashboard, title: "KPI Dashboard" },
  "year-end-letter": { component: YearEndLetter, title: "Year-End Letter" },
} as const;

type Slug = keyof typeof TEMPLATES;

export function generateStaticParams() {
  return Object.keys(TEMPLATES).map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const entry = TEMPLATES[slug as Slug];
  return {
    title: entry ? `${entry.title} · PivoxQuant` : "Report · PivoxQuant",
  };
}

export default async function SampleReportPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const entry = TEMPLATES[slug as Slug];
  if (!entry) notFound();
  const Template = entry.component;
  return (
    <ReportSurface>
      <PdfToolbar />
      <Template />
    </ReportSurface>
  );
}
