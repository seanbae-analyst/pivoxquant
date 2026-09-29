import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import * as cfoHooks from "@/lib/cfo/hooks";
import { WIZARD_QUESTIONS } from "@/data/onboarding-questions";

/**
 * No persona type label on any surface (CEO 2026-09-29 —
 * CLAUDE.md "유형 라벨·점수는 만들지 않는다").
 *
 * This file used to pin that every declared persona code collapsed to one of
 * three disclosed buckets (성장형 / 균형형 / 수익형) via `declaredSurfaceLabel`.
 * The buckets themselves are no longer shown: the helpers are gone from
 * lib/cfo/hooks.ts and must not come back as a way to name a type.
 */
describe("persona type labels — not exported, not written", () => {
  it("lib/cfo/hooks exports no surface-label helper", () => {
    for (const name of [
      "surfaceLabel",
      "declaredSurfaceLabel",
      "declaredSurfaceHighlights",
      "PERSONA_LABELS",
    ]) {
      expect(name in cfoHooks, `${name} is exported again`).toBe(false);
    }
  });

  it("lib/cfo/hooks source carries no bucket name as a string literal", () => {
    const src = readFileSync(join(__dirname, "..", "cfo", "hooks.ts"), "utf8");
    for (const name of ["성장형", "균형형", "수익형"]) {
      expect(src).not.toMatch(new RegExp(`["'\`]${name}["'\`]`));
    }
  });
});

describe("v3 questionnaire copy — no grade, no type, no advice vocabulary", () => {
  const BANNED = ["추천", "조언", "점수", "등급", "AI", "레버리지", "수익률", "recommend", "advice", "score"];

  it("question and option copy stays observational", () => {
    for (const q of WIZARD_QUESTIONS) {
      const blob = [q.question, q.question_kr, ...q.options.flatMap((o) => [o.label, o.label_kr])].join("\n");
      for (const term of BANNED) {
        expect(blob.includes(term), `question "${q.id}" contains banned term "${term}"`).toBe(false);
      }
    }
  });
});
