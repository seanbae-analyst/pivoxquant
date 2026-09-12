/**
 * SelfObservedRadar — unmeasured axes are never drawn as measurements.
 *
 * 2026-09-10: the classifier leaves a 0.5 default on axes it had no evidence
 * for. Drawing the observed polygon through those defaults, and printing
 * "50%" under them, showed behaviour that was never observed.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SelfObservedRadar } from "@/components/mirror/self-observed-radar";

const LABELS = ["a", "b", "c", "d", "e", "f", "g", "h", "i"];
const DECLARED = new Array(9).fill(0.6);
const OBSERVED = [0.9, 0.5, 0.5, 0.2, 0.5, 0.5, 0.7, 0.5, 0.5];

describe("SelfObservedRadar measured mask", () => {
  it("draws a closed observed shape when every axis was measured", () => {
    const { container } = render(
      <SelfObservedRadar labels={LABELS} declared={DECLARED} observed={OBSERVED} />,
    );
    // 4 reference rings + declared + observed
    expect(container.querySelectorAll("polygon")).toHaveLength(6);
    expect(container.querySelectorAll("circle")).toHaveLength(0);
    expect(container.textContent).not.toContain("—");
  });

  it("draws points only on measured axes and a dash under the rest", () => {
    const measured = [true, false, false, true, false, false, true, false, false];
    const { container } = render(
      <SelfObservedRadar
        labels={LABELS}
        declared={DECLARED}
        observed={OBSERVED}
        measured={measured}
      />,
    );
    expect(container.querySelectorAll("polygon")).toHaveLength(5);
    expect(container.querySelectorAll("circle")).toHaveLength(3);
    const text = container.textContent ?? "";
    expect(text).toContain("90%");
    expect(text).toContain("20%");
    expect(text).not.toContain("50%");
    expect((text.match(/—/g) ?? []).length).toBe(6);
  });

  it("shows no observed marks in the new stage", () => {
    const { container } = render(
      <SelfObservedRadar labels={LABELS} declared={DECLARED} observed={null} />,
    );
    expect(container.querySelectorAll("polygon")).toHaveLength(5);
    expect(container.querySelectorAll("circle")).toHaveLength(0);
  });
});
