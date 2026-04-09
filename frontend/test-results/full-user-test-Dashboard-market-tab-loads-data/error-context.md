# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: full-user-test.spec.ts >> Dashboard >> market tab loads data
- Location: e2e/full-user-test.spec.ts:99:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: [data-testid='market-tab'], table, text=Market >> nth=0
Expected: visible
Error: Unexpected token "=" while parsing css selector "[data-testid='market-tab'], table, text=Market". Did you mean to CSS.escape it?

Call log:
  - Expect "toBeVisible" with timeout 10000ms
  - waiting for [data-testid='market-tab'], table, text=Market >> nth=0

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [active]:
    - generic [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e6]:
          - navigation [ref=e7]:
            - button "previous" [disabled] [ref=e8]:
              - img "previous" [ref=e9]
            - generic [ref=e11]:
              - generic [ref=e12]: 1/
              - text: "1"
            - button "next" [disabled] [ref=e13]:
              - img "next" [ref=e14]
          - img
        - generic [ref=e16]:
          - link "Next.js 16.2.2 (stale) Turbopack" [ref=e17] [cursor=pointer]:
            - /url: https://nextjs.org/docs/messages/version-staleness
            - img [ref=e18]
            - generic "There is a newer version (16.2.3) available, upgrade recommended!" [ref=e20]: Next.js 16.2.2 (stale)
            - generic [ref=e21]: Turbopack
          - img
      - dialog "Runtime TypeError" [ref=e23]:
        - generic [ref=e26]:
          - generic [ref=e27]:
            - generic [ref=e28]:
              - generic [ref=e30]: Runtime TypeError
              - generic [ref=e31]:
                - button "Copy Error Info" [ref=e32] [cursor=pointer]:
                  - img [ref=e33]
                - button "No related documentation found" [disabled] [ref=e35]:
                  - img [ref=e36]
                - button "Attach Node.js inspector" [ref=e38] [cursor=pointer]:
                  - img [ref=e39]
            - generic [ref=e48]: Cannot read properties of undefined (reading 'price')
          - generic [ref=e50]:
            - paragraph [ref=e52]:
              - text: Call Stack
              - generic [ref=e53]: "20"
            - generic [ref=e54]:
              - generic [ref=e55]:
                - text: <unknown>
                - button "Sourcemapping failed. Click to log cause of error." [ref=e56] [cursor=pointer]:
                  - img [ref=e57]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/src_0z17s2p._.js (3139:48)
            - generic [ref=e59]:
              - generic [ref=e60]: Array.map
              - text: <anonymous>
            - generic [ref=e61]:
              - generic [ref=e62]:
                - text: MarketTab
                - button "Sourcemapping failed. Click to log cause of error." [ref=e63] [cursor=pointer]:
                  - img [ref=e64]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/src_0z17s2p._.js (3126:21)
            - generic [ref=e66]:
              - generic [ref=e67]:
                - text: Object.react_stack_bottom_frame
                - button "Sourcemapping failed. Click to log cause of error." [ref=e68] [cursor=pointer]:
                  - img [ref=e69]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (15037:24)
            - generic [ref=e71]:
              - generic [ref=e72]:
                - text: renderWithHooks
                - button "Sourcemapping failed. Click to log cause of error." [ref=e73] [cursor=pointer]:
                  - img [ref=e74]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (4620:24)
            - generic [ref=e76]:
              - generic [ref=e77]:
                - text: updateFunctionComponent
                - button "Sourcemapping failed. Click to log cause of error." [ref=e78] [cursor=pointer]:
                  - img [ref=e79]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (6081:21)
            - generic [ref=e81]:
              - generic [ref=e82]:
                - text: beginWork
                - button "Sourcemapping failed. Click to log cause of error." [ref=e83] [cursor=pointer]:
                  - img [ref=e84]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (6691:24)
            - generic [ref=e86]:
              - generic [ref=e87]:
                - text: runWithFiberInDEV
                - button "Sourcemapping failed. Click to log cause of error." [ref=e88] [cursor=pointer]:
                  - img [ref=e89]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (965:74)
            - generic [ref=e91]:
              - generic [ref=e92]:
                - text: performUnitOfWork
                - button "Sourcemapping failed. Click to log cause of error." [ref=e93] [cursor=pointer]:
                  - img [ref=e94]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (9555:97)
            - generic [ref=e96]:
              - generic [ref=e97]:
                - text: workLoopSync
                - button "Sourcemapping failed. Click to log cause of error." [ref=e98] [cursor=pointer]:
                  - img [ref=e99]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (9449:40)
            - generic [ref=e101]:
              - generic [ref=e102]:
                - text: renderRootSync
                - button "Sourcemapping failed. Click to log cause of error." [ref=e103] [cursor=pointer]:
                  - img [ref=e104]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (9433:13)
            - generic [ref=e106]:
              - generic [ref=e107]:
                - text: performWorkOnRoot
                - button "Sourcemapping failed. Click to log cause of error." [ref=e108] [cursor=pointer]:
                  - img [ref=e109]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (9098:47)
            - generic [ref=e111]:
              - generic [ref=e112]:
                - text: performSyncWorkOnRoot
                - button "Sourcemapping failed. Click to log cause of error." [ref=e113] [cursor=pointer]:
                  - img [ref=e114]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (10263:9)
            - generic [ref=e116]:
              - generic [ref=e117]:
                - text: flushSyncWorkAcrossRoots_impl
                - button "Sourcemapping failed. Click to log cause of error." [ref=e118] [cursor=pointer]:
                  - img [ref=e119]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (10179:316)
            - generic [ref=e121]:
              - generic [ref=e122]:
                - text: processRootScheduleInMicrotask
                - button "Sourcemapping failed. Click to log cause of error." [ref=e123] [cursor=pointer]:
                  - img [ref=e124]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (10200:106)
            - generic [ref=e126]:
              - generic [ref=e127]:
                - text: <unknown>
                - button "Sourcemapping failed. Click to log cause of error." [ref=e128] [cursor=pointer]:
                  - img [ref=e129]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_compiled_react-dom_058-ah~._.js (10274:158)
            - generic [ref=e131]:
              - generic [ref=e132]:
                - text: TerminalTabs
                - button "Sourcemapping failed. Click to log cause of error." [ref=e133] [cursor=pointer]:
                  - img [ref=e134]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/src_0z17s2p._.js (2724:249)
            - generic [ref=e136]:
              - generic [ref=e137]:
                - text: Terminal
                - button "Sourcemapping failed. Click to log cause of error." [ref=e138] [cursor=pointer]:
                  - img [ref=e139]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/src_0z17s2p._.js (4167:245)
            - generic [ref=e141]:
              - generic [ref=e142]:
                - text: MainPage
                - button "Sourcemapping failed. Click to log cause of error." [ref=e143] [cursor=pointer]:
                  - img [ref=e144]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/src_0z17s2p._.js (6081:218)
            - generic [ref=e146]:
              - generic [ref=e147]:
                - text: ClientPageRoot
                - button "Sourcemapping failed. Click to log cause of error." [ref=e148] [cursor=pointer]:
                  - img [ref=e149]
              - text: file:///Users/seanbae/Desktop/%E1%84%8E%E1%85%B1%E1%84%8C%E1%85%AE%E1%86%AB/stockpilot/frontend/.next/dev/static/chunks/node_modules_next_dist_0z8ikg~._.js (4688:50)
        - generic [ref=e151]: "1"
        - generic [ref=e152]: "2"
    - generic [ref=e157] [cursor=pointer]:
      - button "Open Next.js Dev Tools" [ref=e158]:
        - img [ref=e159]
      - generic [ref=e162]:
        - button "Open issues overlay" [ref=e163]:
          - generic [ref=e164]:
            - generic [ref=e165]: "0"
            - generic [ref=e166]: "1"
          - generic [ref=e167]: Issue
        - button "Collapse issues badge" [ref=e168]:
          - img [ref=e169]
  - generic [ref=e172]:
    - img [ref=e173]
    - heading "This page couldn’t load" [level=1] [ref=e175]
    - paragraph [ref=e176]: Reload to try again, or go back.
    - generic [ref=e177]:
      - button "Reload" [ref=e179] [cursor=pointer]
      - button "Back" [ref=e180] [cursor=pointer]
