/**
 * <LivingCFOStatusBar /> — must not restate /mirror (2026-09-29).
 * The modal points to /mirror for declared-vs-observed, the onboarding CTA
 * names what /onboarding actually is (five questions), and /mirror itself no
 * longer mounts the bar.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

vi.mock("@/lib/hooks", () => ({
  useInvestmentProfile: () => ({ data: { profile: null } }),
}));
vi.mock("@/lib/cfo/hooks", async (orig) => ({
  ...(await orig<typeof import("@/lib/cfo/hooks")>()),
  usePersona: () => ({ data: { observed: { window_30d: {} } } }),
  usePulse: () => ({ data: { history: [] } }),
}));

import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";

describe("LivingCFOStatusBar", () => {
  it("links to /mirror and /onboarding without an 'assessment' label", () => {
    render(<LivingCFOStatusBar />);
    fireEvent.click(screen.getByRole("button", { name: /CFO status/ }));
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/mirror");
    expect(hrefs).toContain("/onboarding");
    expect(screen.queryByText(/assessment/i)).toBeNull();
  });

  it("is not mounted on /mirror", () => {
    const src = readFileSync(
      join(__dirname, "..", "..", "..", "app", "(dashboard)", "mirror", "page.tsx"),
      "utf8",
    );
    expect(src).not.toContain("LivingCFOStatusBar");
  });
});
