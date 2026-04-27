/**
 * /reports/preview/credit-rating — Report 14 (Premium · Quarterly · 3 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { CreditRating } from "@/components/reports/templates/credit-rating";

export const metadata = {
  title: "Credit Rating · PivoxQuant",
};

export default function CreditRatingPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <CreditRating />
    </ReportSurface>
  );
}
