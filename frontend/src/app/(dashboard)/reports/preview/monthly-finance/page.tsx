"use client";

/**
 * /reports/preview/monthly-finance — Wave 2 (2026-04-29).
 * Premium tier. Backend type: `monthly_finance`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  MonthlyFinance,
  type MonthlyFinanceData,
} from "@/components/reports/templates/monthly-finance";

export default function MonthlyFinancePreviewPage() {
  return (
    <ReportPreviewShell<MonthlyFinanceData>
      type="monthly_finance"
      tier="premium"
      emptyReason="no_trades"
      render={(data) => <MonthlyFinance data={data} />}
    />
  );
}
