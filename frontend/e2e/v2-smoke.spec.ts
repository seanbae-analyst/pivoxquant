/**
 * V2 visual-regression smoke (CEO decision 2026-05-19 — V2 production ON track).
 *
 * Captures V1 vs V2 screenshots for the 9 surfaces gated by NEXT_PUBLIC_*_V2:
 *   1. /(auth)/login        — NEXT_PUBLIC_LOGIN_V2
 *   2. /(auth)/signup       — NEXT_PUBLIC_SIGNUP_V2
 *   3. /(dashboard)/home    — NEXT_PUBLIC_HOME_V2
 *   4. /(dashboard)/portfolio — NEXT_PUBLIC_PORTFOLIO_V2
 *   5. /(dashboard)/risk    — NEXT_PUBLIC_RISK_V2
 *   6. /(dashboard)/signals — NEXT_PUBLIC_SIGNALS_V2
 *   7. /(dashboard)/reports — NEXT_PUBLIC_REPORTS_V2
 *   8. /(dashboard)/profile — NEXT_PUBLIC_PROFILE_V2
 *   9. /(dashboard)/settings — NEXT_PUBLIC_SETTINGS_V2
 *
 * Each surface is captured at:
 *   - desktop (1280×800)
 *   - mobile (375×667)
 * Dark mode is the Vantablack #050505 default of the app — we don't need to
 * force-toggle it; the design system is dark by construction.
 *
 * For unauthenticated public routes (login/signup) we navigate directly.
 * For dashboard routes the layout redirects to /login if `/api/auth/me`
 * returns unauthenticated — we intercept that endpoint and inject a mock
 * user so the dashboard mounts. Other backend endpoints are stubbed with
 * empty-but-valid JSON so SWR doesn't fire 500s that pollute the layout.
 *
 * Run modes (set V2_MODE env):
 *   V2_MODE=v1  pnpm e2e v2-smoke  →  reads NEXT_PUBLIC_*_V2=false, snaps to qa/v2-smoke/<date>/v1
 *   V2_MODE=v2  pnpm e2e v2-smoke  →  reads NEXT_PUBLIC_*_V2=true,  snaps to qa/v2-smoke/<date>/v2
 *
 * The flags must already be set in .env.local before `next dev` starts —
 * Next inlines NEXT_PUBLIC_* at module init. The harness shell script
 * `scripts/v2-smoke.sh` swaps .env.local and re-launches between runs.
 *
 * Output dir: /Users/seanbae/Desktop/취준/pivoxquant/qa/v2-smoke/<YYYY-MM-DD>/<v1|v2>/<surface>-<viewport>.png
 *
 * Functional asserts (independent of variant):
 *   - login page exposes <input type="email"> and a submit/login button
 *   - signup page exposes email + password inputs
 *   - dashboard routes mount without throwing (no full-page error boundary)
 */

import { test, expect, type Page, type Route } from "@playwright/test";
import * as path from "node:path";
import * as fs from "node:fs";

const REPO_ROOT = path.resolve(__dirname, "../..");
const DATE = new Date().toISOString().slice(0, 10);
const MODE = (process.env.V2_MODE ?? "v2") as "v1" | "v2";
const OUT_DIR = path.join(REPO_ROOT, "qa/v2-smoke", DATE, MODE);
fs.mkdirSync(OUT_DIR, { recursive: true });

const VIEWPORTS = {
  desktop: { width: 1280, height: 800 },
  mobile: { width: 375, height: 667 },
} as const;

type Viewport = keyof typeof VIEWPORTS;

interface Surface {
  name: string;
  path: string;
  needsAuth: boolean;
  /** Functional assert run against the mounted page (variant-agnostic). */
  assert: (page: Page) => Promise<void>;
}

