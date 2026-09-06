import { describe, it, expect } from "vitest";

import { declaredSurfaceLabel, declaredSurfaceHighlights } from "@/lib/cfo/hooks";
import { DECLARED_PERSONA_CODES, WIZARD_QUESTIONS } from "@/data/onboarding-questions";

/**
 * §101 compliance regression guard (legal F-01).
 *
 * v3 (2026-09-06): the onboarding RESULT screen no longer shows a persona at
 * all — it echoes the user's own answers. The 8-code persona the backend
 * derives (`profile_type`) still reaches other surfaces (`/mirror`, profile
 * hero, living-cfo status) through `declaredSurfaceLabel`, so this guard now
 * pins that every code the v3 rule table can emit collapses to one of the 3
 * disclosed buckets — 성장형 / 균형형 / 수익형 — and never a short-horizon name.
 */
const SURFACE_SET = new Set(["성장형", "균형형", "수익형"]);

// Granular persona NAMES that must never appear on any user-facing surface.
const GRANULAR_NAMES = [
  "Growth CFO", "Value CFO", "Balanced CFO", "Income CFO", "Quant CFO",
  "Speculator CFO", "Daytrader CFO", "Beginner CFO",
  "공격형 스캘퍼", "스윙 트레이더", "모멘텀 라이더", "매크로 로테이터",
  "가치투자 헌터", "패시브 인덱스 추종자", "꾸준한 적립 투자자", "리스크 관리형 성장투자",
  "투기형", "데이트레이더", "초심자",
];

describe("declared persona → §101 3-surface collapse (F-01)", () => {
  it("maps every v3-reachable persona code to a 3-surface label", () => {
    expect(DECLARED_PERSONA_CODES.length).toBe(8);
    for (const code of DECLARED_PERSONA_CODES) {
      const label = declaredSurfaceLabel(code);
      expect(label, `persona "${code}" must surface a 3-bucket label`).not.toBeNull();
      expect(
        SURFACE_SET.has(label as string),
        `persona "${code}" surfaced "${label}" — not in {성장형, 균형형, 수익형}`,
      ).toBe(true);
    }
  });

  it("never surfaces a granular persona NAME for any code", () => {
    for (const code of DECLARED_PERSONA_CODES) {
      const label = declaredSurfaceLabel(code) ?? "균형형";
      expect(GRANULAR_NAMES.includes(label), `persona "${code}" leaked "${label}"`).toBe(false);
    }
  });

  it("renders a safe 3-surface fallback (균형형) for unknown/empty codes — never granular", () => {
    for (const bad of ["", "totally_unknown_code", "scalper_x"]) {
      const label = declaredSurfaceLabel(bad) ?? "균형형";
      expect(SURFACE_SET.has(label)).toBe(true);
      expect(GRANULAR_NAMES.includes(label)).toBe(false);
    }
  });

  // ── Body guard (tagline + features on surfaces that still render them) ──
  const BANNED_BODY_TERMS = ["장중", "스윙", "스캘퍼", "단타", "실시간 신호", "잦은 시도", "투기"];

  it("never leaks granular short-horizon vocabulary in tagline/features for any code", () => {
    for (const code of DECLARED_PERSONA_CODES) {
      const h = declaredSurfaceHighlights(code);
      const rendered = [h.tagline, h.tagline_kr, ...h.features, ...h.features_kr].join("\n");
      for (const term of BANNED_BODY_TERMS) {
        expect(rendered.includes(term), `persona "${code}" leaked "${term}"`).toBe(false);
      }
      for (const name of GRANULAR_NAMES) {
        expect(rendered.includes(name), `persona "${code}" leaked name "${name}"`).toBe(false);
      }
      expect(h.tagline.length).toBeGreaterThan(0);
      expect(h.features.length).toBeGreaterThan(0);
      expect(h.features_kr.length).toBeGreaterThan(0);
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
