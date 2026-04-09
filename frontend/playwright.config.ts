import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "python3 ../run.py",
      port: 5050,
      timeout: 15000,
      reuseExistingServer: true,
    },
    {
      command: "npx next dev",
      port: 3000,
      timeout: 30000,
      reuseExistingServer: true,
    },
  ],
});
