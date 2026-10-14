/**
 * lib/payday-plan — 월급날 배분 (2026-10-14).
 *
 * Pins: pay cycles run payday → next payday in KST calendar days, with a
 * 29–31 payday clamped to short months; the money a cycle's fills put in is
 * (bought − sold) per currency from the user's own rows, registration rows
 * excluded, USD converted only when a rate is known; a full 100-row page
 * whose oldest row is inside the cycle is flagged as possibly cut off; the
 * store is per user, tolerant of garbage, and capped.
 */
import { afterEach, describe, expect, it } from "vitest";

import {
  EMPTY_STORE,
  MAX_CYCLES,
  clearStore,
  cycleFlow,
  cycleFor,
  kstToday,
  loadStore,
  paydayIn,
  parseAmount,
  parseStore,
  previousCycle,
  reviewFor,
  saveStore,
  storageKey,
  unassigned,
  upsertCycle,
  type CyclePlan,
  type PaydayStore,
} from "@/lib/payday-plan";

afterEach(() => window.localStorage.clear());

const plan = (start: string, invest: number | null = 1_000_000): CyclePlan => ({
  start,
  income: null,
  parts: { living: 1_500_000, saving: 500_000, invest, other: null },
  review: {},
  savedAt: "2026-10-14T00:00:00Z",
});

describe("cycles", () => {
  it("runs from the most recent payday to the next one", () => {
    expect(cycleFor("2026-10-14", 25)).toEqual({ start: "2026-09-25", end: "2026-10-25" });
    expect(cycleFor("2026-10-25", 25)).toEqual({ start: "2026-10-25", end: "2026-11-25" });
    expect(cycleFor("2026-12-30", 25)).toEqual({ start: "2026-12-25", end: "2027-01-25" });
    expect(cycleFor("2027-01-03", 25)).toEqual({ start: "2026-12-25", end: "2027-01-25" });
  });

  it("clamps a late payday to the last day of a short month", () => {
    expect(paydayIn(2026, 2, 31)).toBe("2026-02-28");
    expect(paydayIn(2028, 2, 30)).toBe("2028-02-29");
    expect(cycleFor("2026-03-05", 31)).toEqual({ start: "2026-02-28", end: "2026-03-31" });
    expect(previousCycle("2026-03-31", 31)).toEqual({ start: "2026-02-28", end: "2026-03-31" });
  });

  it("today is the KST calendar date", () => {
    // 2026-10-13 16:00 UTC = 2026-10-14 01:00 KST.
    expect(kstToday(new Date("2026-10-13T16:00:00Z"))).toBe("2026-10-14");
    expect(kstToday(new Date("2026-10-13T14:59:00Z"))).toBe("2026-10-13");
  });
});

describe("plan arithmetic", () => {
  it("unassigned is income minus the written parts, null without income", () => {
    expect(unassigned({ income: null, parts: plan("2026-10-25").parts })).toBeNull();
    expect(unassigned({ income: 3_500_000, parts: plan("2026-10-25").parts })).toBe(500_000);
    expect(unassigned({ income: 2_000_000, parts: plan("2026-10-25").parts })).toBe(-1_000_000);
  });

  it("a typed actual says more / less / as planned against what was set", () => {
    expect(reviewFor(1_500_000, 1_820_000)).toBe("more");
    expect(reviewFor(1_500_000, 1_200_000)).toBe("less");
    expect(reviewFor(1_500_000, 1_500_000)).toBe("as_planned");
  });

  it("amounts are digits only", () => {
    expect(parseAmount("1,000,000")).toBe(1_000_000);
    expect(parseAmount("  250000원 ")).toBe(250_000);
    expect(parseAmount("")).toBeNull();
    expect(parseAmount("abc")).toBeNull();
  });
});

