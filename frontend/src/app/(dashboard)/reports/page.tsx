"use client";

/**
 * /reports — feature-flag toggle between v1 and v2.
 *
 * v1 (default) preserves the legacy "Dossier" / 18-CATALOG library page
 * with tier-gating, persona filter, SectionFeedbackBar, PeerBenchmarkBlock,
 * and the liveByType Map (live artifact → catalog mapping).
 *
 * v2 (NEXT_PUBLIC_REPORTS_V2=true) is the new "CFO Archive" editorial
 * surface — hero + latest artifact + 6-card gallery + request box + year
 * timeline. The 18 `/reports/preview/*` sub-routes remain mounted in both
 * variants (untouched).
 *
 * Mirrors signals-v2 / risk-v2 / portfolio-v2 / home-v2 toggle pattern.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. DisclaimerBanner mounted by
 * (dashboard)/layout.tsx — never render twice.
 */

import V1 from "./_v1/page-v1";
import V2 from "./_v2/page-v2";

export default function ReportsPage() {
  const v2Enabled = process.env.NEXT_PUBLIC_REPORTS_V2 === "true";
  return v2Enabled ? <V2 /> : <V1 />;
}
