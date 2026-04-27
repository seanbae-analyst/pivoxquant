/**
 * /reports/preview/capital-allocation — Report 13 (Premium · Quarterly · 4 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { CapitalAllocation } from "@/components/reports/templates/capital-allocation";

export const metadata = {
  title: "Capital Allocation · PivoxQuant",
};

export default function CapitalAllocationPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <CapitalAllocation />
    </ReportSurface>
  );
}
