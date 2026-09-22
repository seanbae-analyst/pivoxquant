/**
 * /journal timeline — pure merge/filter/count helpers.
 *
 * docs/design/observation-notes_2026-09-22.md §5 ("journal 타임라인 병합"):
 * the page shows ONE record, not two tabs. A 멈춤 기록 (pre-trade reflection)
 * and a 관찰 노트 (observation note) are different kinds of evidence — the
 * first is attached to a decision, the second is the front of the loop — so
 * every entry keeps its `kind` and the UI labels it (§9 리스크: "기록"의 희석).
 *
 * Everything here is pure and side-effect free: no SWR, no fetch, no Date.now()
 * unless it is handed in. That is the point — `page.tsx` renders it and
 * `__tests__/timeline.test.ts` pins the ordering rules.
 *
 * No score, no label, no judgement is computed here. Counts only.
 */

import { parseIsoUtc } from "@/lib/format";
import type { ObservationNote, PreTradeReflection } from "@/lib/types";

/* ────────────────────────────────────────────────────────────────────────
 * Timestamps
 * ────────────────────────────────────────────────────────────────────── */

/**
 * When a reflection entry was created — the proceeded/cancelled stamp, else
 * the cooldown start.
 *
 * Lives here rather than in `page.tsx` so the merge can read it without
 * importing a module that pulls in six mirrors, the weekly pulse and the
 * import inbox. `page.tsx` re-exports it, which is what
 * `__tests__/journal-helpers.test.ts` imports.
 */
export function entryTimestamp(r: PreTradeReflection): string | null {
  return r.proceeded_at ?? r.cancelled_at ?? r.cooldown_started_at ?? null;
}

/**
 * Epoch milliseconds for an ISO stamp, or `-Infinity` when it is missing or
 * unparseable.
 *
 * `-Infinity` (not 0, not NaN) is deliberate: a NaN would poison every
 * comparison in the sort, and 0 is a real instant (1970) that a genuine — if
 * absurd — backdated record could occupy. `-Infinity` sorts such an entry to
 * the bottom of a newest-first feed without ever dropping it, because a row
 * the user wrote must stay visible even when its stamp is broken.
 */
export function timestampMs(iso: string | null | undefined): number {
  const d = parseIsoUtc(iso ?? null);
  return d ? d.getTime() : Number.NEGATIVE_INFINITY;
}

/* ────────────────────────────────────────────────────────────────────────
 * Entries
 * ────────────────────────────────────────────────────────────────────── */

export type TimelineEntry =
  | {
      kind: "reflection";
      /** Epoch ms; `-Infinity` when the record carries no usable stamp. */
      ts: number;
      /** Stable React key — kind-prefixed so the two id spaces cannot collide. */
      id: string;
      reflection: PreTradeReflection;
    }
  | {
      kind: "note";
      ts: number;
      id: string;
      note: ObservationNote;
    };

export type TimelineKind = TimelineEntry["kind"];

/** Which chip is active above the feed. */
export type TimelineFilter = "all" | TimelineKind;

/**
 * Merge both feeds into one newest-first list.
 *
 * Tolerant by contract: either argument may be `undefined`/null (SWR's first
 * render), may be empty, and may contain rows whose timestamps do not parse.
 * Nothing is ever dropped.
 *
 * The sort is stable (ES2019 guarantees `Array.prototype.sort` is), so two
 * records written in the same second keep the order they arrived in —
 * reflections before notes, each feed internally in backend order. The
 * comparator avoids `b.ts - a.ts` because `-Infinity - -Infinity` is NaN,
 * which would make the ordering implementation-defined.
 */
export function mergeTimeline(
  reflections: readonly PreTradeReflection[] | null | undefined,
  notes: readonly ObservationNote[] | null | undefined,
): TimelineEntry[] {
  const entries: TimelineEntry[] = [];

  for (const r of reflections ?? []) {
    if (!r) continue;
    entries.push({
      kind: "reflection",
      ts: timestampMs(entryTimestamp(r)),
      id: `reflection:${r.id}`,
      reflection: r,
    });
  }

  for (const n of notes ?? []) {
    if (!n) continue;
    entries.push({
      kind: "note",
      ts: timestampMs(n.created_at),
      id: `note:${n.id}`,
      note: n,
    });
  }

  entries.sort((a, b) => {
    if (a.ts === b.ts) return 0;
    return b.ts > a.ts ? 1 : -1;
  });
  return entries;
}

/** Narrow a merged timeline to one kind. `"all"` returns the input as-is. */
export function filterTimeline(
  entries: readonly TimelineEntry[],
  filter: TimelineFilter,
): TimelineEntry[] {
  if (filter === "all") return [...entries];
  return entries.filter((e) => e.kind === filter);
}

/* ────────────────────────────────────────────────────────────────────────
 * Count line — "이번 주 관찰 노트 N개 · 종목 M개"
 * ────────────────────────────────────────────────────────────────────── */

/** 7 days in milliseconds. */
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export interface RecentNoteSummary {
  notes: number;
  tickers: number;
}

/**
 * How much the user recorded lately, counted client-side from the notes
 * already loaded.
 *
 * "이번 주" is read as the TRAILING 7 DAYS, not the ISO calendar week: a
 * calendar week resets the number to zero every Monday morning, which reads
 * as "you stopped writing" the moment the user has done nothing wrong. The
 * copy in `page.tsx` says 이번 주 for the same reason a 주간 reading always
 * does — the window is what this comment pins.
 *
 * Counts only. No rate, no streak, no score (§4-3: the behaviour score is
 * untouched by observation notes in v1). A note with zero tickers (a
 * market-wide note, §8 Q2) contributes to `notes` and not to `tickers`.
 */
export function recentNoteSummary(
  notes: readonly ObservationNote[] | null | undefined,
  now: number = Date.now(),
): RecentNoteSummary {
  const cutoff = now - WEEK_MS;
  const tickers = new Set<string>();
  let count = 0;
  for (const n of notes ?? []) {
    if (!n) continue;
    const ts = timestampMs(n.created_at);
    // `-Infinity` (broken stamp) falls outside the window rather than being
    // counted as "this week" — the count must not claim a date it lacks.
    if (!(ts >= cutoff && ts <= now)) continue;
    count += 1;
    for (const t of n.tickers ?? []) {
      const symbol = (t?.ticker ?? "").trim().toUpperCase();
      if (symbol) tickers.add(symbol);
    }
  }
  return { notes: count, tickers: tickers.size };
}
