/**
 * safeNext — only same-origin, path-absolute redirect targets.
 *
 * 2026-09-10: /signup/oauth-finalize passed the raw `?next=` query param to
 * router.replace(). Next treats a cross-origin URL as external and calls
 * location.replace, so `?next=https://evil.example` left the site right after
 * sign-in (an open redirect; the backend's _safe_next was never consulted).
 */
export function safeNext(raw: string | null | undefined, fallback = "/mirror"): string {
  if (typeof raw !== "string") return fallback;
  const v = raw.trim();
  // Path-absolute only. Reject protocol-relative ("//host"), backslash tricks
  // ("/\\host", which some browsers normalise to "//host"), and control chars.
  if (!v.startsWith("/") || v.startsWith("//") || v.startsWith("/\\")) return fallback;
  if (/[\u0000-\u001f\u007f]/.test(v)) return fallback;
  return v;
}
