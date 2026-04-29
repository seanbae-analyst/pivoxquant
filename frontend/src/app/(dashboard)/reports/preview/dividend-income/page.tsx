"use client";

/**
 * /reports/preview/dividend-income — Wave 2 (2026-04-29).
 * Pro tier. Backend type: `dividend_income`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  DividendIncome,
  type DividendIncomeData,
} from "@/components/reports/templates/dividend-income";

export default function DividendIncomePreviewPage() {
  return (
    <ReportPreviewShell<DividendIncomeData>
      type="dividend_income"
      tier="pro"
      emptyReason="no_positions"
      render={(data) => <DividendIncome data={data} />}
    />
  );
}
