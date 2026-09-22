/**
 * /journal timeline merge — ordering, stability, tolerance.
 *
 * docs/design/observation-notes_2026-09-22.md §5. The feed mixes two record
 * kinds, so the rules that matter are: newest first, nothing dropped, and a
 * broken timestamp never reorders (or poisons) the rest of the list.
 */
import { describe, it, expect } from "vitest";
import {
  entryTimestamp,
  mergeTimeline,
  filterTimeline,
  recentNoteSummary,
  timestampMs,
} from "@/app/(dashboard)/journal/timeline";
import type { ObservationNote, PreTradeReflection } from "@/lib/types";

function reflection(
  id: number,
  partial: Partial<PreTradeReflection> = {},
): PreTradeReflection {
  // Only the id + timestamp fields matter to the merge; cast through unknown
  // so we do not have to stub every required field (same shape the sibling
  // journal-helpers test uses).
  return {
    id,
    intended_ticker: "AAPL",
    status: "ready",
    proceeded_at: null,
    cancelled_at: null,
    cooldown_started_at: null,
    rationale: "",
    ...partial,
  } as unknown as PreTradeReflection;
}

function note(
  id: number,
  createdAt: string,
  tickers: { ticker: string; name: string }[] = [],
): ObservationNote {
  return {
    id,
    body: "장 초반 거래량이 평소보다 두껍다.",
    tickers,
    tags: [],
    source: "journal",
    created_at: createdAt,
  };
}

describe("timestampMs", () => {
  it("reads a naive backend stamp as UTC", () => {
    expect(timestampMs("2026-05-03T00:00:00")).toBe(
      Date.parse("2026-05-03T00:00:00Z"),
    );
  });

  it("returns -Infinity for null, empty and unparseable input", () => {
    expect(timestampMs(null)).toBe(Number.NEGATIVE_INFINITY);
    expect(timestampMs(undefined)).toBe(Number.NEGATIVE_INFINITY);
    expect(timestampMs("")).toBe(Number.NEGATIVE_INFINITY);
    expect(timestampMs("not-a-date")).toBe(Number.NEGATIVE_INFINITY);
  });
});

describe("entryTimestamp", () => {
  it("prefers proceeded_at, then cancelled_at, then cooldown_started_at", () => {
    expect(
      entryTimestamp(
        reflection(1, {
          proceeded_at: "2026-05-03",
          cancelled_at: "2026-05-02",
          cooldown_started_at: "2026-05-01",
        }),
      ),
    ).toBe("2026-05-03");
    expect(entryTimestamp(reflection(2, { cooldown_started_at: "2026-05-01" }))).toBe(
      "2026-05-01",
    );
    expect(entryTimestamp(reflection(3))).toBeNull();
  });
});

describe("mergeTimeline", () => {
  it("interleaves both feeds newest-first", () => {
    const entries = mergeTimeline(
      [
        reflection(1, { proceeded_at: "2026-05-01T00:00:00Z" }),
        reflection(2, { proceeded_at: "2026-05-05T00:00:00Z" }),
      ],
      [note(10, "2026-05-03T00:00:00Z"), note(11, "2026-05-07T00:00:00Z")],
    );
    expect(entries.map((e) => e.id)).toEqual([
      "note:11",
      "reflection:2",
      "note:10",
      "reflection:1",
    ]);
    expect(entries.map((e) => e.kind)).toEqual([
      "note",
      "reflection",
      "note",
      "reflection",
    ]);
  });

  it("carries the source row through on each entry", () => {
    const [first] = mergeTimeline([], [note(10, "2026-05-03T00:00:00Z")]);
    expect(first.kind).toBe("note");
    if (first.kind === "note") expect(first.note.id).toBe(10);
  });

  it("tolerates empty, null and undefined inputs", () => {
    expect(mergeTimeline([], [])).toEqual([]);
    expect(mergeTimeline(null, null)).toEqual([]);
    expect(mergeTimeline(undefined, undefined)).toEqual([]);
    expect(mergeTimeline(undefined, [note(1, "2026-05-01T00:00:00Z")])).toHaveLength(
      1,
    );
    expect(mergeTimeline([reflection(1)], undefined)).toHaveLength(1);
  });

  it("keeps rows with unparseable or missing dates, at the bottom", () => {
    const entries = mergeTimeline(
      [reflection(1), reflection(2, { proceeded_at: "not-a-date" })],
      [note(10, "2026-05-03T00:00:00Z"), note(11, "")],
    );
    // Nothing dropped.
    expect(entries).toHaveLength(4);
    // The only dated row leads; the three undated ones follow in input order
    // (reflections before notes — the merge pushes reflections first).
    expect(entries.map((e) => e.id)).toEqual([
      "note:10",
      "reflection:1",
      "reflection:2",
      "note:11",
    ]);
  });

  it("is stable for identical timestamps", () => {
    const sameTs = "2026-05-03T00:00:00Z";
    const entries = mergeTimeline(
      [
        reflection(1, { proceeded_at: sameTs }),
        reflection(2, { proceeded_at: sameTs }),
      ],
      [note(10, sameTs), note(11, sameTs)],
    );
    expect(entries.map((e) => e.id)).toEqual([
      "reflection:1",
      "reflection:2",
      "note:10",
      "note:11",
    ]);
  });
});

describe("filterTimeline", () => {
  const entries = mergeTimeline(
    [reflection(1, { proceeded_at: "2026-05-01T00:00:00Z" })],
    [note(10, "2026-05-03T00:00:00Z"), note(11, "2026-05-07T00:00:00Z")],
  );

  it("returns everything for 'all'", () => {
    expect(filterTimeline(entries, "all")).toHaveLength(3);
  });

  it("narrows to one kind and keeps the order", () => {
    expect(filterTimeline(entries, "note").map((e) => e.id)).toEqual([
      "note:11",
      "note:10",
    ]);
    expect(filterTimeline(entries, "reflection").map((e) => e.id)).toEqual([
      "reflection:1",
    ]);
  });

  it("never mutates the input", () => {
    const copy = [...entries];
    filterTimeline(entries, "note");
    expect(entries).toEqual(copy);
  });
});

describe("recentNoteSummary", () => {
  const now = Date.parse("2026-05-10T00:00:00Z");

  it("counts notes and distinct tickers inside the trailing 7 days", () => {
    const summary = recentNoteSummary(
      [
        note(1, "2026-05-09T00:00:00Z", [{ ticker: "NVDA", name: "NVIDIA" }]),
        note(2, "2026-05-08T00:00:00Z", [{ ticker: "nvda", name: "NVIDIA" }]),
        note(3, "2026-05-05T00:00:00Z", [{ ticker: "005930", name: "삼성전자" }]),
        // Outside the window — 8 days old.
        note(4, "2026-05-01T00:00:00Z", [{ ticker: "AAPL", name: "Apple" }]),
      ],
      now,
    );
    expect(summary).toEqual({ notes: 3, tickers: 2 });
  });

  it("counts a market-wide note but adds no ticker", () => {
    expect(recentNoteSummary([note(1, "2026-05-09T00:00:00Z")], now)).toEqual({
      notes: 1,
      tickers: 0,
    });
  });

  it("excludes rows with a broken stamp and tolerates empty input", () => {
    expect(recentNoteSummary([note(1, "not-a-date")], now)).toEqual({
      notes: 0,
      tickers: 0,
    });
    expect(recentNoteSummary([], now)).toEqual({ notes: 0, tickers: 0 });
    expect(recentNoteSummary(undefined, now)).toEqual({ notes: 0, tickers: 0 });
  });
});
