import type { MetadataRoute } from "next";

const BASE_URL = "https://pivoxquant.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          // ── Internal API ───────────────────────────────
          "/api/",

          // ── Admin (allowlist-gated; 404 to non-admins) ─
          // Wave C-2 SEO (2026-05-17): admin pages are "use client"
          // so cannot export server-side metadata for robots.
          // Defence-in-depth: robots.ts disallow + allowlist gate
          // in admin/layout.tsx + admin paths absent from sitemap.
          "/admin/",
          "/admin/preview/",

          // ── Authenticated dashboard pages ─────────────
          "/home/",
          "/portfolio/",
          "/settings/",
          "/risk/",
          "/discover/",
          "/watchlist/",
          "/ai/",
          "/ai-chat/",
          // REMOVED 2026-04-27 per CEO + legal: "/autotrade/" route retired.
          "/market/",
          "/signals/",
          "/alerts/",
          "/detail/",
          "/reports/",
          "/growth/",

          // ── Onboarding (post-signup, requires session) ─
          "/onboarding/",
        ],
      },
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
    host: BASE_URL,
  };
}
