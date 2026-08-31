/**
 * Regression guard — /dashboard/* → /:path* redirect (W6.3 / E2E P1 #3).
 *
 * Next.js App Router uses the route group `(dashboard)/` whose URL segment
 * is the empty string, so the real paths are `/home`, `/market`, etc. A
 * literal `/dashboard` route does not exist. SEO crawlers, external
 * backlinks, and ad campaigns may still hit `/dashboard` or
 * `/dashboard/home`, which previously rendered the 404 "Nothing to observe
 * here" page.
 *
 * `frontend/next.config.ts` now declares two 308 permanent redirects:
 *   /dashboard          → /home
 *   /dashboard/:path*   → /:path*
 *
 * This test imports the Next.js config and asserts the redirect entries
 * are wired correctly. It runs in vitest (Node) without spinning up the
 * dev server — fast feedback in CI and locally.
 */
import { describe, expect, it } from "vitest";

import nextConfig from "../../next.config";

type RedirectRule = {
  source: string;
  destination: string;
  permanent: boolean;
};

describe("/dashboard/* redirect (W6.3 / E2E P1 #3)", () => {
  it("declares an async redirects() function", () => {
    expect(typeof nextConfig.redirects).toBe("function");
  });

  it("redirects /dashboard to /mirror (308 permanent)", async () => {
    const rules = (await nextConfig.redirects!()) as RedirectRule[];
    const rule = rules.find((r) => r.source === "/dashboard");

    expect(rule, "missing rule for /dashboard").toBeDefined();
    expect(rule!.destination).toBe("/mirror");
    expect(rule!.permanent).toBe(true);
  });

  it("redirects /dashboard/:path* to /:path* (308 permanent)", async () => {
    const rules = (await nextConfig.redirects!()) as RedirectRule[];
    const rule = rules.find((r) => r.source === "/dashboard/:path*");

    expect(rule, "missing rule for /dashboard/:path*").toBeDefined();
    expect(rule!.destination).toBe("/:path*");
    expect(rule!.permanent).toBe(true);
  });

  it("rule ordering: exact /dashboard before wildcard /dashboard/:path*", async () => {
    // Next.js matches redirects top-to-bottom; the exact match must come
    // first so `/dashboard` is not mis-routed by the wildcard rule (which
    // would otherwise also match `/dashboard` and rewrite it to `/`).
    const rules = (await nextConfig.redirects!()) as RedirectRule[];
    const exactIdx = rules.findIndex((r) => r.source === "/dashboard");
    const wildcardIdx = rules.findIndex(
      (r) => r.source === "/dashboard/:path*",
    );

    expect(exactIdx).toBeGreaterThanOrEqual(0);
    expect(wildcardIdx).toBeGreaterThanOrEqual(0);
    expect(exactIdx).toBeLessThan(wildcardIdx);
  });
});
