import { describe, it, expect } from "vitest";
import {
  computeAveragingDownView,
  EM_DASH,
  MIN_FOLLOW_ON,
} from "@/components/journal/averaging-down-mirror";
import koMessages from "@/messages/ko.json";
import enMessages from "@/messages/en.json";
import type { AveragingDownMirrorResponse } from "@/lib/types";

function base(
  overrides: Partial<AveragingDownMirrorResponse> = {},
): AveragingDownMirrorResponse {
  return {
    ok: true,
    period: "all",
    period_days: null,
    sufficient_data: true,
    follow_on_count: 6,
    below_avg_count: 4,
    above_avg_count: 1,
    flat_count: 1,
    by_ticker: [
      { ticker: "AAPL", name: "Apple Inc.", follow_on: 4, below_avg: 3, above_avg: 1 },
      { ticker: "005930", name: "삼성전자", follow_on: 2, below_avg: 1, above_avg: 0 },
    ],
    ...overrides,
  };
}

describe("computeAveragingDownView", () => {
  it("formats stable counts as plain integers", () => {
    const v = computeAveragingDownView(base());
    expect(v.enough).toBe(true);
    expect(v.followOn).toBe("6");
    expect(v.below).toBe("4");
    expect(v.above).toBe("1");
    expect(v.flat).toBe("1");
  });

  it("resolves per-ticker display names (never a naked ticker)", () => {
    const v = computeAveragingDownView(base());
    expect(v.tickers).toHaveLength(2);
    const byTicker = Object.fromEntries(
      v.tickers.map((r) => [r.ticker, r]),
    );
    expect(byTicker.AAPL.name).toBe("Apple Inc.");
    expect(byTicker.AAPL.followOn).toBe("4");
    expect(byTicker.AAPL.below).toBe("3");
    // KR code resolves to a name, not the bare 005930.
    expect(byTicker["005930"].name).toBe("삼성전자");
    expect(byTicker["005930"].name).not.toBe("005930");
  });

  it("falls back to a resolved name when backend name is null", () => {
    const v = computeAveragingDownView(
      base({
        by_ticker: [
          { ticker: "TSLA", name: null, follow_on: 3, below_avg: 2, above_avg: 1 },
        ],
      }),
    );
    // displayName resolves a known ticker; at minimum it is never the empty
    // string and never a different ticker code.
    expect(v.tickers[0].name.length).toBeGreaterThan(0);
  });

  it("uses em-dash sentinels + no ticker rows below the threshold", () => {
    const v = computeAveragingDownView(
      base({
        sufficient_data: false,
        follow_on_count: null,
        below_avg_count: null,
        above_avg_count: null,
        flat_count: null,
        by_ticker: [],
      }),
    );
    expect(v.enough).toBe(false);
    expect(v.followOn).toBe(EM_DASH);
    expect(v.below).toBe(EM_DASH);
    expect(v.above).toBe(EM_DASH);
    expect(v.flat).toBe(EM_DASH);
    expect(v.tickers).toHaveLength(0);
  });

  it("requires at least MIN_FOLLOW_ON even when sufficient_data is true", () => {
    const v = computeAveragingDownView(
      base({ sufficient_data: true, follow_on_count: MIN_FOLLOW_ON - 1 }),
    );
    expect(v.enough).toBe(false);
    expect(v.followOn).toBe(EM_DASH);
    expect(v.tickers).toHaveLength(0);
  });

  it("handles null counts (insufficient backend shape) without crashing", () => {
    const v = computeAveragingDownView(
      base({
        sufficient_data: false,
        follow_on_count: null,
        below_avg_count: null,
        above_avg_count: null,
        flat_count: null,
        by_ticker: [],
      }),
    );
    expect(v.enough).toBe(false);
    expect(v.below).toBe(EM_DASH);
    expect(v.above).toBe(EM_DASH);
  });

  it("carries only the documented view fields (no score/grade/ratio)", () => {
    const v = computeAveragingDownView(base());
    expect(Object.keys(v).sort()).toEqual([
      "above",
      "below",
      "enough",
      "flat",
      "followOn",
      "tickers",
    ]);
    for (const row of v.tickers) {
      expect(Object.keys(row).sort()).toEqual([
        "above",
        "below",
        "followOn",
        "name",
        "ticker",
      ]);
    }
  });
});

describe("averaging-down-mirror i18n", () => {
  const REQUIRED = [
    "kicker",
    "heading",
    "followOnLabel",
    "belowLabel",
    "aboveLabel",
    "byTickerLabel",
    "tickerRow",
    "framing",
    "insufficient",
    "emptyTitle",
    "emptyDesc",
  ];

  function deepFind(obj: unknown): Record<string, string> | null {
    if (!obj || typeof obj !== "object") return null;
    const rec = obj as Record<string, unknown>;
    const journal = rec["journal"] as Record<string, unknown> | undefined;
    if (journal && journal["averagingDownMirror"]) {
      return journal["averagingDownMirror"] as Record<string, string>;
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

  it("never surfaces a scoring / verdict / judgement term in the copy", () => {
    const ko = deepFind(koMessages)!;
    const en = deepFind(enMessages)!;
    const blob = [...Object.values(ko), ...Object.values(en)].join(" ");
    const lower = blob.toLowerCase();
    // The mirror passes no judgement: no 물타기 slang, no loss/risk/excess
    // nudge, no score/grade/diagnosis vocabulary, no investment recommendation.
    for (const banned of [
      "물타기",
      "과도",
      "과하다",
      "손실",
      "위험",
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
      "average down",
      "averaging down",
      "too much",
      "excessive",
      "diagnos",
      "bias",
      "loss",
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
