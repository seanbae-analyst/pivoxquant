"use client";

/**
 * /reports/preview/portfolio-segment — Wave 2 (2026-04-29).
 * Pro tier. Backend type: `portfolio_segment`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  PortfolioSegment,
  type PortfolioSegmentData,
} from "@/components/reports/templates/portfolio-segment";

export default function PortfolioSegmentPreviewPage() {
  return (
    <ReportPreviewShell<PortfolioSegmentData>
      type="portfolio_segment"
      tier="pro"
      emptyReason="no_positions"
      render={(data) => <PortfolioSegment data={data} />}
    />
  );
}
