/**
 * 적은 뒤 (lib/research.ts::afterNote) — what the research detail screen
 * lists after a note: the same stock's records from the moment it was
 * written, oldest first, plus the note's own 다시 볼 날 · 채점. The note
 * itself and holding imports are left out; date-only values count from the
 * note's KST day (the server's `_sold_after` rule).
 */
import { describe, expect, it } from "vitest";
import { afterNote, atOrAfterNote, kstToday } from "@/lib/research";
import type { ResearchNote, StockRecordEvent } from "@/lib/types";

// Written 2026-06-01 01:00 KST (= 2026-05-31 16:00 UTC).
const NOTE: ResearchNote = {
  id: 7, ticker: "005930.KS", name: "삼성전자", business: "", theses: ["메모리 가격이 반등한다"],
  invalidation: null, risk: null, numbers: null, info_source: "report", surface: "journal",
  review_on: "2026-09-01", verdicts: [], review_note: null, reviewed_at: null,
  created_at: "2026-05-31T16:00:00", due: false, outcome: "open",
};

const fill = (at: string, side: "buy" | "sell", extra: Partial<StockRecordEvent> = {}): StockRecordEvent =>
  ({ kind: "fill", at, side, shares: 3, price: 70000, currency: "KRW", after_pause: false, ...extra }) as StockRecordEvent;

describe("atOrAfterNote", () => {
  it("compares instants for timed values", () => {
    expect(atOrAfterNote("2026-05-31T15:59:59", NOTE.created_at)).toBe(false);
    expect(atOrAfterNote("2026-05-31T16:00:00.000001", NOTE.created_at)).toBe(true);
  });
  it("a date-only value counts from the note's KST day", () => {
    // The note's KST day is 06-01; a date-only 05-31 fill was before it.
    expect(atOrAfterNote("2026-05-31T00:00:00", NOTE.created_at)).toBe(false);
    expect(atOrAfterNote("2026-06-01T00:00:00", NOTE.created_at)).toBe(true);
  });
  it("is false without a date", () => {
    expect(atOrAfterNote(null, NOTE.created_at)).toBe(false);
    expect(atOrAfterNote("2026-06-02T00:00:01", null)).toBe(false);
  });
});

describe("afterNote", () => {
  const events: StockRecordEvent[] = [
    fill("2026-07-10T02:00:00.000001", "sell"),
    fill("2026-05-20T02:00:00.000001", "buy"), // before the note
    { kind: "registered", at: "2026-06-05T00:00:00", shares: 10, price: 60000, currency: "KRW" },
    { kind: "research", at: NOTE.created_at, id: 7, theses: [], invalidation: null, verdicts: [], review_on: null, reviewed_at: null, due: false },
    { kind: "research", at: "2026-08-01T01:00:00", id: 9, theses: ["다른 이유"], invalidation: null, verdicts: [], review_on: null, reviewed_at: null, due: false },
    { kind: "pause", at: "2026-06-03T03:00:00", side: "entry", rationale: "더 보고", status: "cancelled", bought_after: false },
    fill("2026-06-01T00:00:00", "buy"), // date-only, the note's KST day
    { kind: "note", at: "2026-06-20T05:00:00", id: 3, body: "실적 기다림", tags: [] },
  ];

  it("keeps what came after, oldest first, without the note or holding imports", () => {
    const out = afterNote(NOTE, events, "2026-10-27");
    expect(out.items.map((i) => (i.kind === "event" ? `${i.event.kind}:${i.at.slice(0, 10)}` : i.kind))).toEqual([
      "fill:2026-06-01",
      "pause:2026-06-03",
      "note:2026-06-20",
      "fill:2026-07-10",
      "research:2026-08-01",
      "review_day",
    ]);
    expect(out.counts).toEqual({ buys: 1, sells: 1, pauses: 1, notTaken: 1, notes: 1, research: 1, filings: 0 });
  });

  it("marks a review day still ahead, and the scoring day once scored", () => {
    const ahead = afterNote(NOTE, [], "2026-08-31").items;
    expect(ahead).toEqual([{ kind: "review_day", at: "2026-09-01T00:00:00", upcoming: true }]);

    const scored = afterNote({ ...NOTE, reviewed_at: "2026-09-02T03:00:00" }, [], "2026-10-27").items;
    expect(scored.map((i) => i.kind)).toEqual(["review_day", "scored"]);
    expect(scored[0]).toMatchObject({ upcoming: false });
  });
});

describe("kstToday", () => {
  it("is the Korean calendar day", () => {
    expect(kstToday(Date.UTC(2026, 9, 26, 15, 30))).toBe("2026-10-27");
  });
});
