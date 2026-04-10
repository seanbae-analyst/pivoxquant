import { test, expect } from "@playwright/test";

const EMAIL = "e2e-tester@stockpilot.com";
const PASSWORD = "test123456";
const BASE = "http://localhost:5050";

/* ── Helper: register + login via API, return cookie ── */
async function setupUser(request: any) {
  // Register (ignore if already exists)
  await request.post(`${BASE}/api/auth/register`, {
    data: { email: EMAIL, password: PASSWORD, name: "E2E Tester" },
  });

  // Login
  const loginRes = await request.post(`${BASE}/api/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  expect(loginRes.ok()).toBeTruthy();

  // Set capital
  await request.put(`${BASE}/api/portfolio/capital`, {
    data: { capital_usd: 50000, capital_krw: 5000000 },
  });

  // Add positions
  const tickers = [
    { ticker: "AAPL", shares: 25, avg_cost: 178.5 },
    { ticker: "NVDA", shares: 15, avg_cost: 450 },
    { ticker: "MSFT", shares: 10, avg_cost: 380.25 },
    { ticker: "TSLA", shares: 12, avg_cost: 245 },
    { ticker: "005930.KS", shares: 50, avg_cost: 72000 },
  ];
  for (const t of tickers) {
    await request.post(`${BASE}/api/portfolio/position`, { data: t });
  }
}

/* ══════════════════════════════════════
   1. AUTH TESTS
   ══════════════════════════════════════ */

test.describe("Auth", () => {
  test("login page loads", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("text=Welcome Back")).toBeVisible();
    await expect(page.locator("input[placeholder*='example']")).toBeVisible();
    await expect(page.locator("input[placeholder*='Min 6']")).toBeVisible();
  });

  test("login with valid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.fill("input[placeholder*='example']", EMAIL);
    await page.fill("input[placeholder*='Min 6']", PASSWORD);
    await page.click("button:has-text('Sign In')");
    await page.waitForURL(/\/(home)?$/, { timeout: 10000 }).catch(() => {});
    // Should redirect to home or root
    const url = page.url();
    expect(url.endsWith("/home") || url.endsWith("/")).toBeTruthy();
  });

  test("login with wrong password shows error", async ({ page }) => {
    await page.goto("/login");
    await page.fill("input[placeholder*='example']", EMAIL);
    await page.fill("input[placeholder*='Min 6']", "wrongpassword");
    await page.click("button:has-text('Sign In')");
    await page.waitForTimeout(2000);
    // Should stay on login page
    expect(page.url()).toContain("login");
  });
});

/* ══════════════════════════════════════
   2. DASHBOARD TESTS
   ══════════════════════════════════════ */

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page, request }) => {
    await setupUser(request);
    await page.goto("/login");
    await page.fill("input[placeholder*='example']", EMAIL);
    await page.fill("input[placeholder*='Min 6']", PASSWORD);
    await page.click("button:has-text('Sign In')");
    await page.waitForTimeout(3000);
    await page.goto("/home");
    await page.waitForTimeout(3000);
  });

  test("portfolio summary cards visible", async ({ page }) => {
    await expect(page.locator("text=PORTFOLIO VALUE")).toBeVisible();
    await expect(page.locator("text=AVG P&L")).toBeVisible();
    await expect(page.locator("text=POSITIONS")).toBeVisible();
  });

  test("holdings tab shows positions", async ({ page }) => {
    await expect(page.locator("text=Holdings")).toBeVisible();
    await expect(page.locator("text=AAPL").first()).toBeVisible({ timeout: 10000 });
  });

  test("market tab loads data", async ({ page }) => {
    await page.click("button:has-text('Market')");
    await page.waitForTimeout(10000);
    await expect(page.locator("[data-testid='market-tab'], table").first()).toBeVisible({ timeout: 10000 });
  });

  test("movers tab shows gainers and losers", async ({ page }) => {
    await page.click("button:has-text('Movers')");
    await page.waitForTimeout(2000);
    await expect(page.locator("text=Top Gainers")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Top Losers")).toBeVisible({ timeout: 10000 });
  });

  test("discover tab loads", async ({ page }) => {
    await page.click("button:has-text('Discover')");
    await page.waitForTimeout(3000);
    // Should show either results or scanning message
    const hasContent = await page.locator("text=Scanning").or(page.locator("table")).count();
    expect(hasContent).toBeGreaterThan(0);
  });
});

/* ══════════════════════════════════════
   3. TRADING MODAL TESTS
   ══════════════════════════════════════ */

test.describe("Trading Modals", () => {
  test.beforeEach(async ({ page, request }) => {
    await setupUser(request);
    await page.goto("/login");
    await page.fill("input[placeholder*='example']", EMAIL);
    await page.fill("input[placeholder*='Min 6']", PASSWORD);
    await page.click("button:has-text('Sign In')");
    await page.waitForTimeout(3000);
    await page.goto("/home");
    await page.waitForTimeout(3000);
  });

  test("buy modal opens and submits", async ({ page }) => {
    // Click first Buy button in table
    const buyBtn = page.locator("table button:has-text('Buy')").first();
    await buyBtn.click();
    await page.waitForTimeout(1000);

    // Modal should be open
    await expect(page.locator("text=Current Price")).toBeVisible();

    // Fill shares
    const sharesInput = page.locator("[role=\"dialog\"] input[type='number']").first();
    await sharesInput.fill("5");

    // Total should update (not NaN)
    const totalText = await page.locator("text=Total:").textContent();
    expect(totalText).not.toContain("NaN");

    // Submit
    await page.click("[role=\"dialog\"] button:has-text('Confirm Buy')");
    await page.waitForTimeout(3000);
  });

  test("sell modal opens with max shares", async ({ page }) => {
    const sellBtn = page.locator("table button:has-text('Sell')").first();
    await sellBtn.click();
    await page.waitForTimeout(1000);

    await expect(page.locator("text=Current Price")).toBeVisible();
    await expect(page.locator("button:has-text('All')")).toBeVisible();

    // Proceeds should not be NaN
    const proceedsText = await page.locator("text=Proceeds:").textContent();
    expect(proceedsText).not.toContain("NaN");
  });

  test("sell modal rejects exceeding shares", async ({ page }) => {
    const sellBtn = page.locator("table button:has-text('Sell')").first();
    await sellBtn.click();
    await page.waitForTimeout(1000);

    const sharesInput = page.locator("[role=\"dialog\"] input[type='number']").first();
    await sharesInput.fill("99999");
    await page.click("[role=\"dialog\"] button:has-text('Confirm Sell')");
    await page.waitForTimeout(2000);

    // Should show error
    const errorVisible = await page.locator("text=Maximum").or(page.locator(".text-destructive")).count();
    expect(errorVisible).toBeGreaterThan(0);
  });

  test("edit modal opens and saves", async ({ page }) => {
    const editBtn = page.locator("table button:has-text('Edit')").first();
    await editBtn.click();
    await page.waitForTimeout(1000);

    await expect(page.locator("text=Shares")).toBeVisible();
    await expect(page.locator("text=Avg Cost")).toBeVisible();

    // Change value
    const inputs = page.locator("[role=\"dialog\"] input[type='number']");
    await inputs.nth(1).fill("200");

    await page.click("[role=\"dialog\"] button:has-text('Save Changes')");
    await page.waitForTimeout(3000);
  });

  test("buy modal rejects 0 shares", async ({ page }) => {
    const buyBtn = page.locator("table button:has-text('Buy')").first();
    await buyBtn.click();
    await page.waitForTimeout(1000);

    const sharesInput = page.locator("[role=\"dialog\"] input[type='number']").first();
    await sharesInput.fill("0");
    await page.click("[role=\"dialog\"] button:has-text('Confirm Buy')");
    await page.waitForTimeout(1000);

    // Should show validation error
    const errorVisible = await page.locator("text=greater than 0").count();
    expect(errorVisible).toBeGreaterThan(0);
  });
});

/* ══════════════════════════════════════
   4. NAVIGATION TESTS
   ══════════════════════════════════════ */

test.describe("Navigation", () => {
  test.beforeEach(async ({ page, request }) => {
    await setupUser(request);
    await page.goto("/login");
    await page.fill("input[placeholder*='example']", EMAIL);
    await page.fill("input[placeholder*='Min 6']", PASSWORD);
    await page.click("button:has-text('Sign In')");
    await page.waitForTimeout(3000);
  });

  test("market page loads", async ({ page }) => {
    await page.goto("/market");
    await page.waitForTimeout(5000);
    await expect(page.locator("text=Market").first()).toBeVisible();
  });

  test("ai chat page loads", async ({ page }) => {
    await page.goto("/ai-chat");
    await page.waitForTimeout(3000);
    await expect(page.locator("text=AI Chat")).toBeVisible();
    await expect(page.locator("text=How can I help")).toBeVisible();
  });

  test("ai chat sends message", async ({ page }) => {
    await page.goto("/ai-chat");
    await page.waitForTimeout(2000);

    await page.fill("input[placeholder*='portfolio']", "What should I sell?");
    await page.locator("button[type='submit']").click();
    await page.waitForTimeout(10000);

    // Should have user message visible
    await expect(page.locator("text=What should I sell?")).toBeVisible();
  });

  test("ai review page loads", async ({ page }) => {
    await page.goto("/ai-review");
    await page.waitForTimeout(3000);
    await expect(page.locator("text=AI Portfolio Review")).toBeVisible();
    await expect(page.locator("text=Generate Monthly Review")).toBeVisible();
  });

  test("alerts page loads", async ({ page }) => {
    await page.goto("/alerts");
    await page.waitForTimeout(3000);
    const title = page.locator("h1, h2").first();
    await expect(title).toBeVisible();
  });

  test("trades page loads", async ({ page }) => {
    await page.goto("/trades");
    await page.waitForTimeout(3000);
    const title = page.locator("h1, h2").first();
    await expect(title).toBeVisible();
  });

  test("watchlist page loads", async ({ page }) => {
    await page.goto("/watchlist");
    await page.waitForTimeout(3000);
    const title = page.locator("h1, h2").first();
    await expect(title).toBeVisible();
  });
});

/* ══════════════════════════════════════
   5. API HEALTH TESTS
   ══════════════════════════════════════ */

test.describe("API Health", () => {
  test.beforeEach(async ({ request }) => {
    await setupUser(request);
  });

  test("GET /api/auth/me returns user", async ({ request }) => {
    const res = await request.get(`${BASE}/api/auth/me`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.authenticated).toBeTruthy();
  });

  test("GET /api/portfolio returns positions", async ({ request }) => {
    const res = await request.get(`${BASE}/api/portfolio`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.positions.length).toBeGreaterThan(0);
  });

  test("GET /api/market/overview returns macro data", async ({ request }) => {
    const res = await request.get(`${BASE}/api/market/overview`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.macro).toBeDefined();
  });

  test("GET /api/signals returns signals", async ({ request }) => {
    const res = await request.get(`${BASE}/api/signals`);
    expect(res.ok()).toBeTruthy();
  });

  test("GET /api/ai/status returns available", async ({ request }) => {
    const res = await request.get(`${BASE}/api/ai/status`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.available).toBeDefined();
  });

  test("GET /api/discover returns results", async ({ request }) => {
    const res = await request.get(`${BASE}/api/discover`);
    expect(res.ok()).toBeTruthy();
  });

  test("PUT /api/portfolio/capital updates capital", async ({ request }) => {
    const res = await request.put(`${BASE}/api/portfolio/capital`, {
      data: { capital_usd: 25000, capital_krw: 3000000 },
    });
    expect(res.ok()).toBeTruthy();
  });

  test("POST buy 0 shares rejected", async ({ request }) => {
    // Get first position ID
    const portfolio = await request.get(`${BASE}/api/portfolio`);
    const data = await portfolio.json();
    const posId = data.positions[0]?.id;
    if (!posId) return;

    const res = await request.post(`${BASE}/api/portfolio/position/${posId}/buy`, {
      data: { shares: 0, price: 100 },
    });
    expect(res.ok()).toBeFalsy();
  });
});
