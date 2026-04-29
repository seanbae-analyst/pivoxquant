"use client";

/**
 * /reports/preview/risk-board — Wave 2 (2026-04-29).
 * Pro tier. Backend type: `risk_board`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  RiskBoard,
  type RiskBoardData,
} from "@/components/reports/templates/risk-board";

export default function RiskBoardPreviewPage() {
  return (
    <ReportPreviewShell<RiskBoardData>
      type="risk_board"
      tier="pro"
      emptyReason="no_positions"
      render={(data) => <RiskBoard data={data} />}
    />
  );
}
