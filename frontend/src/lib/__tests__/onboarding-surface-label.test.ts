import { describe, it, expect } from "vitest";

import { declaredSurfaceLabel, declaredSurfaceHighlights } from "@/lib/cfo/hooks";
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

  // ── Result-screen BODY guard (tagline + features) ──────────────────────────
  //
  // Closes the gap where the headline collapsed to 3 buckets but the
  // tagline/features body still rendered granular short-horizon persona copy
  // (e.g. "속도가 곧 우위, 짧은 손절과 잦은 시도." / "장중 모멘텀 + 변동성 모델"
  // / "실시간 신호 스트리밍" / "스윙 진입·청산 신호"). The result screen now
  // renders tagline/features via declaredSurfaceHighlights() — this asserts no
  // banned short-horizon vocabulary survives for any of the 8 result codes.
  const BANNED_BODY_TERMS = [
    "장중",
    "스윙",
    "스캘퍼",
    "단타",
    "실시간 신호",
    "잦은 시도",
    "투기",
  ];

  it("never leaks granular short-horizon vocabulary in tagline/features for any of the 8 result types", () => {
    const resultTypes = Object.keys(INVESTOR_TYPES);
    expect(resultTypes.length).toBe(8);

    for (const code of resultTypes) {
      const h = declaredSurfaceHighlights(code);
      // Mirror exactly what the result screen renders (ko + en surfaces).
      const rendered = [
        h.tagline,
        h.tagline_kr,
        ...h.features,
        ...h.features_kr,
      ].join("\n");

      for (const term of BANNED_BODY_TERMS) {
        expect(
          rendered.includes(term),
          `result type "${code}" leaked banned body term "${term}" in tagline/features`,
        ).toBe(false);
      }

      // Body must be non-empty (feature preservation: screen still renders content).
      expect(h.tagline.length, `result type "${code}" has empty tagline`).toBeGreaterThan(0);
      expect(h.features.length, `result type "${code}" has no features`).toBeGreaterThan(0);
      expect(h.features_kr.length, `result type "${code}" has no KR features`).toBeGreaterThan(0);
    }
  });

  it("never leaks a granular persona NAME in tagline/features either", () => {
    for (const code of Object.keys(INVESTOR_TYPES)) {
      const h = declaredSurfaceHighlights(code);
      const rendered = [h.tagline, h.tagline_kr, ...h.features, ...h.features_kr].join("\n");
      for (const name of GRANULAR_NAMES) {
        expect(
          rendered.includes(name),
          `result type "${code}" leaked granular persona NAME "${name}" in body`,
        ).toBe(false);
      }
    }
  });

  it("falls back to non-granular balanced body for unknown/empty codes", () => {
    for (const bad of ["", "totally_unknown_code", "scalper_x"]) {
      const h = declaredSurfaceHighlights(bad);
      const rendered = [h.tagline, h.tagline_kr, ...h.features, ...h.features_kr].join("\n");
      for (const term of BANNED_BODY_TERMS) {
        expect(rendered.includes(term)).toBe(false);
      }
      expect(h.features.length).toBeGreaterThan(0);
    }
  });
});
