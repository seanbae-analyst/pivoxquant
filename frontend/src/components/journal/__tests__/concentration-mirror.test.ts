import { describe, it, expect } from "vitest";
import {
  computeConcentrationView,
  EM_DASH,
} from "@/components/journal/concentration-mirror";
import koMessages from "@/messages/ko.json";
import enMessages from "@/messages/en.json";
import type { ConcentrationMirrorResponse } from "@/lib/types";

const NOTE = "평균매입가 기준 (시장가 아님)";

function base(
  overrides: Partial<ConcentrationMirrorResponse> = {},
): ConcentrationMirrorResponse {
  return {
    ok: true,
    sufficient_data: true,
    ticker_count: 3,
    max_weight_pct: 67.3,
    largest_ticker: "삼성전자",
    cost_basis_note: NOTE,
    ...overrides,
  };
}

describe("computeConcentrationView", () => {
  it("formats the weight as a percent string and surfaces the largest name", () => {
    const v = computeConcentrationView(base(), "fallback");
    expect(v.enough).toBe(true);
    expect(v.count).toBe(3);
    expect(v.largest).toBe("삼성전자");
    expect(v.weight).toBe("67.3%");
  });

  it("prefers the backend cost_basis_note verbatim over the i18n fallback", () => {
    const v = computeConcentrationView(base(), "fallback note");
    expect(v.note).toBe(NOTE);
  });

  it("falls back to the i18n note only when the backend omits one", () => {
    const v = computeConcentrationView(
      base({ cost_basis_note: "   " }),
      "fallback note",
    );
    expect(v.note).toBe("fallback note");
  });

  it("shows a single holding as a plain 100% fact (no warning state)", () => {
    const v = computeConcentrationView(
      base({ ticker_count: 1, max_weight_pct: 100, largest_ticker: "삼성전자" }),
      "fallback",
    );
    expect(v.enough).toBe(true);
    expect(v.count).toBe(1);
    expect(v.weight).toBe("100%");
  });

  it("uses the em-dash sentinel when sufficient_data is false", () => {
    const v = computeConcentrationView(
      base({
        sufficient_data: false,
        ticker_count: 0,
        max_weight_pct: null,
        largest_ticker: null,
      }),
      "fallback",
    );
    expect(v.enough).toBe(false);
    expect(v.weight).toBe(EM_DASH);
    expect(v.largest).toBe(EM_DASH);
    expect(v.count).toBe(0);
  });

  it("uses the em-dash sentinel (never a fabricated 0) when weight is null", () => {
    const v = computeConcentrationView(
      base({ max_weight_pct: null, largest_ticker: null }),
      "fallback",
    );
    expect(v.enough).toBe(false);
    expect(v.weight).toBe(EM_DASH);
    expect(v.largest).toBe(EM_DASH);
  });

  it("keeps the view-model free of any score / tone / grade field", () => {
    const v = computeConcentrationView(base(), "fallback");
    // Only factual fields — no tone/score/grade/colour leaks the mirror.
    expect(Object.keys(v).sort()).toEqual([
      "count",
      "enough",
      "largest",
      "note",
      "weight",
    ]);
  });
});

describe("concentration-mirror i18n", () => {
  const REQUIRED = [
    "kicker",
    "heading",
    "factCountLabel",
    "factCountUnit",
    "factLead",
    "factWeightLabel",
    "costBasisNote",
    "framing",
    "emptyTitle",
    "emptyDesc",
  ];

  function deepFind(obj: unknown): Record<string, string> | null {
    if (!obj || typeof obj !== "object") return null;
    const rec = obj as Record<string, unknown>;
    const journal = rec["journal"] as Record<string, unknown> | undefined;
    if (journal && journal["concentrationMirror"]) {
      return journal["concentrationMirror"] as Record<string, string>;
    }
    for (const k of Object.keys(rec)) {
      const found = deepFind(rec[k]);
      if (found) return found;
    }
    return null;
  }

  it("has every required key in ko + en", () => {
    const ko = deepFind(koMessages);
    const en = deepFind(enMessages);
    expect(ko).not.toBeNull();
    expect(en).not.toBeNull();
    for (const key of REQUIRED) {
      // factCountUnit may legitimately be an empty string in en — assert it
      // is present (a defined string), not necessarily truthy.
      expect(ko?.[key], `ko missing ${key}`).toBeTypeOf("string");
      expect(en?.[key], `en missing ${key}`).toBeTypeOf("string");
    }
    // Non-empty keys (everything except the optional unit suffix).
    for (const key of REQUIRED.filter((k) => k !== "factCountUnit")) {
      expect(ko?.[key], `ko empty ${key}`).toBeTruthy();
      expect(en?.[key], `en empty ${key}`).toBeTruthy();
    }
  });

  it("never surfaces a scoring / risk-judgement / bias term in the copy", () => {
    const ko = deepFind(koMessages)!;
    const en = deepFind(enMessages)!;
    // The framing line deliberately *negates* judgement ("평가나 권유는 담지
    // 않습니다" / "No grade, no recommendation.") — so the negated tokens
    // (추천/조언/권유 / "recommend" / "grade") legitimately appear ONLY there.
    // We scan every OTHER copy value to prove the affirmative judgement
    // vocabulary never leaks into the user-facing facts (same posture as the
    // holding-mirror i18n guard).
    const blob = [
      ...Object.entries(ko)
        .filter(([k]) => k !== "framing")
        .map(([, v]) => v),
      ...Object.entries(en)
        .filter(([k]) => k !== "framing")
        .map(([, v]) => v),
    ].join(" ");
    const lower = blob.toLowerCase();
    for (const banned of [
      "과집중",
      "집중 위험",
      "집중위험",
      "분산 필요",
      "분산필요",
      "위험도",
      "위험 수준",
      "편향",
      "점수",
      "등급",
      "별점",
      "뱃지",
      "게이지",
      "퍼센타일",
      "진단",
      "치료",
      "diagnos",
      "risk level",
      "score",
      "grade",
      "gauge",
      "bias",
      "추천",
      "조언",
    ]) {
      expect(
        lower,
        `banned token "${banned}" leaked into copy`,
      ).not.toContain(banned.toLowerCase());
    }
    // The only occurrence of a recommendation token must be the negation.
    expect(ko.framing).toContain("담지 않습니다");
    expect(en.framing.toLowerCase()).toContain("no recommendation");
    // Cost-basis clarifier must state it is NOT market price (oversight guard).
    expect(ko.costBasisNote).toContain("시장가 아님");
    expect(en.costBasisNote.toLowerCase()).toContain("not market price");
  });
});
