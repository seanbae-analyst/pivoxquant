"use client";

/**
 * /home
 *
 * 거울 promotion (2026-06-15): when NEXT_PUBLIC_MIRROR_HOME=true the
 * behavioural Mirror becomes the home surface (strategy: mirror as spine).
 * Otherwise the gallery surface in ./home-surface.tsx renders. One variable,
 * fully reversible.
 *
 * Legal disclaimer + DisclaimerBanner are mounted by (dashboard)/layout.tsx,
 * not by the surface — single source of truth preserved.
 */

import dynamic from "next/dynamic";

import HomeSurface from "./home-surface";

const MirrorHome = dynamic(() => import("../mirror/page"));

export default function HomePage() {
  if (process.env.NEXT_PUBLIC_MIRROR_HOME === "true") return <MirrorHome />;
  return <HomeSurface />;
}
