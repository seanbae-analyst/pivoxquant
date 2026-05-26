/**
 * Server-side backend fetch (RSC / generateMetadata). Unlike the browser
 * `apiFetch`, server components can't use the Next rewrite proxy with a
 * relative path — they need an absolute backend origin. We resolve it the
 * same way next.config.ts does so prod (Railway) and local dev both work.
 *
 * Only used by PUBLIC, unauthenticated endpoints (the OG card landing). No
 * cookies are forwarded — these routes must work for a logged-out recipient
 * and for social-media crawlers.
 */

/** Absolute backend origin, mirroring next.config.ts BACKEND_URL logic. */
function backendOrigin(): string {
  const explicit = process.env.NEXT_PUBLIC_API_URL;
  if (explicit) return explicit.replace(/\/$/, "");
  if (process.env.VERCEL) {
    const railway = process.env.RAILWAY_BACKEND_URL;
    return railway ? railway.replace(/\/$/, "") : "";
  }
  return "http://localhost:5050";
}

/**
 * Fetch a PUBLIC backend JSON endpoint from a server component. Returns the
 * parsed body on 2xx, or `null` on any non-2xx / network / parse error so
 * callers can render a clean fallback (e.g. card not found / private).
 *
 * `revalidate` controls Next's data cache (seconds). Public cards are
 * effectively immutable per share_token, so a short positive value is fine.
 */
export async function serverGetPublic<T>(
  path: string,
  opts?: { revalidate?: number },
): Promise<T | null> {
  const origin = backendOrigin();
  // No origin configured (misconfigured prod env) → fail soft to fallback.
  if (!origin) return null;
  const url = `${origin}${path.startsWith("/") ? "" : "/"}${path}`;
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/json" },
      next: { revalidate: opts?.revalidate ?? 300 },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
