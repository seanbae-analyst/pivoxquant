"use client";

/**
 * /reports/preview/credit-rating — Wave 2 (2026-04-29).
 * Premium tier. Backend type: `credit_rating`.
 */

import { ReportPreviewShell } from "@/components/reports/report-preview-shell";
import {
  CreditRating,
  type CreditRatingData,
} from "@/components/reports/templates/credit-rating";

export default function CreditRatingPreviewPage() {
  return (
    <ReportPreviewShell<CreditRatingData>
      type="credit_rating"
      tier="premium"
      emptyReason="not_in_portfolio"
      render={(data) => <CreditRating data={data} />}
    />
  );
}
