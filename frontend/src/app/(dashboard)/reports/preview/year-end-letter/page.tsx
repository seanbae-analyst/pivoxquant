"use client";

/**
 * /reports/preview/year-end-letter — Wave 2 (2026-04-29).
 * Premium tier. Backend type: `year_end_letter`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  YearEndLetter,
  type YearEndLetterData,
} from "@/components/reports/templates/year-end-letter";

export default function YearEndLetterPreviewPage() {
  return (
    <ReportPreviewShell<YearEndLetterData>
      type="year_end_letter"
      tier="premium"
      emptyReason="insufficient_history"
      render={(data) => <YearEndLetter data={data} />}
    />
  );
}
