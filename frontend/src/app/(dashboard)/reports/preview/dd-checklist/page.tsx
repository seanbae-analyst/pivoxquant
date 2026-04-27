/**
 * /reports/preview/dd-checklist
 *
 * Print-ready preview of Report 08 — DD Checklist (Pro).
 * Cmd/Ctrl+P → Save as PDF works directly from this route.
 */

import {
  ReportSurface,
  PdfToolbar,
} from "@/components/reports/pdf-primitives";
import { DdChecklist } from "@/components/reports/templates/dd-checklist";

export const metadata = {
  title: "DD Checklist · PivoxQuant",
};

export default function DdChecklistPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <DdChecklist />
    </ReportSurface>
  );
}
