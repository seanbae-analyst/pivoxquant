"use client";

/**
 * /reports/preview/weekly-memo
 *
 * Wave 2 (2026-04-29) — wired to real artifact data via <ReportPreviewShell />.
 * Free tier. Falls back to <EmptyState reason="no_artifact" /> when the
 * user has no weekly memo yet.
 *
 * Cmd/Ctrl+P → Save as PDF works directly from this route when an
 * artifact is present.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  WeeklyMemo,
  type WeeklyMemoData,
} from "@/components/reports/templates/weekly-memo";

export default function WeeklyMemoPreviewPage() {
  return (
    <ReportPreviewShell<WeeklyMemoData>
      type="weekly_memo"
      tier="free"
      render={(data) => <WeeklyMemo data={data} />}
    />
  );
}