describe("what a cycle's fills put in", () => {
  const rows = [
    // backend shape
    { date: "2026-10-01", side: "Bought", total: 700_000, currency: "KRW", source: null },
    { date: "2026-10-03", side: "Sold", total: 200_000, currency: "KRW", source: null },
    { date: "2026-10-05", side: "Bought", total: 500, currency: "USD", source: null },
    // demo-fixture shape
    { date: "2026-10-06T01:00:00Z", side: "sell", amount: 100, currency: "USD" },
    // registration rows are not fills
    { date: "2026-10-07", side: "Bought", total: 9_999_999, currency: "KRW", source: "holding_seed" },
    { date: "2026-10-08", side: "Sold", total: 9_999_999, currency: "KRW", source: "holding_adjust" },
    // outside the cycle
    { date: "2026-09-24", side: "Bought", total: 1_000_000, currency: "KRW" },
    { date: "2026-10-25", side: "Bought", total: 1_000_000, currency: "KRW" },
  ];

  it("sums bought minus sold per currency inside [start, end)", () => {
    const f = cycleFlow(rows, "2026-09-25", "2026-10-25", 1_400);
    expect(f.KRW).toEqual({ in: 700_000, out: 200_000, net: 500_000 });
    expect(f.USD).toEqual({ in: 500, out: 100, net: 400 });
    expect(f.fills).toBe(4);
    expect(f.netKrw).toBe(500_000 + 400 * 1_400);
    expect(f.truncated).toBe(false);
  });

  it("without a rate, USD fills leave the KRW total unknown — never guessed", () => {
    expect(cycleFlow(rows, "2026-09-25", "2026-10-25", null).netKrw).toBeNull();
    const krwOnly = rows.filter((r) => r.currency === "KRW");
    expect(cycleFlow(krwOnly, "2026-09-25", "2026-10-25", null).netKrw).toBe(500_000);
  });

  it("falls back to qty × price when a row has no total", () => {
    const f = cycleFlow([{ date: "2026-10-01", side: "Bought", qty: 3, price: 10_000, currency: "KRW" }], "2026-09-25", "2026-10-25", null);
    expect(f.KRW.in).toBe(30_000);
  });

  it("a full page whose oldest row is inside the cycle may be cut off", () => {
    const page = Array.from({ length: 100 }, (_, i) => ({
      date: `2026-10-${String((i % 20) + 1).padStart(2, "0")}`,
      side: "Bought",
      total: 1,
      currency: "KRW",
    }));
    expect(cycleFlow(page, "2026-09-25", "2026-10-25", null).truncated).toBe(true);
    expect(cycleFlow(page.slice(0, 99), "2026-09-25", "2026-10-25", null).truncated).toBe(false);
  });
});

describe("storage (this browser, one key per user)", () => {
  it("round-trips and keeps users apart", () => {
    const store = upsertCycle({ ...EMPTY_STORE, payday: 25, cycles: [] }, plan("2026-10-25"));
    expect(saveStore(7, store)).toBe(true);
    expect(loadStore(7)).toEqual(store);
    expect(loadStore(8)).toEqual({ v: 1, payday: null, cycles: [] });
    expect(window.localStorage.getItem(storageKey(7))).toContain("2026-10-25");
    clearStore(7);
    expect(window.localStorage.getItem(storageKey(7))).toBeNull();
  });

  it("garbage reads as empty; bad fields are dropped, not trusted", () => {
    expect(parseStore("{not json")).toEqual({ v: 1, payday: null, cycles: [] });
    expect(parseStore(JSON.stringify({ v: 2, payday: 25 }))).toEqual({ v: 1, payday: null, cycles: [] });
    const s = parseStore(
      JSON.stringify({
        v: 1,
        payday: 99,
        cycles: [
          { start: "nope" },
          { start: "2026-10-25", income: -5, parts: { living: "x", invest: 100 }, review: { living: "lots" } },
        ],
      }),
    );
    expect(s.payday).toBeNull();
    expect(s.cycles).toHaveLength(1);
    expect(s.cycles[0].income).toBeNull();
    expect(s.cycles[0].parts).toEqual({ living: null, saving: null, invest: 100, other: null });
    expect(s.cycles[0].review).toEqual({});
    expect(s.cycles[0].actual).toBeUndefined();
  });

  it("keeps typed actuals for the self-reviewed parts only, and only real amounts", () => {
    const s = parseStore(
      JSON.stringify({
        v: 1,
        payday: 25,
        cycles: [
          {
            start: "2026-09-25",
            parts: { living: 1_500_000, saving: 500_000, invest: 1_000_000 },
            actual: { living: 1_820_000, saving: -5, other: "x", invest: 9 },
          },
        ],
      }),
    );
    expect(s.cycles[0].actual).toEqual({ living: 1_820_000 });
  });

  it("upsert replaces the same cycle and keeps only the newest cycles", () => {
    let store: PaydayStore = { ...EMPTY_STORE, payday: 25, cycles: [] };
    for (let i = 0; i < MAX_CYCLES + 3; i++) {
      const y = 2024 + Math.floor(i / 12);
      const m = (i % 12) + 1;
      store = upsertCycle(store, plan(paydayIn(y, m, 25)));
    }
    expect(store.cycles).toHaveLength(MAX_CYCLES);
    expect(store.cycles[0].start > "2024-01-25").toBe(true);
    const last = store.cycles[store.cycles.length - 1];
    store = upsertCycle(store, { ...last, parts: { ...last.parts, invest: 1 } });
    expect(store.cycles).toHaveLength(MAX_CYCLES);
    expect(store.cycles[store.cycles.length - 1].parts.invest).toBe(1);
  });
});
