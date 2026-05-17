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
    // noticeably slower in jsdom than vitest 1.x — the 3 signup tests that
    // chain 3+ `user.click()` awaits time out at the 5000ms default. Bumping
    // the global ceiling clears those without slowing fast tests (most still
    // complete in <50ms). If a real assertion ever hangs it still fails —
    // just after 15s instead of 5s.
    testTimeout: 15000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
