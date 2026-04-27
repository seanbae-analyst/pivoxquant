/**
 * /reports/preview/self-audit — Report 07 (Pro · On-demand · 2 pages)
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { SelfAudit } from "@/components/reports/templates/self-audit";

export const metadata = {
  title: "Self Audit · PivoxQuant",
};

export default function SelfAuditPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <SelfAudit />
    </ReportSurface>
  );
}
