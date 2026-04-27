/**
 * /reports/preview/monthly-finance — Report 16 (Premium · Monthly · 4 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { MonthlyFinance } from "@/components/reports/templates/monthly-finance";

export const metadata = {
  title: "Monthly Finance · PivoxQuant",
};

export default function MonthlyFinancePreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <MonthlyFinance />
    </ReportSurface>
  );
}
