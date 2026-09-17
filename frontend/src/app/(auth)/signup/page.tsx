"use client";

/**
 * /signup — alias of the unified auth entry screen.
 *
 * 2026-09-17 (CEO decision): 로그인과 시작하기는 같은 화면으로 간다.
 *
 * Both routes always pointed at the same `API.auth.google` / `API.auth.kakao`
 * anchors, and the backend callback provisions an account when none exists —
 * so /login and /signup were two decorations on one path. The canonical
 * surface now lives in `../login/page.tsx` and this route renders it verbatim.
 *
 * Why a render and not a redirect:
 * - Backend `_safe_next()`, the OAuth redirect targets and existing user
 *   bookmarks all still use /signup. A redirect would add a round trip and
 *   lose `?error=` / `?expired=` query params on the way.
 * - Both URLs must keep answering 200.
 *
 * What left this file (733 lines → this):
 * - The 4 required + 1 optional consent stack, the birth-date field and all
 *   of their state/validation. Required consents are now collected after
 *   OAuth, from new accounts only, on the post-callback interstitial
 *   (`signup/oauth-finalize`). Asking before OAuth made every returning user
 *   re-consent to sign in, and asked consent from people who never finished
 *   provisioning.
 *
 * What stayed: the OAuth entry itself, via the unified screen.
 */

import AuthEntryPage from "../login/page";

export default function SignupPage() {
  return <AuthEntryPage />;
}
