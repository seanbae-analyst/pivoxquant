/**
 * /reports/preview/earnings-prebrief
 *
 * Print-ready preview of Report 04 — Earnings Pre-Brief (Pro · Per-event · 2 pages).
 *
 * COMPLIANCE NOTE: The Quant Signal block uses POSITIVE / NEGATIVE / NEUTRAL
 * labels (NEVER BUY/SELL/HOLD). See templates/earnings-prebrief.tsx for the
 * compliance-fixed version of the original PDF mock.
 */

import {
  ReportSurface,
  PdfToolbar,
} from "@/components/reports/pdf-primitives";
import { EarningsPrebrief } from "@/components/reports/templates/earnings-prebrief";

export const metadata = {
  title: "Earnings Pre-Brief · PivoxQuant",
};

export default function EarningsPrebriefPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <EarningsPrebrief />
    </ReportSurface>
  );
}
