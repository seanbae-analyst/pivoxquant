/**
 * /reports/preview/sp500-backtest — Report 11 (Pro · On-demand · 2 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { Sp500Backtest } from "@/components/reports/templates/sp500-backtest";

export const metadata = {
  title: "S&P 500 Backtest · PivoxQuant",
};

export default function Sp500BacktestPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <Sp500Backtest />
    </ReportSurface>
  );
}
