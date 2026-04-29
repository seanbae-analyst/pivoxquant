"use client";

/**
 * /reports/preview/kpi-dashboard — Wave 2 (2026-04-29).
 * Free tier. Real-data wired via <ReportPreviewShell />.
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
      tier="free"
      emptyReason="no_positions"
      render={(data) => <KpiDashboard data={data} />}
    />
  );
}
