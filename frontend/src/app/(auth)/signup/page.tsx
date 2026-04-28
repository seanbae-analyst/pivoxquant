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

import SignupPageV1 from "./_v1/page-v1";
import SignupPageV2 from "./_v2/page-v2";

export default function SignupPage() {
  const v2Enabled = process.env.NEXT_PUBLIC_SIGNUP_V2 === "true";
  return v2Enabled ? <SignupPageV2 /> : <SignupPageV1 />;
}
