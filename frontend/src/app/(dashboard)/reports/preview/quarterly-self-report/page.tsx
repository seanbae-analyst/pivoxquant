"use client";

/**
 * /reports/preview/quarterly-self-report — Wave 2 (2026-04-29).
 * Pro tier. Backend type: `quarterly_self_report`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  QuarterlySelfReport,
  type QuarterlySelfReportData,
} from "@/components/reports/templates/quarterly-self-report";

export default function QuarterlySelfReportPreviewPage() {
  return (
    <ReportPreviewShell<QuarterlySelfReportData>
      type="quarterly_self_report"
      tier="pro"
      emptyReason="insufficient_history"
      render={(data) => <QuarterlySelfReport data={data} />}
    />
  );
}
