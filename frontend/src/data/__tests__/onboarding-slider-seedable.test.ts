import { describe, it, expect } from "vitest";
import { WIZARD_QUESTIONS } from "@/data/onboarding-questions";

/**
 * Regression guard for the 2026-05-28 onboarding slider dead-end.
 *
 * The wizard's `knowledge_self_rating` slider rendered at its `min` value but
 * never wrote that default to `answers`, so `isStepValid` (ans !== undefined)
 * stayed false and the "Next" button was dead until the user happened to drag
 * the handle — blocking every new user at the final wizard step. The fix seeds
 * `question.min ?? 1` into state on entry, so each slider question MUST define a
 * numeric `min` for the seeded default to land inside its valid range.
 */
describe("onboarding slider questions are seedable", () => {
  it("every slider question defines a numeric min", () => {
    const sliders = WIZARD_QUESTIONS.filter((q) => q.type === "slider");
    expect(sliders.length).toBeGreaterThan(0);
    for (const q of sliders) {
      expect(typeof q.min, `slider "${q.id}" must define min`).toBe("number");
    }
  });
});
