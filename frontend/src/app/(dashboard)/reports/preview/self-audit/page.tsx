"use client";

/**
 * /reports/preview/self-audit — Wave 2 (2026-04-29).
 * Pro tier. Backend type: `self_audit`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  SelfAudit,
  type SelfAuditData,
} from "@/components/reports/templates/self-audit";

export default function SelfAuditPreviewPage() {
  return (
    <ReportPreviewShell<SelfAuditData>
      type="self_audit"
      tier="pro"
      emptyReason="no_trades"
      render={(data) => <SelfAudit data={data} />}
    />
  );
}
