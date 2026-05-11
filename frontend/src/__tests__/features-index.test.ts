/**
 * Regression guard — /features index route (W7.4 / E2E P2 #4).
 *
 * Before this fix /features was a 404 dead route. The 13 subpaths
 * (/features/engine, /features/personas, …) existed but the index
 * did not, breaking nav fallbacks, SEO crawl discovery, and any
 * external backlink to /features.
 *
 * This test asserts:
 *   1. `frontend/src/app/features/page.tsx` exists on disk (Next.js
 *      App Router contract — only a `page.tsx` registers the route).
 *   2. The page source links to every existing /features/<dir>
 *      subpath. New feature subpaths added without a link from the
 *      index are caught here.
 *   3. `frontend/src/app/sitemap.ts` includes the /features URL so
 *      crawlers and external indexers see the page.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";

const FRONTEND_SRC = join(__dirname, "..");
const FEATURES_DIR = join(FRONTEND_SRC, "app", "features");
const INDEX_PAGE = join(FEATURES_DIR, "page.tsx");
const SITEMAP_PATH = join(FRONTEND_SRC, "app", "sitemap.ts");

function listFeatureSubpaths(): string[] {
  return readdirSync(FEATURES_DIR)
    .filter((name) => {
      const full = join(FEATURES_DIR, name);
      try {
        return (
          statSync(full).isDirectory() &&
          existsSync(join(full, "page.tsx"))
        );
      } catch {
        return false;
      }
    })
    .sort();
}

describe("/features index route (W7.4 / E2E P2 #4)", () => {
  it("page.tsx exists at app/features/", () => {
    expect(
      existsSync(INDEX_PAGE),
      "frontend/src/app/features/page.tsx missing — /features will 404",
    ).toBe(true);
  });

  it("links to every /features/<subpath> with a page.tsx", () => {
    const source = readFileSync(INDEX_PAGE, "utf-8");
    const subpaths = listFeatureSubpaths();

    // Sanity: we should have discovered the existing 13 surfaces.
    expect(subpaths.length).toBeGreaterThanOrEqual(10);

    const missing: string[] = [];
    for (const sub of subpaths) {
      const href = `/features/${sub}`;
      if (!source.includes(href)) missing.push(href);
    }

    if (missing.length > 0) {
      throw new Error(
        `/features index missing links for ${missing.length} subpath(s):\n` +
          missing.map((h) => `  • ${h}`).join("\n") +
          `\nAdd them to FEATURE_CARDS in app/features/page.tsx.`,
      );
    }
    expect(missing).toEqual([]);
  });

  it("sitemap.ts includes the /features URL", () => {
    const sitemap = readFileSync(SITEMAP_PATH, "utf-8");
    expect(
      sitemap.includes("/features`") ||
        sitemap.includes('"/features"') ||
        sitemap.includes("${BASE_URL}/features`"),
      "sitemap.ts missing /features entry — SEO crawl discovery breaks",
    ).toBe(true);
  });
});
