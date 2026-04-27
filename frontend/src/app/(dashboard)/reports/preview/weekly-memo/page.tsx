/**
 * /reports/preview/weekly-memo
 *
 * Print-ready preview of Report 01 — Weekly Memo (Free).
 * Uses the .pq-report scope so Source Serif 4 + ink palette take effect.
 * Cmd/Ctrl+P → Save as PDF works directly from this route.
 */

import {
  ReportSurface,
  PdfToolbar,
} from "@/components/reports/pdf-primitives";
import { WeeklyMemo } from "@/components/reports/templates/weekly-memo";

export const metadata = {
  title: "Weekly Memo · PivoxQuant",
};

export default function WeeklyMemoPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <WeeklyMemo />
    </ReportSurface>
  );
}
