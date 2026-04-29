"use client";

/**
 * /reports/preview/capital-allocation — Wave 2 (2026-04-29).
 * Premium tier. Backend type: `capital_allocation`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  CapitalAllocation,
  type CapitalAllocationData,
} from "@/components/reports/templates/capital-allocation";

export default function CapitalAllocationPreviewPage() {
  return (
    <ReportPreviewShell<CapitalAllocationData>
      type="capital_allocation"
      tier="premium"
      emptyReason="no_positions"
      render={(data) => <CapitalAllocation data={data} />}
    />
  );
}
