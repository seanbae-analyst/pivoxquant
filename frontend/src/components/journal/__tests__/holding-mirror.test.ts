import { describe, it, expect } from "vitest";
import {
  computeMirrorView,
  EM_DASH,
  MIN_PAIRS,
} from "@/components/journal/holding-mirror";
import koMessages from "@/messages/ko.json";
import enMessages from "@/messages/en.json";
import type { HoldingMirrorResponse } from "@/lib/types";

function base(overrides: Partial<HoldingMirrorResponse> = {}): HoldingMirrorResponse {
  return {
    ok: true,
    period: "최근 90일",
    sufficient_data: true,
    one_sided: false,
    total_closed_pairs: 14,
    winners: { count: 6, median_hold_days: 8, mean_hold_days: 9, examples: [] },
    losers: { count: 8, median_hold_days: 31, mean_hold_days: 33, examples: [] },
    ...overrides,
  };
}

describe("computeMirrorView", () => {
  it("formats stable averages with the i18n unit and rounds days", () => {
    const v = computeMirrorView(base(), "일");
    expect(v.enough).toBe(true);
    expect(v.winners.value).toBe("8일");
    expect(v.losers.value).toBe("31일");
  });

  it("prefers median over mean for the displayed days", () => {
    const v = computeMirrorView(
      base({
        winners: { count: 6, median_hold_days: 8, mean_hold_days: 999, examples: [] },
      }),
      "d",
    );
    expect(v.winners.days).toBe(8);
    expect(v.winners.value).toBe("8d");
  });

  it("falls back to mean when median is null", () => {
    const v = computeMirrorView(
      base({
        winners: { count: 6, median_hold_days: null, mean_hold_days: 12, examples: [] },
      }),
      "d",
    );
    expect(v.winners.days).toBe(12);
    expect(v.winners.value).toBe("12d");
  });

  it("scales the longer hold to full width and the shorter proportionally", () => {
    const v = computeMirrorView(base(), "일"); // 8 vs 31
    // Longer side (losers, 31) reaches full width.
    expect(v.losers.weight).toBeCloseTo(1, 5);
    // Shorter side is 8/31 of the bar.
    expect(v.winners.weight).toBeCloseTo(8 / 31, 5);
  });

  it("keeps both sides neutral (no colour/score field is produced)", () => {
    const v = computeMirrorView(base(), "일");
    // The view model only carries value/weight/days — no tone/score/grade.
    expect(Object.keys(v.winners).sort()).toEqual(["days", "value", "weight"]);
    expect(Object.keys(v.losers).sort()).toEqual(["days", "value", "weight"]);
  });

  it("uses the em-dash sentinel + zero weight when below the pair threshold", () => {
    const v = computeMirrorView(
      base({ sufficient_data: false, total_closed_pairs: 3 }),
      "일",
    );
    expect(v.enough).toBe(false);
    expect(v.winners.value).toBe(EM_DASH);
    expect(v.losers.value).toBe(EM_DASH);
    expect(v.winners.weight).toBe(0);
    expect(v.losers.weight).toBe(0);
  });

  it("treats a one-sided window (empty losers) with an em-dash, not a fabricated 0", () => {
    const v = computeMirrorView(
      base({
        one_sided: true,
        total_closed_pairs: 6,
        losers: { count: 0, median_hold_days: null, mean_hold_days: null, examples: [] },
      }),
      "일",
    );
    expect(v.winners.value).toBe("8일");
    expect(v.losers.value).toBe(EM_DASH);
    expect(v.losers.weight).toBe(0);
  });

  it("handles a null side (real backend shape) without crashing", () => {
    // Backend nulls the empty side of a one-sided window (holding_mirror.py).
    const v = computeMirrorView(
      base({ one_sided: true, total_closed_pairs: 6, losers: null }),
      "일",
    );
    expect(v.winners.value).toBe("8일");
    expect(v.losers.value).toBe(EM_DASH);
    expect(v.losers.days).toBeNull();
    expect(v.losers.weight).toBe(0);
  });

  it("handles both sides null (insufficient data) without crashing", () => {
    const v = computeMirrorView(
      base({ sufficient_data: false, total_closed_pairs: 2, winners: null, losers: null }),
      "d",
    );
    expect(v.enough).toBe(false);
    expect(v.winners.value).toBe(EM_DASH);
    expect(v.losers.value).toBe(EM_DASH);
  });

  it("requires at least MIN_PAIRS even when sufficient_data is true", () => {
    const v = computeMirrorView(
      base({ sufficient_data: true, total_closed_pairs: MIN_PAIRS - 1 }),
      "일",
    );
    expect(v.enough).toBe(false);
    expect(v.winners.value).toBe(EM_DASH);
  });
});

describe("holding-mirror i18n", () => {
  const REQUIRED = [
    "kicker",
    "heading",
    "daysUnit",
    "avgHold",
    "winnersLabel",
    "losersLabel",
    "countsLabel",
    "countsValue",
    "framing",
    "insufficient",
    "emptyTitle",
    "emptyDesc",
  ];

  function deepFind(obj: unknown): Record<string, string> | null {
    if (!obj || typeof obj !== "object") return null;
    const rec = obj as Record<string, unknown>;
    const journal = rec["journal"] as Record<string, unknown> | undefined;
    if (journal && journal["holdingMirror"]) {
      return journal["holdingMirror"] as Record<string, string>;
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
      expect(ko?.[key], `ko missing ${key}`).toBeTruthy();
      expect(en?.[key], `en missing ${key}`).toBeTruthy();
    }
  });

  it("never surfaces a scoring / diagnosis / bias term in the copy", () => {
    const ko = deepFind(koMessages)!;
    const en = deepFind(enMessages)!;
    const blob = [...Object.values(ko), ...Object.values(en)].join(" ");
    // The mirror passes no judgement: no 처분효과/편향/hazard label, no score,
    // no diagnosis/treatment vocabulary, and no investment recommendation.
    // NOTE: the framing line deliberately *negates* recommendation
    // ("평가나 권유는 담지 않습니다" / "no grade, no recommendation") — so the
    // affirmative tokens 추천/조언/권유 and "recommend" must NOT appear EXCEPT
    // inside that negated disclaimer. We assert the banned tokens are absent
    // outside the framing line.
    const lower = blob.toLowerCase();
    for (const banned of [
      "처분효과",
      "편향",
      "hazard",
      "진단",
      "치료",
      "점수",
      "등급",
      "별점",
      "뱃지",
      "게이지",
      "퍼센타일",
      "심리건강",
      "diagnos",
      "추천",
      "조언",
      "bias",
    ]) {
      expect(lower, `banned token "${banned}" leaked into copy`).not.toContain(
        banned.toLowerCase(),
      );
    }
    // The only occurrence of "recommend" / "권유" must be the negation.
    expect(ko.framing).toContain("담지 않습니다");
    expect(en.framing.toLowerCase()).toContain("no recommendation");
  });
});
