import { describe, it, expect } from "vitest";
import { colorForLabel } from "@/components/home/v2/signals-card";

// Regression for the 2026-05-24 reversal bug: signal *evaluation* labels must
// use the dedicated evaluation tokens (--pq-positive bronze / --pq-negative
// carmine), NOT the price-direction tokens (PRICE_COLOR_HEX.up/down). The
// sibling components/signals/v2/signal-card.tsx is the correct reference.

describe("colorForLabel — evaluation tokens, not price-direction (v3)", () => {
  it("POSITIVE → --pq-positive (bronze), never a price-direction hex", () => {
    expect(colorForLabel("POSITIVE")).toBe("var(--pq-positive, #b8956a)");
  });

  it("NEGATIVE → --pq-negative (carmine), never a price-direction hex", () => {
    expect(colorForLabel("NEGATIVE")).toBe("var(--pq-negative, #d18888)");
  });

  it("NEUTRAL/unknown → muted ivory (unchanged)", () => {
    expect(colorForLabel("NEUTRAL")).toBe("rgba(245,240,232,0.55)");
    expect(colorForLabel("WHATEVER")).toBe("rgba(245,240,232,0.55)");
  });
});
