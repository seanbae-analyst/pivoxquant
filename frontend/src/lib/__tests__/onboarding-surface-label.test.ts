import { describe, it, expect } from "vitest";

import { declaredSurfaceLabel } from "@/lib/cfo/hooks";
import { INVESTOR_TYPES } from "@/data/onboarding-questions";

/**
 * §101 compliance regression guard (legal F-01).
 *
 * The onboarding RESULT headline must surface exactly one of the 3 disclosed
 * buckets — 성장형 / 균형형 / 수익형 — and must NEVER name a short-horizon
 * granular persona (e.g. "공격형 스캘퍼" / "스윙 트레이더" / "모멘텀 추종형").
 *
 * The result screen feeds `investorType` (one of the INVESTOR_TYPES keys, i.e.
 * the same 8 questionnaire codes the local classifier can produce) into
 * `declaredSurfaceLabel`. This test pins that every possible result code maps
 * to a 3-surface label and that no granular NAME can leak through.
 */
const SURFACE_SET = new Set(["성장형", "균형형", "수익형"]);

// Every granular persona NAME that must never appear as a result headline.
const GRANULAR_NAMES = Object.values(INVESTOR_TYPES).flatMap((t) => [
  t.label,
  t.label_kr,
]);

describe("onboarding result label — §101 3-surface collapse (F-01)", () => {
  it("maps every questionnaire result type to a 3-surface label", () => {
    const resultTypes = Object.keys(INVESTOR_TYPES);
    expect(resultTypes.length).toBe(8); // sanity: all 8 codes present

    for (const code of resultTypes) {
      const label = declaredSurfaceLabel(code);
      expect(label, `result type "${code}" must surface a 3-bucket label`).not.toBeNull();
      expect(
        SURFACE_SET.has(label as string),
        `result type "${code}" surfaced "${label}" — not in {성장형, 균형형, 수익형}`,
      ).toBe(true);
    }
  });

  it("never surfaces a granular persona NAME for any result type", () => {
    for (const code of Object.keys(INVESTOR_TYPES)) {
      const label = declaredSurfaceLabel(code) ?? "균형형";
      expect(
        GRANULAR_NAMES.includes(label),
        `result type "${code}" leaked granular name "${label}"`,
      ).toBe(false);
    }
  });

  it("renders a safe 3-surface fallback (균형형) for unknown/empty codes — never granular", () => {
    for (const bad of ["", "totally_unknown_code", "scalper_x"]) {
      const label = declaredSurfaceLabel(bad) ?? "균형형";
      expect(SURFACE_SET.has(label)).toBe(true);
      expect(GRANULAR_NAMES.includes(label)).toBe(false);
    }
  });
});
