import type { NextConfig } from "next";

// Backend API URL: Railway production or local development.
// NEXT_PUBLIC_API_URL is evaluated in next.config.ts at build time.
// On Vercel we pin the Railway hostname directly to avoid env var drift;
// local dev still uses the env override or falls back to localhost:5050.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.VERCEL ? "https://RAILWAY_BACKEND_HOST.up.railway.app" : "http://localhost:5050");

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
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
