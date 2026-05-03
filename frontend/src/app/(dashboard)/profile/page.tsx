"use client";

/**
 * /profile — feature-flag toggle between v1 (legacy) and v2 (editorial).
 *
 * Set NEXT_PUBLIC_PROFILE_V2=true to render the editorial 8-block layout
 * (mockup: frontend/design-mockups/profile-v2/{mockup.html, SPEC.md, MIGRATION.md}).
 * Default (unset / false) keeps the existing v1 page intact — no behavior change.
 *
 * v1 lives at ./_v1/page-v1.tsx (verbatim copy of legacy page).
 * v2 lives at ./_v2/page-v2.tsx (editorial 8-block).
 *
 * Mirrors the home-v2 / portfolio-v2 / risk-v2 / signals-v2 / settings-v2 toggle pattern.
 *
 * Legal: persona vocabulary only. No advice/recommend strings.
 */

import dynamic from "next/dynamic";
import ProfilePageV1 from "./_v1/page-v1";

// V2 is lazy-loaded — V1 is the active default (NEXT_PUBLIC_PROFILE_V2 unset).
// Splits the dormant V2 editorial layout into its own chunk so the initial
// bundle only carries the rendered variant. SSR remains enabled (default).
const ProfilePageV2 = dynamic(() => import("./_v2/page-v2"));

export default function ProfilePage() {
  const v2Enabled = process.env.NEXT_PUBLIC_PROFILE_V2 === "true";
  return v2Enabled ? <ProfilePageV2 /> : <ProfilePageV1 />;
}
