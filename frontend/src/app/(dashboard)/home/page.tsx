"use client";

/**
 * /home — feature-flag toggle between V1 (terminal) and V2 (gallery).
 *
 * Set NEXT_PUBLIC_HOME_V2=true to render the gallery layout.
 * Default (unset / false) keeps the existing V1 terminal intact.
 *
 * V1 lives at ./_v1/page-v1.tsx (1140 lines, behavior preserved 1:1).
 * V2 lives at ./_v2/page-v2.tsx (gallery shell per home-v2 SPEC.md).
 *
 * Legal disclaimer + DisclaimerBanner are mounted by (dashboard)/layout.tsx,
 * not by either variant — single source of truth preserved.
 */

import HomePageV1 from "./_v1/page-v1";
import HomePageV2 from "./_v2/page-v2";

export default function HomePage() {
  const v2Enabled = process.env.NEXT_PUBLIC_HOME_V2 === "true";
  return v2Enabled ? <HomePageV2 /> : <HomePageV1 />;
}
