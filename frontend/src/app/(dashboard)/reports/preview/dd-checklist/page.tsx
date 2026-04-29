"use client";

/**
 * /reports/preview/dd-checklist — Wave 2 (2026-04-29).
 * Free tier · interactive (user-filled). Backend type: `dd_checklist`.
 * Empty reason `interactive` — checklist requires user input to populate.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  DdChecklist,
  type DdChecklistData,
} from "@/components/reports/templates/dd-checklist";

export default function DdChecklistPreviewPage() {
  return (
    <ReportPreviewShell<DdChecklistData>
      type="dd_checklist"
      tier="free"
      emptyReason="interactive"
      render={(data) => <DdChecklist data={data} />}
    />
  );
}
