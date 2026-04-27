/**
 * /reports/preview/kpi-dashboard — Report 17 (Premium · Monthly · 3 pages)
 * NOTE: Page 1 is the only DARK IC-pack cover in the 18-report system.
 */

import { ReportSurface, PdfToolbar } from "@/components/reports/pdf-primitives";
import { KpiDashboard } from "@/components/reports/templates/kpi-dashboard";

export const metadata = {
  title: "KPI Dashboard · PivoxQuant",
};

export default function KpiDashboardPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <KpiDashboard />
    </ReportSurface>
  );
}
