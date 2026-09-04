import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SUPPORTED_LOCALES = ["ko", "en"] as const;
type Locale = (typeof SUPPORTED_LOCALES)[number];
const DEFAULT_LOCALE: Locale = "ko";
const LOCALE_COOKIE = "sp_locale";

/**
 * Detect preferred locale from cookie first, then Accept-Language header.
 * Falls back to DEFAULT_LOCALE ("ko").
 */
function detectLocale(request: NextRequest): Locale {
  // 1. Cookie takes priority (user's explicit choice)
  const cookie = request.cookies.get(LOCALE_COOKIE)?.value;
  if (cookie === "en" || cookie === "ko") return cookie;

  // 2. Accept-Language header
  const acceptLang = request.headers.get("accept-language") ?? "";
  const preferred = acceptLang
    .split(",")
    .map((s) => s.split(";")[0].trim().toLowerCase().slice(0, 2))
    .find((code) => SUPPORTED_LOCALES.includes(code as Locale));

  return (preferred as Locale | undefined) ?? DEFAULT_LOCALE;
}

export async function middleware(request: NextRequest) {
  // ─── Locale: set cookie if missing (no URL rewriting for now) ────────────
  const locale = detectLocale(request);
  const hasCookie = !!request.cookies.get(LOCALE_COOKIE)?.value;

  // ─── CSP ─────────────────────────────────────────────────────────────────
  // Per-request nonce (B7 migration 2026-05-02). The base64-encoded UUID is
  // injected into the request headers as `x-nonce`; Next.js 16 reads that
  // header and automatically attaches it to its emitted inline bootstrap
  // scripts (hydration payload, `__next_f` flight chunks). Manually authored
  // inline `<script>` tags must read the nonce via `headers().get("x-nonce")`
  // in `next/headers` and pass it as the `nonce` prop. See app/layout.tsx.
  //
  // `script-src` drops 'unsafe-inline' in prod and uses `'nonce-…'` +
  // `'strict-dynamic'` instead — strict-dynamic lets a nonced script load
  // further chunks transitively without us having to enumerate every CDN.
  // Modern browsers honor strict-dynamic and ignore the host allowlist;
  // legacy browsers ignore strict-dynamic and fall back to the host list,
  // so 'self' is kept for safety.
  //
  // `style-src` MUST keep 'unsafe-inline' — Tailwind 4 inlines arbitrary
  // utility styles and shadcn/Radix primitives set inline `style` props.
  // Migrating styles is a separate, larger effort.
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");

  const isDev = process.env.NODE_ENV === "development";
  // Backend host allowance. 2026-09-01: this said `https://*.railway.app`,
  // but that account was deleted and the backend moves to Render
  // (render.yaml). Today every call is same-origin — `lib/endpoints.ts` sets
  // `API_BASE = ""` and Next rewrites proxy /api → backend, so `'self'`
  // already covers the API and the portfolio SSE stream. The host entry only
  // matters the moment something connects to the backend origin DIRECTLY.
  // Keeping a dead platform there would fail that first direct call silently
  // (CSP violations are console-only), so it now names the real one.
  const backendHost = "https://*.onrender.com";
  const connectSrc = isDev
    ? `'self' http://localhost:5050 ws://localhost:3000 ws://localhost:* ${backendHost} https://cdn.jsdelivr.net https://*.sentry.io https://accounts.google.com https://kapi.kakao.com https://kauth.kakao.com`
    : `'self' ${backendHost} https://cdn.jsdelivr.net https://*.sentry.io https://accounts.google.com https://kapi.kakao.com https://kauth.kakao.com`;

  // Dev keeps 'unsafe-eval' + 'unsafe-inline' for React Fast Refresh / HMR
  // (webpack injects literal `eval(…)` and inline `<script>` runtime patches
  // that don't carry a nonce). Prod drops both and switches to nonce + strict-dynamic.
  const scriptSrc = isDev
    ? "'self' 'unsafe-inline' 'unsafe-eval'"
    : `'self' 'nonce-${nonce}' 'strict-dynamic'`;

  const cspHeader = `
    default-src 'self';
    script-src ${scriptSrc};
    style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
    font-src 'self' https://cdn.jsdelivr.net;
    img-src 'self' data: blob:;
    media-src 'self';
    connect-src ${connectSrc};
    worker-src 'self';
    frame-src 'self';
    frame-ancestors 'none';
    base-uri 'self';
    form-action 'self';
    object-src 'none';
    upgrade-insecure-requests;
  `
    .replace(/\s{2,}/g, " ")
    .trim();

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("x-locale", locale);

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });

  response.headers.set("Content-Security-Policy", cspHeader);

  // Set locale cookie if it wasn't present (silently initialises first-time visitors)
  // 2026-05-12 bug-hunter P1: Secure flag was missing — locale cookie could be
  // sent over plain HTTP in MITM scenarios. lib/locale.tsx client-side setter
  // already gates Secure on NODE_ENV; this server-side setter now matches.
  if (!hasCookie) {
    response.cookies.set(LOCALE_COOKIE, locale, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    });
  }

  return response;
}

export const config = {
  matcher: [
    // P0 fix (2026-05-03): previously this matcher used `missing: [
    //   { type: "header", key: "next-router-prefetch" },
    //   { type: "header", key: "purpose", value: "prefetch" },
    // ]` to skip the middleware on RSC prefetch requests. That caused a
    // production-wide 500: when a `<Link>` triggered a prefetch (hover or
    // viewport entry), the middleware was bypassed, so `x-nonce` was never
    // injected. `app/layout.tsx` then called `headers().get("x-nonce")`
    // which threw a Next.js dynamic-API error in the prefetch render
    // context, surfacing as `__next_error__` (500), occasionally wrapped
    // by Vercel as 503. Letting prefetch requests through the middleware
    // restores the nonce and keeps the locale logic consistent
    // for prefetched payloads. layout.tsx also wraps `headers()` in
    // try/catch as defense-in-depth — see that file.
    "/((?!api|_next/static|_next/image|favicon.ico|icons|videos|sw.js|offline.html|logo|agents-preview).*)",
  ],
};