```

# Test source

```ts
  2   | 
  3   | const EMAIL = "e2e-tester@stockpilot.com";
  4   | const PASSWORD = "test123456";
  5   | const BASE = "http://localhost:5050";
  6   | 
  7   | /* ── Helper: register + login via API, return cookie ── */
  8   | async function setupUser(request: any) {
  9   |   // Register (ignore if already exists)
  10  |   await request.post(`${BASE}/api/auth/register`, {
  11  |     data: { email: EMAIL, password: PASSWORD, name: "E2E Tester" },
  12  |   });
  13  | 
  14  |   // Login
  15  |   const loginRes = await request.post(`${BASE}/api/auth/login`, {
  16  |     data: { email: EMAIL, password: PASSWORD },
  17  |   });
  18  |   expect(loginRes.ok()).toBeTruthy();
  19  | 
  20  |   // Set capital
  21  |   await request.put(`${BASE}/api/portfolio/capital`, {
  22  |     data: { capital_usd: 50000, capital_krw: 5000000 },
  23  |   });
  24  | 
  25  |   // Add positions
  26  |   const tickers = [
  27  |     { ticker: "AAPL", shares: 25, avg_cost: 178.5 },
  28  |     { ticker: "NVDA", shares: 15, avg_cost: 450 },
  29  |     { ticker: "MSFT", shares: 10, avg_cost: 380.25 },
  30  |     { ticker: "TSLA", shares: 12, avg_cost: 245 },
  31  |     { ticker: "005930.KS", shares: 50, avg_cost: 72000 },
  32  |   ];
  33  |   for (const t of tickers) {
  34  |     await request.post(`${BASE}/api/portfolio/position`, { data: t });
  35  |   }
  36  | }
  37  | 
  38  | /* ══════════════════════════════════════
  39  |    1. AUTH TESTS
  40  |    ══════════════════════════════════════ */
  41  | 
  42  | test.describe("Auth", () => {
  43  |   test("login page loads", async ({ page }) => {
  44  |     await page.goto("/login");
  45  |     await expect(page.locator("text=Welcome Back")).toBeVisible();
  46  |     await expect(page.locator("input[placeholder*='example']")).toBeVisible();
  47  |     await expect(page.locator("input[placeholder*='Min 6']")).toBeVisible();
  48  |   });
  49  | 
  50  |   test("login with valid credentials", async ({ page }) => {
  51  |     await page.goto("/login");
  52  |     await page.fill("input[placeholder*='example']", EMAIL);
  53  |     await page.fill("input[placeholder*='Min 6']", PASSWORD);
  54  |     await page.click("button:has-text('Sign In')");
  55  |     await page.waitForURL(/\/(home)?$/, { timeout: 10000 }).catch(() => {});
  56  |     // Should redirect to home or root
  57  |     const url = page.url();
  58  |     expect(url.endsWith("/home") || url.endsWith("/")).toBeTruthy();
  59  |   });
  60  | 
  61  |   test("login with wrong password shows error", async ({ page }) => {
  62  |     await page.goto("/login");
  63  |     await page.fill("input[placeholder*='example']", EMAIL);
  64  |     await page.fill("input[placeholder*='Min 6']", "wrongpassword");
  65  |     await page.click("button:has-text('Sign In')");
  66  |     await page.waitForTimeout(2000);
  67  |     // Should stay on login page
  68  |     expect(page.url()).toContain("login");
  69  |   });
  70  | });
  71  | 
  72  | /* ══════════════════════════════════════
  73  |    2. DASHBOARD TESTS
  74  |    ══════════════════════════════════════ */
  75  | 
  76  | test.describe("Dashboard", () => {
  77  |   test.beforeEach(async ({ page, request }) => {
  78  |     await setupUser(request);
  79  |     await page.goto("/login");
  80  |     await page.fill("input[placeholder*='example']", EMAIL);
  81  |     await page.fill("input[placeholder*='Min 6']", PASSWORD);
  82  |     await page.click("button:has-text('Sign In')");
  83  |     await page.waitForTimeout(3000);
  84  |     await page.goto("/home");
  85  |     await page.waitForTimeout(3000);
  86  |   });
  87  | 
  88  |   test("portfolio summary cards visible", async ({ page }) => {
  89  |     await expect(page.locator("text=PORTFOLIO VALUE")).toBeVisible();
  90  |     await expect(page.locator("text=AVG P&L")).toBeVisible();
  91  |     await expect(page.locator("text=POSITIONS")).toBeVisible();
  92  |   });
  93  | 
  94  |   test("holdings tab shows positions", async ({ page }) => {
  95  |     await expect(page.locator("text=Holdings")).toBeVisible();
  96  |     await expect(page.locator("text=AAPL").first()).toBeVisible({ timeout: 10000 });
  97  |   });
  98  | 
  99  |   test("market tab loads data", async ({ page }) => {
  100 |     await page.click("button:has-text('Market')");
  101 |     await page.waitForTimeout(10000);
> 102 |     await expect(page.locator("[data-testid='market-tab'], table, text=Market").first()).toBeVisible({ timeout: 10000 });
      |                                                                                          ^ Error: expect(locator).toBeVisible() failed
  103 |   });
  104 | 
  105 |   test("movers tab shows gainers and losers", async ({ page }) => {
  106 |     await page.click("button:has-text('Movers')");
  107 |     await page.waitForTimeout(2000);
  108 |     await expect(page.locator("text=Top Gainers")).toBeVisible({ timeout: 10000 });
  109 |     await expect(page.locator("text=Top Losers")).toBeVisible({ timeout: 10000 });
  110 |   });
  111 | 
  112 |   test("discover tab loads", async ({ page }) => {
  113 |     await page.click("button:has-text('Discover')");
  114 |     await page.waitForTimeout(3000);
  115 |     // Should show either results or scanning message
  116 |     const hasContent = await page.locator("text=Scanning").or(page.locator("table")).count();
  117 |     expect(hasContent).toBeGreaterThan(0);
  118 |   });
  119 | });
  120 | 
  121 | /* ══════════════════════════════════════
  122 |    3. TRADING MODAL TESTS
  123 |    ══════════════════════════════════════ */
  124 | 
  125 | test.describe("Trading Modals", () => {
  126 |   test.beforeEach(async ({ page, request }) => {
  127 |     await setupUser(request);
  128 |     await page.goto("/login");
  129 |     await page.fill("input[placeholder*='example']", EMAIL);
  130 |     await page.fill("input[placeholder*='Min 6']", PASSWORD);
  131 |     await page.click("button:has-text('Sign In')");
  132 |     await page.waitForTimeout(3000);
  133 |     await page.goto("/home");
  134 |     await page.waitForTimeout(3000);
  135 |   });
  136 | 
  137 |   test("buy modal opens and submits", async ({ page }) => {
  138 |     // Click first Buy button in table
  139 |     const buyBtn = page.locator("table button:has-text('Buy')").first();
  140 |     await buyBtn.click();
  141 |     await page.waitForTimeout(1000);
  142 | 
  143 |     // Modal should be open
  144 |     await expect(page.locator("text=Current Price")).toBeVisible();
  145 | 
  146 |     // Fill shares
  147 |     const sharesInput = page.locator("[role=\"dialog\"] input[type='number']").first();
  148 |     await sharesInput.fill("5");
  149 | 
  150 |     // Total should update (not NaN)
  151 |     const totalText = await page.locator("text=Total:").textContent();
  152 |     expect(totalText).not.toContain("NaN");
  153 | 
  154 |     // Submit
  155 |     await page.click("[role=\"dialog\"] button:has-text('Confirm Buy')");
  156 |     await page.waitForTimeout(3000);
  157 |   });
  158 | 
  159 |   test("sell modal opens with max shares", async ({ page }) => {
  160 |     const sellBtn = page.locator("table button:has-text('Sell')").first();
  161 |     await sellBtn.click();
  162 |     await page.waitForTimeout(1000);
  163 | 
  164 |     await expect(page.locator("text=Current Price")).toBeVisible();
  165 |     await expect(page.locator("button:has-text('All')")).toBeVisible();
  166 | 
  167 |     // Proceeds should not be NaN
  168 |     const proceedsText = await page.locator("text=Proceeds:").textContent();
  169 |     expect(proceedsText).not.toContain("NaN");
  170 |   });
  171 | 
  172 |   test("sell modal rejects exceeding shares", async ({ page }) => {
  173 |     const sellBtn = page.locator("table button:has-text('Sell')").first();
  174 |     await sellBtn.click();
  175 |     await page.waitForTimeout(1000);
  176 | 
  177 |     const sharesInput = page.locator("[role=\"dialog\"] input[type='number']").first();
  178 |     await sharesInput.fill("99999");
  179 |     await page.click("[role=\"dialog\"] button:has-text('Confirm Sell')");
  180 |     await page.waitForTimeout(2000);
  181 | 
  182 |     // Should show error
  183 |     const errorVisible = await page.locator("text=Maximum").or(page.locator(".text-destructive")).count();
  184 |     expect(errorVisible).toBeGreaterThan(0);
  185 |   });
  186 | 
  187 |   test("edit modal opens and saves", async ({ page }) => {
  188 |     const editBtn = page.locator("table button:has-text('Edit')").first();
  189 |     await editBtn.click();
  190 |     await page.waitForTimeout(1000);
  191 | 
  192 |     await expect(page.locator("text=Shares")).toBeVisible();
  193 |     await expect(page.locator("text=Avg Cost")).toBeVisible();
  194 | 
  195 |     // Change value
  196 |     const inputs = page.locator("[role=\"dialog\"] input[type='number']");
  197 |     await inputs.nth(1).fill("200");
  198 | 
  199 |     await page.click("[role=\"dialog\"] button:has-text('Save Changes')");
  200 |     await page.waitForTimeout(3000);
  201 |   });
  202 | 
```