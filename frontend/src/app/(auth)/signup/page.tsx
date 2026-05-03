"use client";

/**
 * /signup — feature-flag toggle between V1 (slate/Geist) and V2 (Vantablack).
 *
 * Set NEXT_PUBLIC_SIGNUP_V2=true to render the editorial Vantablack layout.
 * Default (unset / false) keeps the existing V1 page intact.
 *
 * V1 lives at ./_v1/page-v1.tsx (verbatim copy, export rename only).
 * V2 lives at ./_v2/page-v2.tsx (editorial split layout per v3 lock-in).
 *
 * OAuth flow + consent gating + localStorage persistence are identical
 * across both — only the visual layer differs.
 */

import dynamic from "next/dynamic";
import SignupPageV1 from "./_v1/page-v1";

// V2 is lazy-loaded — V1 is the active default (NEXT_PUBLIC_SIGNUP_V2 unset).
// Splits the dormant V2 Vantablack split layout into its own chunk so the
// initial bundle only carries the rendered variant. SSR remains enabled.
const SignupPageV2 = dynamic(() => import("./_v2/page-v2"));

export default function SignupPage() {
  const v2Enabled = process.env.NEXT_PUBLIC_SIGNUP_V2 === "true";
  return v2Enabled ? <SignupPageV2 /> : <SignupPageV1 />;
}
