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

import V1 from "./_v1/page-v1";
import V2 from "./_v2/page-v2";

export default function RiskPage() {
  const v2Enabled = process.env.NEXT_PUBLIC_RISK_V2 === "true";
  return v2Enabled ? <V2 /> : <V1 />;
}
