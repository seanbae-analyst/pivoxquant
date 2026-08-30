import { describe, expect, it } from "vitest";

import { derivePosture } from "@/app/(dashboard)/risk/page";

/**
 * Regression guard (AUTOPILOT_BACKLOG 2026-07-12 P1):
 * a portfolio with zero positions produced `layers.length === 0`, which mapped
 * to "composed" — the same posture a genuinely steady book gets. The Risk Board
 * hero then stated "All layers within band, none breached" about layers that
 * were never observed.
 */
describe("derivePosture", () => {
  it("reports an unobserved book as insufficient, not composed", () => {
    expect(derivePosture(0, 0, 0)).toBe("insufficient");
  });

  it("still reports a genuinely calm book as composed", () => {
    expect(derivePosture(7, 0, 0)).toBe("composed");
  });

  it("does not confuse the two", () => {
    expect(derivePosture(0, 0, 0)).not.toBe(derivePosture(7, 0, 0));
  });

  it("ranks breach above strain", () => {
    expect(derivePosture(7, 1, 5)).toBe("breached");
  });

  it("escalates to strained at three strained layers", () => {
    expect(derivePosture(7, 0, 3)).toBe("strained");
    expect(derivePosture(7, 0, 2)).toBe("attentive");
    expect(derivePosture(7, 0, 1)).toBe("attentive");
  });
});
