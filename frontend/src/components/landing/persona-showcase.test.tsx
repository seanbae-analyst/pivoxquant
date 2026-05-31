import { describe, it, expect, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { PersonaShowcase } from "./persona-showcase";

// jsdom has no IntersectionObserver; motion/react's `whileInView` needs it.
beforeAll(() => {
  class IO {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  }
  // @ts-expect-error — minimal stub for jsdom
  globalThis.IntersectionObserver = IO;
});

/**
 * Regression guard (2026-05-31): the public marketing surface must NOT expose
 * the "speculator" / "daytrader" investor personas. They were removed from the
 * landing showcase per DECISIONS (✅ "speculator/daytrader 라벨화 금지") and the
 * 표시광고법 §3 HIGH-risk finding. The internal 9-dim / 8-centroid engine still
 * classifies them — this test only pins the *rendered* public copy so the
 * labels can't silently reappear in the showcase.
 */
describe("PersonaShowcase — no speculator/daytrader exposure", () => {
  it("renders without any speculator/daytrader label (EN or KR)", () => {
    const { container } = render(<PersonaShowcase />);
    const text = container.textContent ?? "";

    expect(text).not.toMatch(/speculator/i);
    expect(text).not.toMatch(/daytrader/i);
    expect(text).not.toContain("투기형");
    expect(text).not.toContain("단타형");
  });

  it("does not hardcode an 'eight personas' count in the header", () => {
    render(<PersonaShowcase />);
    // The header was "Eight Investor Personas"; after removing two personas it
    // must be neutralized so the public count stays honest.
    expect(screen.queryByText(/eight investor personas/i)).toBeNull();
    expect(screen.queryByText(/8가지/)).toBeNull();
  });
});
