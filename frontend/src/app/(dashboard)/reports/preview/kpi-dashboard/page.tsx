"use client";

/**
 * /reports/preview/kpi-dashboard — Wave 2 (2026-04-29).
 * Premium tier (B2 pricing-page alignment 2026-06-11 — the pricing page
 * sells KPI Dashboard under Premium; "Free tier" here was Wave-2 drift).
 * Real-data wired via <ReportPreviewShell />.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  KpiDashboard,
  type KpiDashboardData,
} from "@/components/reports/templates/kpi-dashboard";

export default function KpiDashboardPreviewPage() {
  return (
    <ReportPreviewShell<KpiDashboardData>
      type="kpi_dashboard"
      tier="premium"
      emptyReason="no_positions"
      render={(data) => <KpiDashboard data={data} />}
    />
  );
}
