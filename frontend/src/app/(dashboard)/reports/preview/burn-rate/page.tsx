/**
 * /reports/preview/burn-rate — Report 15 (Premium · Monthly · 2 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { BurnRate } from "@/components/reports/templates/burn-rate";

export const metadata = {
  title: "Burn Rate · PivoxQuant",
};

export default function BurnRatePreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <BurnRate />
    </ReportSurface>
  );
}
