import { describe, it, expect } from "vitest";
import {
  computeProfitLossView,
  EM_DASH,
  MIN_PAIRS,
} from "@/components/journal/profit-loss-mirror";
import koMessages from "@/messages/ko.json";
import enMessages from "@/messages/en.json";
import type { ProfitLossMirrorResponse } from "@/lib/types";

function base(
  overrides: Partial<ProfitLossMirrorResponse> = {},
): ProfitLossMirrorResponse {
  return {
    ok: true,
    period: "all",
    sufficient_data: true,
    one_sided: false,
    total_closed_pairs: 14,
    take_profit: {
      count: 6,
      median_hold_days: 8,
      mean_hold_days: 9,
      median_gain_pct: 6.2,
      mean_gain_pct: 7.1,
    },
    stop_loss: {
      count: 8,
      median_hold_days: 31,
      mean_hold_days: 33,
      median_loss_pct: -9.4,
      mean_loss_pct: -11.2,
    },
    ...overrides,
  };
}

describe("computeProfitLossView", () => {
  it("formats stable hold days with the i18n unit and rounds", () => {
    const v = computeProfitLossView(base(), "일");
    expect(v.enough).toBe(true);
    expect(v.takeProfit.hold).toBe("8일");
    expect(v.stopLoss.hold).toBe("31일");
  });

  it("keeps the raw sign on realised return % (gain +, loss -)", () => {
    const v = computeProfitLossView(base(), "d");
    expect(v.takeProfit.ret).toBe("+6.2%");
    // Loss keeps its native negative sign — never abs().
    expect(v.stopLoss.ret).toBe("-9.4%");
  });

  it("prefers median over mean for both hold days and return %", () => {
    const v = computeProfitLossView(
      base({
        take_profit: {
          count: 6,
          median_hold_days: 8,
          mean_hold_days: 999,
          median_gain_pct: 5,
          mean_gain_pct: 800,
        },
      }),
      "d",
    );
    expect(v.takeProfit.days).toBe(8);
    expect(v.takeProfit.hold).toBe("8d");
    expect(v.takeProfit.ret).toBe("+5%");
  });

  it("falls back to mean hold days when median is null", () => {
    const v = computeProfitLossView(
      base({
        take_profit: {
          count: 6,
          median_hold_days: null,
          mean_hold_days: 12,
          median_gain_pct: null,
          mean_gain_pct: 4,
        },
      }),
      "d",
    );
    expect(v.takeProfit.days).toBe(12);
    expect(v.takeProfit.hold).toBe("12d");
    expect(v.takeProfit.ret).toBe("+4%");
  });

  it("scales the longer hold to full width and the shorter proportionally", () => {
    const v = computeProfitLossView(base(), "일"); // 8 vs 31
    expect(v.stopLoss.weight).toBeCloseTo(1, 5);
    expect(v.takeProfit.weight).toBeCloseTo(8 / 31, 5);
  });

  it("carries only hold/ret/weight/days (no tone/score/grade field)", () => {
    const v = computeProfitLossView(base(), "일");
    expect(Object.keys(v.takeProfit).sort()).toEqual([
      "days",
      "hold",
      "ret",
      "weight",
    ]);
    expect(Object.keys(v.stopLoss).sort()).toEqual([
      "days",
      "hold",
      "ret",
      "weight",
    ]);
  });

  it("uses em-dash sentinels + zero weight below the pair threshold", () => {
    const v = computeProfitLossView(
      base({ sufficient_data: false, total_closed_pairs: 3 }),
      "일",
    );
    expect(v.enough).toBe(false);
    expect(v.takeProfit.hold).toBe(EM_DASH);
    expect(v.takeProfit.ret).toBe(EM_DASH);
    expect(v.stopLoss.hold).toBe(EM_DASH);
    expect(v.stopLoss.ret).toBe(EM_DASH);
    expect(v.takeProfit.weight).toBe(0);
    expect(v.stopLoss.weight).toBe(0);
  });

  it("treats a one-sided window (empty loss side) with an em-dash, not a 0", () => {
    const v = computeProfitLossView(
      base({
        one_sided: true,
        total_closed_pairs: 6,
        stop_loss: {
          count: 0,
          median_hold_days: null,
          mean_hold_days: null,
          median_loss_pct: null,
          mean_loss_pct: null,
        },
      }),
      "일",
    );
    expect(v.takeProfit.hold).toBe("8일");
    expect(v.stopLoss.hold).toBe(EM_DASH);
    expect(v.stopLoss.ret).toBe(EM_DASH);
    expect(v.stopLoss.weight).toBe(0);
  });

  it("handles a null side (real backend shape) without crashing", () => {
    const v = computeProfitLossView(
      base({ one_sided: true, total_closed_pairs: 6, stop_loss: null }),
      "일",
    );
    expect(v.takeProfit.hold).toBe("8일");
    expect(v.stopLoss.hold).toBe(EM_DASH);
    expect(v.stopLoss.days).toBeNull();
    expect(v.stopLoss.weight).toBe(0);
  });

  it("handles both sides null (insufficient data) without crashing", () => {
    const v = computeProfitLossView(
      base({
        sufficient_data: false,
        total_closed_pairs: 2,
        take_profit: null,
        stop_loss: null,
      }),
      "d",
    );
    expect(v.enough).toBe(false);
    expect(v.takeProfit.hold).toBe(EM_DASH);
    expect(v.stopLoss.hold).toBe(EM_DASH);
  });

  it("requires at least MIN_PAIRS even when sufficient_data is true", () => {
    const v = computeProfitLossView(
      base({ sufficient_data: true, total_closed_pairs: MIN_PAIRS - 1 }),
      "일",
    );
    expect(v.enough).toBe(false);
    expect(v.takeProfit.hold).toBe(EM_DASH);
  });

  it("renders a zero return % without a stray + sign", () => {
    const v = computeProfitLossView(
      base({
        take_profit: {
          count: 6,
          median_hold_days: 8,
          mean_hold_days: 9,
          median_gain_pct: 0,
          mean_gain_pct: 0,
        },
      }),
      "d",
    );
    // 0 is neither >0 nor a native negative → plain "0%".
    expect(v.takeProfit.ret).toBe("0%");
  });
});

describe("profit-loss-mirror i18n", () => {
  const REQUIRED = [
    "kicker",
    "heading",
    "daysUnit",
    "avgHold",
    "avgReturn",
    "takeProfitLabel",
    "stopLossLabel",
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
    if (journal && journal["profitLossMirror"]) {
      return journal["profitLossMirror"] as Record<string, string>;
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

  it("never surfaces a scoring / diagnosis / bias / verdict term in the copy", () => {
    const ko = deepFind(koMessages)!;
    const en = deepFind(enMessages)!;
    const blob = [...Object.values(ko), ...Object.values(en)].join(" ");
    const lower = blob.toLowerCase();
    // The mirror passes no judgement: no 처분효과/편향/hazard label, no score,
    // no diagnosis/treatment vocabulary, no 과속/지연/개선 verdict, no
    // investment recommendation. "익절/손절" carry a trade-instruction nuance
    // (legal recommends the descriptive "실현 매도" form) — also banned here.
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
      "과속",
      "지연",
      "개선",
      "익절",
      "손절",
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
