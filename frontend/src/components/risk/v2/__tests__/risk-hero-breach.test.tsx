import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { RiskHeroV2 } from "@/components/risk/v2/risk-hero-v2";
import { mapLayerStatus } from "@/lib/hooks";
import type { RiskLayerV2 } from "@/lib/hooks";

/**
 * Regression gate (FIX 1, 2026-05-22): the Risk Board v2 hero must surface
 * a breach when any defense layer is RED.
 *
 * Root cause it guards: the hero formerly read `breachedCount` from
 * `summary?.layers_breached ?? 0`, but the `/api/risk/summary` payload has
 * NO `layers_breached` field — so it always rendered "none breached" even
 * when a VaR/Cash layer was RED. For a finance surface that is a dangerous
 * risk-misread. The fix derives breached/strained counts directly from the
 * `/api/risk/layers` payload status (GREEN/YELLOW/RED → POSITIVE/NEUTRAL/
 * NEGATIVE).
 *
 * Two gates here:
 *   1. mapLayerStatus maps the backend status vocabulary correctly.
 *   2. RiskHeroV2 renders the right breach sentence for each posture.
 */

describe("mapLayerStatus — backend GREEN/YELLOW/RED → POSITIVE/NEUTRAL/NEGATIVE", () => {
  it("RED maps to NEGATIVE (breached)", () => {
    expect(mapLayerStatus("RED")).toBe("NEGATIVE");
    expect(mapLayerStatus("NEGATIVE")).toBe("NEGATIVE");
  });
  it("YELLOW maps to NEUTRAL (strained)", () => {
    expect(mapLayerStatus("YELLOW")).toBe("NEUTRAL");
    expect(mapLayerStatus("NEUTRAL")).toBe("NEUTRAL");
  });
  it("GREEN maps to POSITIVE (within band)", () => {
    expect(mapLayerStatus("GREEN")).toBe("POSITIVE");
    expect(mapLayerStatus("POSITIVE")).toBe("POSITIVE");
  });
});

// Mirror the count derivation that useRiskLayers performs so the test
// asserts on the exact same predicate the production hook uses.
function deriveCounts(layers: Pick<RiskLayerV2, "status">[]) {
  return {
    breachedCount: layers.filter((l) => l.status === "NEGATIVE").length,
    strainedCount: layers.filter((l) => l.status === "NEUTRAL").length,
  };
}

describe("RiskHeroV2 — breach sentence reflects layer counts", () => {
  it("renders 'N layers breached' when RED layers exist", () => {
    // Two RED (breached) + one YELLOW (strained).
    const layers = [
      { status: "NEGATIVE" as const },
      { status: "NEGATIVE" as const },
      { status: "NEUTRAL" as const },
    ];
    const { breachedCount, strainedCount } = deriveCounts(layers);
    expect(breachedCount).toBe(2);

    const { container } = render(
      <RiskHeroV2
        eyebrow="Risk"
        posture="breached"
        breachedCount={breachedCount}
        strainedCount={strainedCount}
      />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain("2 layers breached");
    expect(text).not.toContain("none breached");
  });

  it("renders singular 'layer breached' for exactly one RED", () => {
    const { container } = render(
      <RiskHeroV2
        eyebrow="Risk"
        posture="breached"
        breachedCount={1}
        strainedCount={0}
      />,
    );
    expect(container.textContent ?? "").toContain("1 layer breached");
  });

  it("renders 'N under strain, none breached' when only YELLOW exists", () => {
    const layers = [
      { status: "NEUTRAL" as const },
      { status: "NEUTRAL" as const },
      { status: "POSITIVE" as const },
    ];
    const { breachedCount, strainedCount } = deriveCounts(layers);
    expect(breachedCount).toBe(0);
    expect(strainedCount).toBe(2);

    const { container } = render(
      <RiskHeroV2
        eyebrow="Risk"
        posture="attentive"
        breachedCount={breachedCount}
        strainedCount={strainedCount}
      />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain("2 under strain, none breached");
  });

  it("renders 'All layers within band' when every layer is GREEN", () => {
    const layers = [
      { status: "POSITIVE" as const },
      { status: "POSITIVE" as const },
    ];
    const { breachedCount, strainedCount } = deriveCounts(layers);
    expect(breachedCount).toBe(0);
    expect(strainedCount).toBe(0);

    const { container } = render(
      <RiskHeroV2
        eyebrow="Risk"
        posture="composed"
        breachedCount={breachedCount}
        strainedCount={strainedCount}
      />,
    );
    expect(container.textContent ?? "").toContain("All layers within band");
  });
});
