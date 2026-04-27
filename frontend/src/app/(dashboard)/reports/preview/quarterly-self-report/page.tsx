/**
 * /reports/preview/quarterly-self-report — Report 06 (Pro · Quarterly · 2 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { QuarterlySelfReport } from "@/components/reports/templates/quarterly-self-report";

export const metadata = {
  title: "Quarterly Self Report · PivoxQuant",
};

export default function QuarterlySelfReportPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <QuarterlySelfReport />
    </ReportSurface>
  );
}
