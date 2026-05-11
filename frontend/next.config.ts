import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

// Backend API URL: Railway production or local development.
// NEXT_PUBLIC_API_URL is evaluated in next.config.ts at build time.
// On Vercel set NEXT_PUBLIC_API_URL (or RAILWAY_BACKEND_URL) to the Railway hostname.
// Local dev falls back to localhost:5050.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.VERCEL ? (process.env.RAILWAY_BACKEND_URL || "") : "http://localhost:5050");

const nextConfig: NextConfig = {
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 86400, // 24 h
    remotePatterns: [
      // Alpaca logo CDN, FMP press release images, etc.
      { protocol: "https", hostname: "**.alpaca.markets" },
      { protocol: "https", hostname: "financialmodelingprep.com" },
      { protocol: "https", hostname: "**.financialmodelingprep.com" },
    ],
  },
  // Pin Turbopack workspace root to this dir so Hangul chars in parent path
  // (`취준/`) don't break char-boundary slicing in turbopack-core/ident.rs.
  // Also disambiguates against sibling /pivoxquant/frontend lockfile.
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
  async redirects() {
    // E2E P1 #3 (W6.3): `/dashboard` and `/dashboard/*` previously hit the
    // 404 page ("Nothing to observe here"). The Next.js App Router uses a
    // route group `(dashboard)/` whose URL segment is the empty string, so
    // the real paths are `/home`, `/market`, etc. — there is no literal
    // `/dashboard` route.
    //
    // External backlinks, ad campaigns, and SEO crawlers may still hit
    // `/dashboard` (or `/dashboard/home`, mirroring how most SaaS apps
    // structure their app shell). Issue a 308 permanent redirect at the
    // edge so we never serve a 404 for these paths.
    return [
      { source: "/dashboard", destination: "/home", permanent: true },
      { source: "/dashboard/:path*", destination: "/:path*", permanent: true },
    ];
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          // 2026-05-02: Vercel CDN was caching /sw.js despite no-store
          // (observed `x-vercel-cache: HIT`, `age: 264`). Browser-level
          // Cache-Control alone doesn't reach the edge layer, so version
          // bumps (sp-v5 → sp-v6) took 5-10 min to propagate to
          // PWA-installed users. The CDN-Cache-Control + the explicit
          // Vercel variant tell the edge to skip its own cache while
          // s-maxage=0 covers any other shared cache between Vercel and
          // the user.
          {
            key: "Cache-Control",
            value: "public, max-age=0, s-maxage=0, must-revalidate",
          },
          { key: "CDN-Cache-Control", value: "no-store" },
          { key: "Vercel-CDN-Cache-Control", value: "no-store" },
          {
            key: "Content-Type",
            value: "application/javascript; charset=utf-8",
          },
        ],
      },
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          {
            // 2026-05-10 (L4): added `interest-cohort=()` to opt out of
            // FLoC for any Chromium fork that still ships the cohort API.
            // Kept aligned with backend Permissions-Policy in security.py.
            key: "Permissions-Policy",
            value:
              "camera=(), microphone=(), geolocation=(), payment=(self), usb=(), magnetometer=(), gyroscope=(), accelerometer=(), interest-cohort=()",
          },
        ],
      },
    ];
  },
};

// Source-map upload is opt-in via SENTRY_AUTH_TOKEN; without it the build
// still succeeds without symbol uploads. `silent: true` suppresses the
// "no auth token" notice on local builds. Runtime DSN gating still
// happens inside each sentry.*.config.ts.
export default withSentryConfig(nextConfig, {
  silent: true,
  sourcemaps: {
    deleteSourcemapsAfterUpload: true,
  },
});
