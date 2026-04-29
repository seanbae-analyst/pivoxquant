"use client";

/**
 * /reports/preview/sp500-backtest — Wave 2 (2026-04-29).
 * Pro tier. Backend type: `sp500_backtest`.
 *
 * Note: §101 회색지대 — backend-dev wave handles per-user data scoping
 * separately. Frontend tier-gates the surface; data fetch is via standard
 * useArtifacts hook (server enforces ownership).
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  Sp500Backtest,
  type Sp500BacktestData,
} from "@/components/reports/templates/sp500-backtest";

export default function Sp500BacktestPreviewPage() {
  return (
    <ReportPreviewShell<Sp500BacktestData>
      type="sp500_backtest"
      tier="pro"
      emptyReason="no_artifact"
      render={(data) => <Sp500Backtest data={data} />}
    />
  );
}
