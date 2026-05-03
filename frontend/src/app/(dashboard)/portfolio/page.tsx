"use client";

/**
 * /portfolio — feature-flag toggle between V1 (ledger binder) and V2 (gallery).
 *
 * Set NEXT_PUBLIC_PORTFOLIO_V2=true to render the v2 layout.
 * Default (unset / false) keeps the existing V1 dossier intact.
 *
 * V1 lives at ./_v1/page-v1.tsx (behavior preserved 1:1).
 * V2 lives at ./_v2/page-v2.tsx (gallery shell per portfolio-v2 SPEC.md).
 *
 * Legal disclaimer + DisclaimerBanner are mounted by (dashboard)/layout.tsx,
 * not by either variant — single source of truth preserved.
 */

import dynamic from "next/dynamic";
import PortfolioPageV2 from "./_v2/page-v2";

// V1 is lazy-loaded — V2 is the active default (NEXT_PUBLIC_PORTFOLIO_V2=true).
// Splits the dormant V1 ledger into its own chunk so the initial bundle
// only carries the rendered variant. SSR remains enabled (default).
const PortfolioPageV1 = dynamic(() => import("./_v1/page-v1"));

export default function PortfolioPage() {
  const v2Enabled = process.env.NEXT_PUBLIC_PORTFOLIO_V2 === "true";
  return v2Enabled ? <PortfolioPageV2 /> : <PortfolioPageV1 />;
}
