"use client";

/**
 * /risk — feature-flag toggle between v1 and v2.
 *
 * v1 (default) preserves the legacy ink-card terminal page (4 KPI stats,
 * 7-Layer ladder, Correlation heatmap, Rolling VaR chart, Methodology).
 *
 * v2 (NEXT_PUBLIC_RISK_V2=true) is the new editorial "Risk Board" — hero
 * + 4 big gauges + 7-layer breakdown + concentration + sector + 30-day
 * timeline. Mirrors the home-v2 / portfolio-v2 toggle pattern.
 *
 * No banned UI strings. POSITIVE / NEGATIVE / NEUTRAL only.
 */

import dynamic from "next/dynamic";
import V2 from "./_v2/page-v2";

// V1 is lazy-loaded — V2 is the active default (NEXT_PUBLIC_RISK_V2=true).
// Splits the dormant V1 risk terminal into its own chunk so the initial
// bundle only carries the rendered variant. SSR remains enabled (default).
const V1 = dynamic(() => import("./_v1/page-v1"));

// NOTE: no page-level DisclaimerBanner here. The (dashboard)/layout.tsx mounts
// the legal disclaimer once per route (at the bottom, type "signal" for /risk).
// A duplicate top banner was removed 2026-05-24 (CEO) — the layout banner is
// the single source, so /risk still shows the required disclaimer.
export default function RiskPage() {
  const v2Enabled = process.env.NEXT_PUBLIC_RISK_V2 === "true";
  return v2Enabled ? <V2 /> : <V1 />;
}
