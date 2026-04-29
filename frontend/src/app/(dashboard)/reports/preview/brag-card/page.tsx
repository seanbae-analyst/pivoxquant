"use client";

/**
 * /reports/preview/brag-card
 *
 * Wave 2 (2026-04-29) — wired to real artifact data via <ReportPreviewShell />.
 * Free tier. Backend artifact type: `brag_card` (Wave 1 dispatch).
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  BragCard,
  type BragCardData,
} from "@/components/reports/templates/brag-card";

export default function BragCardPreviewPage() {
  return (
    <ReportPreviewShell<BragCardData>
      type="brag_card"
      tier="free"
      emptyReason="no_trades"
      render={(data) => <BragCard data={data} />}
    />
  );
}
