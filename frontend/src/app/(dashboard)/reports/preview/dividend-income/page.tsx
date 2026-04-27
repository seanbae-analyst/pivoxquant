/**
 * /reports/preview/dividend-income — Report 09 (Pro · Monthly · 1 page)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { DividendIncome } from "@/components/reports/templates/dividend-income";

export const metadata = {
  title: "Dividend Income · PivoxQuant",
};

export default function DividendIncomePreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <DividendIncome />
    </ReportSurface>
  );
}
