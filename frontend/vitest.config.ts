import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "e2e", ".next"],
    css: false,
    // 2026-05-17: vitest 4.x + React 19 + @testing-library/user-event runs
    // noticeably slower in jsdom than vitest 1.x. PR #414 bumped to 15s
    // which cleared 3 signup tests when run alone, but the full 24-file
    // suite still flakes on signup-v2 + marketing-consent-card due to
    // worker contention (environment setup takes 16s in cold workers).
    // 30s gives enough headroom that the entire suite stays green in CI
    // while still failing fast on truly hung tests. Fast tests are
    // unaffected — most still complete in <50ms.
    testTimeout: 30000,
    hookTimeout: 30000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
