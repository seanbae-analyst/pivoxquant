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
const BETA_SIGNING_SECRET =
  process.env.BETA_SIGNING_SECRET ?? process.env.SECRET_KEY ?? "";
// Bump this when BETA_PASSWORD / BETA_SIGNING_SECRET rotate to force all
// existing tokens to fail validation. Middleware detects version mismatch and
// clears the stale cookie so users land on the gate with a clean slate.
const BETA_TOKEN_VERSION = "v2";

// Edge-runtime compatible HMAC-SHA256 using Web Crypto.
let cachedBetaToken: string | null = null;
async function betaSignedToken(): Promise<string> {
  if (cachedBetaToken) return cachedBetaToken;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(BETA_SIGNING_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${BETA_TOKEN_VERSION}:beta-verified`),
  );
  const hex = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  cachedBetaToken = `${BETA_TOKEN_VERSION}.${hex}`;
  return cachedBetaToken;
}

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

// Social/search crawler User-Agents that should see the rendered OG metadata
// instead of the beta gate. Without this, SNS shares fall back to the gate
// HTML (no og:title / og:image) and the unfurl is empty. Match loosely — we
// want to let these bots through, the cost is tiny (HTML only, no API calls).
const CRAWLER_UA_PATTERN =
  /facebookexternalhit|facebookcatalog|Twitterbot|LinkedInBot|Slackbot|TelegramBot|WhatsApp|Discordbot|KAKAOTALK|kakaotalk-scrap|Line|NaverBot|Yeti|Googlebot|bingbot|Applebot|Pinterest|redditbot|Embedly|SkypeUriPreview/i;

function isCrawlerUserAgent(ua: string | null): boolean {
  if (!ua) return false;
  return CRAWLER_UA_PATTERN.test(ua);
}

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

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // ─── Beta gate (only when BETA_PASSWORD is configured) ──────────────────
  // No password env → skipped entirely so local dev stays unblocked.
  // Social/search crawlers bypass the gate so OG cards render on share.
  const userAgent = request.headers.get("user-agent");
  const isCrawler = isCrawlerUserAgent(userAgent);
  if (BETA_PASSWORD && !isBetaBypass(pathname) && !isCrawler) {
    const token = request.cookies.get(BETA_COOKIE_NAME)?.value;
    const expected = BETA_SIGNING_SECRET ? await betaSignedToken() : null;
    if (!expected || token !== expected) {
      const url = request.nextUrl.clone();
      url.pathname = BETA_GATE_PATH;
      url.search = "";
      // Preserve original destination (path + query) so user returns after auth.
      const redirectTarget = pathname + (request.nextUrl.search ?? "");
      url.searchParams.set("redirect", redirectTarget);
      const redirect = NextResponse.redirect(url);
      // If an invalid/stale cookie is present (e.g. signed with a previous
      // BETA_SIGNING_SECRET or BETA_PASSWORD after rotation, or a mismatched
      // token version), explicitly clear it so the user can re-authenticate
      // without manually wiping cookies. Without this, the browser keeps
      // replaying the stale cookie and the gate loops forever.
      if (token) {
        redirect.cookies.set(BETA_COOKIE_NAME, "", {
          path: "/",
          maxAge: 0,
          httpOnly: true,
          secure: process.env.NODE_ENV === "production",
          sameSite: "lax",
        });
      }
      return redirect;
    }
  }

  // ─── Locale: set cookie if missing (no URL rewriting for now) ────────────
  const locale = detectLocale(request);
  const hasCookie = !!request.cookies.get(LOCALE_COOKIE)?.value;

  // ─── CSP ─────────────────────────────────────────────────────────────────
  // TODO(security): Migrate `script-src` from 'unsafe-inline' to nonce-based.
  //   Next.js 16 still emits inline bootstrap scripts (hydration payload,
  //   `__next_f` flight chunks) without nonce attributes by default. Removing
  //   'unsafe-inline' today breaks hydration across the whole app. Track the
  //   upstream RFC before flipping this — once Next wires the nonce through
  //   automatically, replace 'unsafe-inline' with `'nonce-${nonce}'` and add
  //   'strict-dynamic' for transitively loaded chunks.
  //   `style-src` must keep 'unsafe-inline' — Tailwind 4 inlines arbitrary
  //   utility styles and shadcn/Radix primitives set inline style props.
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");

  const isDev = process.env.NODE_ENV === "development";
  const connectSrc = isDev
    ? "'self' http://localhost:5050 ws://localhost:3000 ws://localhost:* https://*.railway.app https://cdn.jsdelivr.net https://api.stripe.com https://*.sentry.io https://accounts.google.com https://kapi.kakao.com https://kauth.kakao.com"
    : "'self' https://*.railway.app https://cdn.jsdelivr.net https://api.stripe.com https://*.sentry.io https://accounts.google.com https://kapi.kakao.com https://kauth.kakao.com";

  // Dev keeps 'unsafe-eval' for React Fast Refresh. Prod drops it.
  const scriptSrc = isDev
    ? "'self' 'unsafe-inline' 'unsafe-eval'"
    : "'self' 'unsafe-inline'";

  const cspHeader = `
    default-src 'self';
    script-src ${scriptSrc};
    style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
    font-src 'self' https://cdn.jsdelivr.net;
    img-src 'self' data: blob:;
    media-src 'self';
    connect-src ${connectSrc};
    worker-src 'self';
    frame-src 'self' https://js.stripe.com https://hooks.stripe.com;
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
