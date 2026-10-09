/**
 * public/sw.js must never cache /api/* (2026-10-09). Per-user JSON in Cache
 * Storage keyed by URL only outlived the session on a shared device; the app's
 * own per-user, logout-cleared cache (lib/persisted-swr-cache.ts) replaces it.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const sw = readFileSync(join(process.cwd(), "public/sw.js"), "utf8");

describe("service worker API caching", () => {
  it("bypasses every /api/ request", () => {
    expect(sw).toMatch(/if \(url\.pathname\.startsWith\("\/api\/"\)\) return;/);
  });

  it("has no API cache bucket or API cache strategies left", () => {
    expect(sw).not.toMatch(/API_CACHE\s*=/);
    expect(sw).not.toMatch(/NETWORK_FIRST_CONFIG|STALE_WHILE_REVALIDATE_CONFIG/);
    expect(sw).not.toMatch(/function (networkFirst|staleWhileRevalidate)\(/);
  });

  it("keeps only the current static cache on activate", () => {
    expect(sw).toMatch(/\.filter\(\(k\) => k !== STATIC_CACHE\)/);
  });
});
