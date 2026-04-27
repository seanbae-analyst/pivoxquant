/**
 * /reports/preview/portfolio-segment — Report 12 (Pro · Monthly · 2 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { PortfolioSegment } from "@/components/reports/templates/portfolio-segment";

export const metadata = {
  title: "Portfolio Segment · PivoxQuant",
};

export default function PortfolioSegmentPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <PortfolioSegment />
    </ReportSurface>
  );
}
