import type { MetadataRoute } from "next";

const BASE_URL = "https://pivoxquant.com";

// Wave C-2 SEO (2026-05-17): `new Date()` per request signalled "every URL
// updated right now" on every crawl — false freshness that trains Googlebot
// to ignore lastmod. Captured once at module-load (build time on Vercel) so
// the timestamp reflects the deploy, not the request. Pair with `force-static`
// below so the sitemap is generated at build, not regenerated on hit.
const LAST_MODIFIED = new Date();

// Force-static so the sitemap is materialised at build and served from the
// edge cache. Without this Next.js can opt the route into dynamic rendering
// (defeating the static lastmod fix above).
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = LAST_MODIFIED;

  return [
    // ── Marketing / public ─────────────────────────────────
    {
      url: `${BASE_URL}/`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${BASE_URL}/pricing`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.9,
    },

    // ── Public funnel pages (release-prep audit 2026-05-09: previously
    // missing — viral acquisition surfaces and unauthenticated demos) ──
    {
      url: `${BASE_URL}/contact`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
    },
    {
      url: `${BASE_URL}/simulator/what-if`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.6,
    },
    {
      url: `${BASE_URL}/sample-reports`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.6,
    },

    // ── Docs (Wave C-2 SEO 2026-05-17: was missing — public Q&A surface) ─
    {
      url: `${BASE_URL}/docs`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
    },

    // ── Feature pages (all 13 directories under /features/ + index) ───
    // W7.4 (2026-05-10): /features index added — was 404 dead route.
    {
      url: `${BASE_URL}/features`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/features/paper-trading`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/ai-assistant`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/canslim`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/profiles`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/quant-scoring`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/risk-defense`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/dashboard`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/engine`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/explorer`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/global-desk`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/personas`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/features/pre-trade`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },

    // ── Auth (entry points but lower crawl priority) ───────
    {
      url: `${BASE_URL}/login`,
      lastModified: now,
      changeFrequency: "yearly",
      priority: 0.4,
    },
    {
      url: `${BASE_URL}/signup`,
      lastModified: now,
      changeFrequency: "yearly",
      priority: 0.4,
    },

    // ── Legal ──────────────────────────────────────────────
    {
      url: `${BASE_URL}/terms`,
      lastModified: now,
      changeFrequency: "yearly",
      priority: 0.3,
    },
    {
      url: `${BASE_URL}/privacy`,
      lastModified: now,
      changeFrequency: "yearly",
      priority: 0.3,
    },
  ];
}
