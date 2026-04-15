import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SUPPORTED_LOCALES = ["ko", "en"] as const;
type Locale = (typeof SUPPORTED_LOCALES)[number];
const DEFAULT_LOCALE: Locale = "ko";
const LOCALE_COOKIE = "sp_locale";

// ─── Private Beta gate ───────────────────────────────────────────────────
const BETA_PASSWORD = process.env.BETA_PASSWORD;
const BETA_COOKIE_NAME = "pivox_beta_access";
const BETA_GATE_PATH = "/beta-gate";
const BETA_AUTH_API = "/api/beta-auth";

// Paths that must remain accessible even without beta authentication.
// (Next internal assets already excluded by matcher below.)
const BETA_BYPASS_PREFIXES = [
  BETA_GATE_PATH,
  BETA_AUTH_API,
  "/manifest",
  "/sw.js",
  "/offline.html",
  "/robots.txt",
  "/sitemap.xml",
  // Public viral page — accessible without beta password (acquisition funnel)
  "/simulator",
];

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

function isBetaBypass(pathname: string): boolean {
  return BETA_BYPASS_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // ─── Beta gate (only when BETA_PASSWORD is configured) ──────────────────
  // No password env → skipped entirely so local dev stays unblocked.
  if (BETA_PASSWORD && !isBetaBypass(pathname)) {
    const token = request.cookies.get(BETA_COOKIE_NAME)?.value;
    if (token !== BETA_PASSWORD) {
      const url = request.nextUrl.clone();
      url.pathname = BETA_GATE_PATH;
      url.search = "";
      // Preserve original destination (path + query) so user returns after auth.
      const redirectTarget = pathname + (request.nextUrl.search ?? "");
      url.searchParams.set("redirect", redirectTarget);
      return NextResponse.redirect(url);
    }
  }

  // ─── Locale: set cookie if missing (no URL rewriting for now) ────────────
  const locale = detectLocale(request);
  const hasCookie = !!request.cookies.get(LOCALE_COOKIE)?.value;

  // ─── CSP ─────────────────────────────────────────────────────────────────
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");

  const isDev = process.env.NODE_ENV === "development";
  const connectSrc = isDev
    ? "'self' http://localhost:5050 ws://localhost:3000 ws://localhost:* https://*.railway.app https://cdn.jsdelivr.net"
    : "'self' https://*.railway.app https://cdn.jsdelivr.net";

  const cspHeader = `
    default-src 'self';
    script-src 'self' 'unsafe-inline' 'unsafe-eval';
    style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
    font-src 'self' https://cdn.jsdelivr.net;
    img-src 'self' data: blob:;
    media-src 'self';
    connect-src ${connectSrc};
    worker-src 'self';
    frame-ancestors 'none';
    base-uri 'self';
    form-action 'self';
    object-src 'none';
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
  if (!hasCookie) {
    response.cookies.set(LOCALE_COOKIE, locale, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    });
  }

  return response;
}

export const config = {
  matcher: [
    {
      source:
        "/((?!api|_next/static|_next/image|favicon.ico|icons|videos|sw.js|offline.html|logo|agents-preview).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
