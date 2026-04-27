/**
 * /reports/preview/brag-card
 *
 * Print-ready preview of Report 03 — Brag Card (Free · Monthly).
 */

import {
  ReportSurface,
  PdfToolbar,
} from "@/components/reports/pdf-primitives";
import { BragCard } from "@/components/reports/templates/brag-card";

export const metadata = {
  title: "Brag Card · PivoxQuant",
};

export default function BragCardPreviewPage() {
  return (
    <ReportSurface>
      <PdfToolbar />
      <BragCard />
    </ReportSurface>
  );
}
