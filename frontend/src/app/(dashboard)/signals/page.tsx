"use client";

/**
 * /signals — feature-flag toggle between v1 and v2.
 *
 * v1 (default) preserves the legacy "Clip Board" page (3 ClipboardPaper
 * stack with SignalMemoStrip 4-pillar expansion + filter pills + Refresh).
 *
 * v2 (NEXT_PUBLIC_SIGNALS_V2=true) is the new editorial "Signals stream"
 * — hero + filter bar + top movers + timeline. Mirrors the home-v2 /
 * risk-v2 / portfolio-v2 toggle pattern.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. Both variants share the
 * single DisclaimerBanner mounted by (dashboard)/layout.tsx.
 */

import dynamic from "next/dynamic";
import V2 from "./_v2/page-v2";

// V1 is lazy-loaded — V2 is the active default (NEXT_PUBLIC_SIGNALS_V2=true).
// Splits the dormant V1 clip-board into its own chunk so the initial bundle
// only carries the rendered variant. SSR remains enabled (default).
const V1 = dynamic(() => import("./_v1/page-v1"));

export default function SignalsPage() {
  const v2Enabled = process.env.NEXT_PUBLIC_SIGNALS_V2 === "true";
  return v2Enabled ? <V2 /> : <V1 />;
}
