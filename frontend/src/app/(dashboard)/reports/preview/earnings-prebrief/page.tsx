"use client";

/**
 * /reports/preview/earnings-prebrief — Wave 2 (2026-04-29).
 * Pro tier. Backend type: `earnings_prebrief`.
 *
 * COMPLIANCE NOTE: Quant Signal block uses POSITIVE / NEGATIVE / NEUTRAL
 * labels (NEVER BUY/SELL/HOLD). Enforced inside the template.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  EarningsPrebrief,
  type EarningsPrebriefData,
} from "@/components/reports/templates/earnings-prebrief";

export default function EarningsPrebriefPreviewPage() {
  return (
    <ReportPreviewShell<EarningsPrebriefData>
      type="earnings_prebrief"
      tier="pro"
      emptyReason="not_in_portfolio"
      render={(data) => <EarningsPrebrief data={data} />}
    />
  );
}
