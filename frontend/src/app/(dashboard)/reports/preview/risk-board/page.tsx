/**
 * /reports/preview/risk-board — Report 05 (Pro · Weekly · 2 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { RiskBoard } from "@/components/reports/templates/risk-board";

export const metadata = {
  title: "Risk Board · PivoxQuant",
};

export default function RiskBoardPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <RiskBoard />
    </ReportSurface>
  );
}
