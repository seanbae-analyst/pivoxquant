"use client";

/**
 * /reports/preview/insider-mirror — Wave 2 (2026-04-29).
 * Pro tier. Backend type: `insider_mirror`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  InsiderMirror,
  type InsiderMirrorData,
} from "@/components/reports/templates/insider-mirror";

export default function InsiderMirrorPreviewPage() {
  return (
    <ReportPreviewShell<InsiderMirrorData>
      type="insider_mirror"
      tier="pro"
      emptyReason="not_in_portfolio"
      render={(data) => <InsiderMirror data={data} />}
    />
  );
}
