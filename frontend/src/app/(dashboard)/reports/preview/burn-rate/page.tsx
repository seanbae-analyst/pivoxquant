"use client";

/**
 * /reports/preview/burn-rate — Wave 2 (2026-04-29).
 * Premium tier. Backend type: `burn_rate`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  BurnRate,
  type BurnRateData,
} from "@/components/reports/templates/burn-rate";

export default function BurnRatePreviewPage() {
  return (
    <ReportPreviewShell<BurnRateData>
      type="burn_rate"
      tier="premium"
      emptyReason="no_positions"
      render={(data) => <BurnRate data={data} />}
    />
  );
}
