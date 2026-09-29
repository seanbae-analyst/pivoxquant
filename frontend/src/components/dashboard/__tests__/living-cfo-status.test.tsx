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

const state = vi.hoisted(() => ({
  profile: null as null | { profile_type: string },
  declared: undefined as undefined | { persona: string; label: string },
}));
vi.mock("@/lib/hooks", () => ({
  useInvestmentProfile: () => ({ data: { profile: state.profile } }),
}));
vi.mock("@/lib/cfo/hooks", async (orig) => ({
  ...(await orig<typeof import("@/lib/cfo/hooks")>()),
  usePersona: () => ({ data: { declared: state.declared, observed: { window_30d: {} } } }),
  usePulse: () => ({ data: { history: [] } }),
}));

import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { LocaleProvider } from "@/lib/locale";
import ko from "@/messages/ko.json";
import en from "@/messages/en.json";

describe("LivingCFOStatusBar", () => {
  it("links to /mirror and /onboarding without an 'assessment' label", () => {
    render(<LivingCFOStatusBar />);
    fireEvent.click(screen.getByRole("button", { name: /CFO status/ }));
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/mirror");
    expect(hrefs).toContain("/onboarding");
    expect(screen.queryByText(/assessment/i)).toBeNull();
  });

  it("reports only the measured pulse count — no '30-day drift tracked'", () => {
    // usePersona above always carries observed.window_30d (the backend sends
    // it even for an empty window), which used to be enough to claim
    // "30-day drift tracked". The Learning row now states only what is
    // counted.
    render(
      <LocaleProvider>
        <LivingCFOStatusBar />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /CFO status/ }));
    expect(screen.queryByText(/drift tracked/i)).toBeNull();
    expect(screen.queryByText(/drift data/i)).toBeNull();
    expect(screen.getByText("주간 펄스 0회 기록됨.")).toBeTruthy();
  });

  it("ko/en both carry dashboard.cfoStatus.pulsesRecorded", () => {
    expect(ko.dashboard.cfoStatus.pulsesRecorded).toContain("{n}");
    expect(en.dashboard.cfoStatus.pulsesRecorded).toContain("{n}");
  });

  it("names no persona type for a user who answered onboarding (2026-09-29)", () => {
    state.profile = { profile_type: "growth" };
    state.declared = { persona: "growth", label: "성장형" };
    try {
      const { container } = render(<LivingCFOStatusBar />);
      fireEvent.click(screen.getByRole("button", { name: /CFO status/ }));
      const text = container.ownerDocument.body.textContent ?? "";
      for (const name of ["성장형", "균형형", "수익형", "Declared persona"]) {
        expect(text).not.toContain(name);
      }
      expect(text).toContain("Five onboarding answers recorded.");
    } finally {
      state.profile = null;
      state.declared = undefined;
    }
  });

  it("is not mounted on /mirror", () => {
    const src = readFileSync(
      join(__dirname, "..", "..", "..", "app", "(dashboard)", "mirror", "page.tsx"),
      "utf8",
    );
    expect(src).not.toContain("LivingCFOStatusBar");
  });
});