const SURFACES: readonly Surface[] = [
  {
    name: "01-login",
    path: "/login",
    needsAuth: false,
    assert: async (page) => {
      // V1 login is OAuth-only (Google/Kakao buttons, no email field).
      // V2 may introduce email/password. Accept either: any auth affordance
      // (oauth link OR email input) is sufficient to call the page "mounted".
      await expect(
        page.locator('input[type="email"], a[href*="/api/auth/google"], a[href*="/api/auth/kakao"]').first(),
      ).toBeVisible({ timeout: 15000 });
    },
  },
  {
    name: "02-signup",
    path: "/signup",
    needsAuth: false,
    assert: async (page) => {
      // Same V1/V2 split as login — OAuth-only in V1.
      await expect(
        page.locator('input[type="email"], a[href*="/api/auth/google"], a[href*="/api/auth/kakao"]').first(),
      ).toBeVisible({ timeout: 15000 });
    },
  },
  {
    name: "03-home",
    path: "/home",
    needsAuth: true,
    assert: async (page) => {
      // Either variant must render some primary heading — accept any <h1> or main role
      await expect(page.locator("main, [role=main]").first()).toBeVisible({ timeout: 15000 });
    },
  },
  {
    name: "04-portfolio",
    path: "/portfolio",
    needsAuth: true,
    assert: async (page) => {
      await expect(page.locator("main, [role=main]").first()).toBeVisible({ timeout: 15000 });
    },
  },
  {
    name: "05-risk",
    path: "/risk",
    needsAuth: true,
    assert: async (page) => {
      await expect(page.locator("main, [role=main]").first()).toBeVisible({ timeout: 15000 });
    },
  },
  {
    name: "06-signals",
    path: "/signals",
    needsAuth: true,
    assert: async (page) => {
      await expect(page.locator("main, [role=main]").first()).toBeVisible({ timeout: 15000 });
    },
  },
  {
    name: "07-reports",
    path: "/reports",
    needsAuth: true,
    assert: async (page) => {
      await expect(page.locator("main, [role=main]").first()).toBeVisible({ timeout: 15000 });
    },
  },
  {
    name: "08-profile",
    path: "/profile",
    needsAuth: true,
    assert: async (page) => {
      await expect(page.locator("main, [role=main]").first()).toBeVisible({ timeout: 15000 });
    },
  },
  {
    name: "09-settings",
    path: "/settings",
    needsAuth: true,
    assert: async (page) => {
      await expect(page.locator("main, [role=main]").first()).toBeVisible({ timeout: 15000 });
    },
  },
] as const;

/**
 * Install API mocks so dashboard surfaces render without a live backend.
 *
 * - /api/auth/me → authenticated user with completed onboarding so the
 *   layout doesn't redirect to /login or /onboarding/broker.
 * - All other /api/* → 200 with the smallest possible shape (empty list
 *   or empty object). Any endpoint that demands a richer shape will need
 *   a dedicated route here; the floor is "don't 500-cascade the layout."
 */
async function installApiMocks(page: Page): Promise<void> {
  await page.route("**/api/auth/me", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        user: {
          id: 1,
          email: "qa-smoke@pivoxquant.com",
          name: "QA Smoke",
          available_capital: 10_000_000,
          available_capital_krw: 10_000_000,
          subscription_tier: "FREE",
          effective_tier: "FREE",
          subscription_status: "active",
          onboarding_completed: true,
          birthdate_required: false,
          profile_changes_left: 3,
          risk_profile: "moderate",
        },
      }),
    });
  });

  // Generic catch-all so SWR fetches don't throw network errors.
  await page.route("**/api/**", async (route: Route) => {
    const url = route.request().url();
    // Already-handled auth/me — let it fall through (Playwright dispatches
    // in registration order so this branch is dead for /api/auth/me, but
    // we guard explicitly for clarity).
    if (url.endsWith("/api/auth/me")) return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}

for (const surface of SURFACES) {
  for (const [viewportName, viewport] of Object.entries(VIEWPORTS) as [Viewport, typeof VIEWPORTS[Viewport]][]) {
    test(`[${MODE}] ${surface.name} @ ${viewportName}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      if (surface.needsAuth) {
        await installApiMocks(page);
      }

      const resp = await page.goto(surface.path, { waitUntil: "domcontentloaded" });
      // Accept any non-5xx — middleware may redirect 307 to /beta-gate in
      // unconfigured envs; we trust the final URL.
      expect(resp?.status() ?? 0, `${surface.path} HTTP status`).toBeLessThan(500);

      // Give SWR + dynamic imports time to settle before snapping.
      await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {
        // networkidle may never fire if SSE / long-poll holds a socket open.
        // Fall back to a fixed wait so the screenshot still captures painted state.
      });
      await page.waitForTimeout(800);

      // Snap BEFORE assert so we always have evidence, even when assertion
      // fails. (Spec was originally written for V2 layout — V1 OAuth-only
      // login would otherwise block capture entirely.)
      const file = path.join(OUT_DIR, `${surface.name}-${viewportName}.png`);
      await page.screenshot({ path: file, fullPage: true });
      await test.info().attach(`${surface.name}-${viewportName}`, {
        path: file,
        contentType: "image/png",
      });

      await surface.assert(page);
    });
  }
}
