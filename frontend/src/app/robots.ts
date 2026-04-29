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
