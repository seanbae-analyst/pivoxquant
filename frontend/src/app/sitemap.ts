import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site-url";

const BASE_URL = SITE_URL;

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
    // /pricing 제거 (DECISIONS.md ✅확정 2026-05-30: 무료 Stage 0). /pricing 은
    // next.config.ts 에서 /home 으로 307 redirect 되므로 sitemap 에 노출하면
    // Googlebot 이 redirect 체인을 크롤하게 된다. Stage 1 유료화 부활 시 복원.

    // ── Public funnel pages (release-prep audit 2026-05-09: previously
    // missing — viral acquisition surfaces and unauthenticated demos) ──
    {
      url: `${BASE_URL}/contact`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
    },

    // ── Support (2026-09-10: public FAQ + 전자상거래법 §13 business info;
    // it was reachable and linked from the footer but missing here) ──
    {
      url: `${BASE_URL}/support`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
    },

    // ── Docs (Wave C-2 SEO 2026-05-17: was missing — public Q&A surface) ─
    {
      url: `${BASE_URL}/docs`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
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
