import { describe, it, expect } from "vitest";
import {
  computeRebuyView,
  EM_DASH,
  MIN_PAIRS,
} from "@/components/journal/rebuy-mirror";
import koMessages from "@/messages/ko.json";
import enMessages from "@/messages/en.json";
import type { RebuyMirrorResponse } from "@/lib/types";

function base(overrides: Partial<RebuyMirrorResponse> = {}): RebuyMirrorResponse {
  return {
    ok: true,
    period: "all",
    period_days: null,
    rebuy_window_days: 90,
    sufficient_data: true,
    rebuy_count: 5,
    higher_count: 3,
    lower_count: 2,
    flat_count: 0,
    median_gap_days: 12.4,
    median_price_change_pct: 4.25,
    by_ticker: [
      { ticker: "AAPL", name: "Apple Inc.", rebuy_count: 3, higher_count: 2, lower_count: 1 },
      { ticker: "005930", name: "삼성전자", rebuy_count: 2, higher_count: 1, lower_count: 1 },
    ],
    ...overrides,
  };
}

const INSUFFICIENT: Partial<RebuyMirrorResponse> = {
  sufficient_data: false,
  rebuy_count: null,
  higher_count: null,
  lower_count: null,
  flat_count: null,
  median_gap_days: null,
  median_price_change_pct: null,
  by_ticker: [],
};

describe("computeRebuyView", () => {
  it("formats counts, gap days and a signed median change", () => {
    const v = computeRebuyView(base());
    expect(v.enough).toBe(true);
    expect(v.rebuy).toBe("5");
    expect(v.higher).toBe("3");
    expect(v.lower).toBe("2");
    expect(v.gapDays).toBe("12");
    expect(v.change).toBe("+4.3%");
    expect(v.windowDays).toBe("90");
  });

  it("keeps a negative change negative and shows zero without a sign", () => {
    expect(computeRebuyView(base({ median_price_change_pct: -3.04 })).change).toBe("-3%");
    expect(computeRebuyView(base({ median_price_change_pct: 0 })).change).toBe("0%");
  });

  it("resolves per-ticker display names", () => {
    const v = computeRebuyView(base());
    expect(v.tickers).toHaveLength(2);
    expect(v.tickers[0]).toEqual({
      ticker: "AAPL",
      name: "Apple Inc.",
      rebuy: "3",
      higher: "2",
      lower: "1",
    });
    expect(v.tickers[1].name).toBe("삼성전자");
  });

  it("uses em-dash sentinels and no ticker rows when insufficient", () => {
    const v = computeRebuyView(base(INSUFFICIENT));
    expect(v.enough).toBe(false);
    for (const field of [v.rebuy, v.higher, v.lower, v.gapDays, v.change]) {
      expect(field).toBe(EM_DASH);
    }
    expect(v.tickers).toHaveLength(0);
  });

  it("requires at least MIN_PAIRS even when sufficient_data is true", () => {
    const v = computeRebuyView(base({ rebuy_count: MIN_PAIRS - 1 }));
    expect(v.enough).toBe(false);
    expect(v.change).toBe(EM_DASH);
    expect(v.tickers).toHaveLength(0);
  });

  it("carries only the documented view fields (no score/grade)", () => {
    const v = computeRebuyView(base());
    expect(Object.keys(v).sort()).toEqual([
      "change",
      "enough",
      "gapDays",
      "higher",
      "lower",
      "rebuy",
      "tickers",
      "windowDays",
    ]);
  });
});

describe("rebuy-mirror i18n", () => {
  const REQUIRED = [
    "kicker",
    "heading",
    "rebuyLabel",
    "higherLabel",
    "lowerLabel",
    "gapLabel",
    "changeLabel",
    "daysUnit",
    "byTickerLabel",
    "tickerRow",
    "framing",
    "emptyTitle",
    "emptyDesc",
    "insufficient",
  ];

  const ko: Record<string, string> = koMessages.journal.rebuyMirror;
  const en: Record<string, string> = enMessages.journal.rebuyMirror;

  it("has every required key in ko + en", () => {
    for (const key of REQUIRED) {
      expect(ko?.[key], `ko missing ${key}`).toBeTruthy();
      expect(en?.[key], `en missing ${key}`).toBeTruthy();
    }
  });

  it("states the window in the framing and empty copy", () => {
    for (const msgs of [ko, en]) {
      expect(msgs.framing).toContain("{window}");
      expect(msgs.emptyDesc).toContain("{window}");
    }
  });

  it("never surfaces a scoring / verdict / advisory term in the copy", () => {
    const blob = [...Object.values(ko), ...Object.values(en)].join(" ");
    const lower = blob.toLowerCase();
    for (const banned of [
      "손실",
      "위험",
      "실수",
      "잘못",
      "후회",
      "편향",
      "진단",
      "점수",
      "등급",
      "추천",
      "조언",
      "사세요",
      "파세요",
      "팔아",
      "mistake",
      "regret",
      "score",
      "grade",
      "should",
    ]) {
      expect(lower, `copy contains ${banned}`).not.toContain(banned);
    }
    // English advisory verbs as whole words (legal_filter deny-list).
    expect(blob).not.toMatch(/\b(?:buy|sell|recommend|advice|advise)\b/i);
  });
});
