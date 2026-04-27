/**
 * /reports/preview/year-end-letter — Report 18 (Premium · Annual · 5 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { YearEndLetter } from "@/components/reports/templates/year-end-letter";

export const metadata = {
  title: "Year-End Letter · PivoxQuant",
};

export default function YearEndLetterPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <YearEndLetter />
    </ReportSurface>
  );
}
