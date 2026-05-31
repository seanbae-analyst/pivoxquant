import { describe, it, expect } from "vitest";
import {
  computeTurnoverView,
  EM_DASH,
  MIN_TRADES,
} from "@/components/journal/turnover-mirror";
import koMessages from "@/messages/ko.json";
import enMessages from "@/messages/en.json";
import type { TurnoverMirrorResponse } from "@/lib/types";

function base(
  overrides: Partial<TurnoverMirrorResponse> = {},
): TurnoverMirrorResponse {
  return {
    ok: true,
    period: "all",
    period_days: null,
    sufficient_data: true,
    trade_count: 12,
    buy_count: 7,
    sell_count: 5,
    by_currency: [
      { currency: "KRW", gross_value: 3_000_000, trade_count: 6 },
      { currency: "USD", gross_value: 4_000, trade_count: 6 },
    ],
    median_hold_days: 10,
    mean_hold_days: 14,
    ...overrides,
  };
}

describe("computeTurnoverView", () => {
  it("formats stable fill counts as plain integers", () => {
    const v = computeTurnoverView(base(), "일");
    expect(v.enough).toBe(true);
    expect(v.trades).toBe("12");
    expect(v.buys).toBe("7");
    expect(v.sells).toBe("5");
  });

  it("formats the average hold days with the i18n unit and rounds", () => {
    const v = computeTurnoverView(base(), "d");
    // median preferred (10) over mean (14)
    expect(v.hold).toBe("10d");
  });

  it("prefers median over mean for hold days", () => {
    const v = computeTurnoverView(
      base({ median_hold_days: 8, mean_hold_days: 999 }),
      "일",
    );
    expect(v.hold).toBe("8일");
  });

  it("falls back to mean hold days when median is null", () => {
    const v = computeTurnoverView(
      base({ median_hold_days: null, mean_hold_days: 12 }),
      "일",
    );
    expect(v.hold).toBe("12일");
  });

  it("shows an em-dash hold when no round trip closed", () => {
    const v = computeTurnoverView(
      base({ median_hold_days: null, mean_hold_days: null }),
      "일",
    );
    expect(v.hold).toBe(EM_DASH);
    // counts are still real (fills exist even with no closed pair)
    expect(v.trades).toBe("12");
  });

  it("renders per-currency rows separately (never FX-converted)", () => {
    const v = computeTurnoverView(base(), "일");
    expect(v.currencies).toHaveLength(2);
    const byCur = Object.fromEntries(
      v.currencies.map((r) => [r.currency, r]),
    );
    expect(byCur.KRW.count).toBe("6");
    expect(byCur.USD.count).toBe("6");
    // KRW myriad scale, USD SI scale — distinct, never a merged total.
    expect(byCur.KRW.gross).toContain("KRW");
    expect(byCur.USD.gross).toContain("USD");
  });

  it("uses em-dash sentinels + no currency rows below the threshold", () => {
    const v = computeTurnoverView(
      base({ sufficient_data: false, trade_count: 3, by_currency: [] }),
      "일",
    );
    expect(v.enough).toBe(false);
    expect(v.trades).toBe(EM_DASH);
    expect(v.buys).toBe(EM_DASH);
    expect(v.sells).toBe(EM_DASH);
    expect(v.hold).toBe(EM_DASH);
    expect(v.currencies).toHaveLength(0);
  });

  it("requires at least MIN_TRADES even when sufficient_data is true", () => {
    const v = computeTurnoverView(
      base({ sufficient_data: true, trade_count: MIN_TRADES - 1 }),
      "일",
    );
    expect(v.enough).toBe(false);
    expect(v.trades).toBe(EM_DASH);
    expect(v.currencies).toHaveLength(0);
  });

  it("handles null counts (insufficient backend shape) without crashing", () => {
    const v = computeTurnoverView(
      base({
        sufficient_data: false,
        trade_count: 2,
        buy_count: null,
        sell_count: null,
        by_currency: [],
        median_hold_days: null,
        mean_hold_days: null,
      }),
      "d",
    );
    expect(v.enough).toBe(false);
    expect(v.buys).toBe(EM_DASH);
    expect(v.sells).toBe(EM_DASH);
  });

  it("carries only the documented view fields (no score/grade/ratio)", () => {
    const v = computeTurnoverView(base(), "일");
    expect(Object.keys(v).sort()).toEqual([
      "buys",
      "currencies",
      "enough",
      "hold",
      "sells",
      "trades",
    ]);
    for (const row of v.currencies) {
      expect(Object.keys(row).sort()).toEqual([
        "count",
        "currency",
        "gross",
      ]);
    }
  });

  it("falls back to a grouped integer for a non-USD/KRW currency", () => {
    const v = computeTurnoverView(
      base({
        by_currency: [
          { currency: "JPY", gross_value: 1234567, trade_count: 8 },
        ],
      }),
      "일",
    );
    expect(v.currencies[0].gross).toContain("JPY");
    expect(v.currencies[0].gross).toContain("1,234,567");
  });
});

describe("turnover-mirror i18n", () => {
  const REQUIRED = [
    "kicker",
    "heading",
    "daysUnit",
    "tradesLabel",
    "buysLabel",
    "sellsLabel",
    "grossLabel",
    "currencyRow",
    "avgHold",
    "framing",
    "insufficient",
    "emptyTitle",
    "emptyDesc",
  ];

  function deepFind(obj: unknown): Record<string, string> | null {
    if (!obj || typeof obj !== "object") return null;
    const rec = obj as Record<string, unknown>;
    const journal = rec["journal"] as Record<string, unknown> | undefined;
    if (journal && journal["turnoverMirror"]) {
      return journal["turnoverMirror"] as Record<string, string>;
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

  it("never surfaces a scoring / verdict / activity-judgement term in the copy", () => {
    const ko = deepFind(koMessages)!;
    const en = deepFind(enMessages)!;
    const blob = [...Object.values(ko), ...Object.values(en)].join(" ");
    const lower = blob.toLowerCase();
    // The mirror passes no judgement on activity level: no 회전율/과잉거래
    // verdict, no "많다/잦다/과하다/과속/줄이세요/늘리세요" nudge, no score/
    // grade/diagnosis vocabulary, no investment recommendation.
    for (const banned of [
      "회전율",
      "과잉",
      "과속",
      "지연",
      "개선",
      "많다",
      "잦다",
      "과하다",
      "줄이",
      "늘리",
      "처분효과",
      "편향",
      "진단",
      "치료",
      "점수",
      "등급",
      "별점",
      "퍼센타일",
      "추천",
      "조언",
      "turnover ratio",
      "too many",
      "too much",
      "excessive",
      "overtrad",
      "diagnos",
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
