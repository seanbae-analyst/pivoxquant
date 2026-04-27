/**
 * /reports/preview/morning-brief-plus — Report 02 (Free · Daily · 1 page)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { MorningBriefPlus } from "@/components/reports/templates/morning-brief-plus";

export const metadata = {
  title: "Morning Brief Plus · PivoxQuant",
};

export default function MorningBriefPlusPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <MorningBriefPlus />
    </ReportSurface>
  );
}
