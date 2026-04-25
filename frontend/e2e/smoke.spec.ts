import { test, expect } from "@playwright/test";

test("landing renders", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/PivoxQuant|Pivox/i);
});

test("login route reachable", async ({ page }) => {
  const resp = await page.goto("/login");
  expect(resp?.status()).toBeLessThan(500);
});
