/**
 * /reports/preview/insider-mirror — Report 10 (Pro · Weekly · 2 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { InsiderMirror } from "@/components/reports/templates/insider-mirror";

export const metadata = {
  title: "Insider Mirror · PivoxQuant",
};

export default function InsiderMirrorPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <InsiderMirror />
    </ReportSurface>
  );
}
