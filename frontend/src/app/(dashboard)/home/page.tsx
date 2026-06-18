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

import dynamic from "next/dynamic";
import HomePageV2 from "./_v2/page-v2";

// V1 is lazy-loaded — V2 is the active default (NEXT_PUBLIC_HOME_V2=true).
// Keeping V1 in the initial bundle costs ~10KB+ gzip per page; dynamic import
// splits it into a separate chunk that is only fetched when the flag is off.
// SSR remains enabled (default) so behavior is unchanged.
const HomePageV1 = dynamic(() => import("./_v1/page-v1"));

// 거울 promotion (2026-06-15): when NEXT_PUBLIC_MIRROR_HOME=true the
// behavioural Mirror becomes the home surface (strategy: mirror as spine).
// Default off → the existing V1/V2 home is unchanged in prod until the env
// var is flipped, so this is a one-variable, fully reversible promotion.
const MirrorHome = dynamic(() => import("../mirror/page"));

export default function HomePage() {
  if (process.env.NEXT_PUBLIC_MIRROR_HOME === "true") return <MirrorHome />;
  const v2Enabled = process.env.NEXT_PUBLIC_HOME_V2 === "true";
  return v2Enabled ? <HomePageV2 /> : <HomePageV1 />;
}
