"use client";

/**
 * SidebarRecordCard — the record, visible from every dashboard page.
 *
 * 2026-09-13: the 240px rail carried five links and 70% empty ink below
 * them. What fills it is not more navigation but the one thing only this
 * product holds — the user's own pre-trade record, and in it the trades
 * that did not happen. Three facts, nothing else:
 *
 *   1. 30-day resolution of the pauses — 멈춤 / 진행 / 취소 counts, read
 *      from GET /api/behavior/friction-outcome?period=30d (the same
 *      service /journal renders in full; this is its one-line face).
 *   2. Seven-day rhythm — one dot per day, filled when a record exists.
 *      The beta's open question is "do Korean retail investors record at
 *      all"; this shows each user their own answer, daily.
 *   3. The last three records — name + date, linking to /journal. Headed
 *      "마지막 기록 N건" (2026-09-19): unheaded, sitting under the 7-day
 *      strip, a months-old entry read as one of the last seven days.
 *
 * Posture (identical to friction-outcome-mirror.tsx):
 *   - No score, grade, streak praise, or verdict. A cancelled count is
 *     shown BESIDE the proceeded count, never alone — alone it would read
 *     as "not buying is better", which the data cannot say.
 *   - No CTA in the empty state. A "start a record" button here would be a
 *     nudge toward a trade. The empty state stays calm.
 *   - Counts only. Labels are the product's own vocabulary (멈춤 / 진행 /
 *     취소), the words /journal already teaches.
 *
 * Data: reuses `usePreTradeJournal()` with its default limit so the SWR key
 * is the one /journal already holds — no second request for the feed.
 * `useFrictionOutcome("30d")` is a distinct key from the journal's all-time
 * read, by design (different window, both cached).
 *
 * Desktop only: the rail is `hidden md:block` in dashboard-layout.tsx, so
 * this never renders under the mobile bottom nav.
 */

import Link from "next/link";
import { useFrictionOutcome, usePreTradeJournal } from "@/lib/hooks";
import { displayName, parseIsoUtc } from "@/lib/format";
import type { FrictionOutcomeResponse, PreTradeReflection } from "@/lib/types";

/* ────────────────────────────────────────────────────────────────────────
 * Pure view-model — unit-testable without a DOM. Counts and strings only.
 * ────────────────────────────────────────────────────────────────────── */

export interface RecordCardRecent {
  id: number;
  /** Resolved company name, else the ticker. */
  name: string;
  /** "M.D" in Asia/Seoul, or "" when the row carries no timestamp. */
  date: string;
  status: PreTradeReflection["status"];
}

export interface RecordCardView {
  /** False → render the calm empty state. */
  hasAny: boolean;
  /** 30-day counts. Null when the outcome read is unavailable (404 / error). */
  counts: { started: number; proceeded: number; cancelled: number } | null;
  /** Seven entries, oldest → today. True when at least one record that day. */
  rhythm: boolean[];
  recent: RecordCardRecent[];
}

/** Proceeded / cancelled stamp else cooldown start — same rule as /journal. */
function entryTimestamp(r: PreTradeReflection): string | null {
  return r.proceeded_at ?? r.cancelled_at ?? r.cooldown_started_at ?? null;
}

/** Naive backend timestamps are UTC — shared guard, see lib/format parseIsoUtc. */
const parseIso = parseIsoUtc;

const SEOUL_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** "YYYY-MM-DD" in Asia/Seoul — pins the day so it never rolls for other zones. */
function seoulDayKey(d: Date): string {
  return SEOUL_DAY.format(d);
}

const SEOUL_SHORT = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  month: "numeric",
  day: "numeric",
});

/** "9.13" style — the rail is 240px, the long form would wrap. */
function shortDate(d: Date | null): string {
  if (!d) return "";
  // ko-KR numeric gives "9. 13." — collapse to "9.13".
  return SEOUL_SHORT.format(d).replace(/\s/g, "").replace(/\.$/, "");
}

export function buildRecordCardView(
  outcome: FrictionOutcomeResponse | null,
  reflections: PreTradeReflection[],
  now: Date = new Date(),
): RecordCardView {
  const counts =
    outcome && outcome.ok
      ? {
          started: outcome.stopped.started,
          proceeded: outcome.stopped.proceeded,
          cancelled: outcome.stopped.cancelled,
        }
      : null;

  // Seven Seoul-calendar days ending today. Build the keys from `now` so the
  // strip is deterministic under a fixed clock in tests.
  const dayKeys: string[] = [];
  for (let i = 6; i >= 0; i--) {
    dayKeys.push(seoulDayKey(new Date(now.getTime() - i * 86_400_000)));
  }
  const recorded = new Set<string>();
  for (const r of reflections) {
    const d = parseIso(entryTimestamp(r));
    if (d) recorded.add(seoulDayKey(d));
  }
  const rhythm = dayKeys.map((k) => recorded.has(k));

  const recent: RecordCardRecent[] = reflections.slice(0, 3).map((r) => ({
    id: r.id,
    name: displayName(r.intended_ticker, r.intended_name),
    date: shortDate(parseIso(entryTimestamp(r))),
    status: r.status,
  }));

  return {
    hasAny: reflections.length > 0 || (counts !== null && counts.started > 0),
    counts,
    rhythm,
    recent,
  };
}

/* ────────────────────────────────────────────────────────────────────── */

const STATUS_LABEL: Record<PreTradeReflection["status"], string> = {
  proceeded: "진행",
  cancelled: "취소",
  pending: "미결",
  ready: "미결",
};

export function SidebarRecordCard() {
  const outcome = useFrictionOutcome("30d");
  const journal = usePreTradeJournal();

  // One read failing must not take the rail down — soft-fail like the mirrors.
  if (outcome.error && journal.error) return null;

  if (outcome.isLoading && journal.isLoading) {
    return (
      <div className="px-6 pt-6" aria-busy="true">
        <div className="pq-skeleton-dark rounded-sm" style={{ height: 2, width: 96 }} />
      </div>
    );
  }

  const view = buildRecordCardView(outcome.data, journal.reflections);

  return (
    <section
      className="mx-3 mt-6 rounded-[2px] border px-4 pt-4 pb-4"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
      aria-label="기록"
    >
      {/* kicker — product vocabulary, bronze, same treatment as the group header */}
      <div className="flex items-baseline justify-between">
        <span
          className="font-serif uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "rgba(184, 149, 106, 0.78)",
          }}
        >
          기록
        </span>
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-kicker)",
            letterSpacing: "0.18em",
            color: "var(--pq-ivory-dim)",
          }}
        >
          30일
        </span>
      </div>

      {!view.hasAny ? (
        <p
          className="mt-3 font-serif"
          style={{
            fontSize: "var(--pq-text-body-sm)",
            lineHeight: 1.6,
            color: "var(--pq-ivory-dim)",
            wordBreak: "keep-all",
          }}
        >
          아직 기록이 없습니다. 사기 전에 남긴 기록이 여기에 쌓입니다.
        </p>
      ) : (
        <>
          {/* ── 30-day resolution: 멈춤 · 진행 · 취소 ─────────────────── */}
          {view.counts && (
            <dl className="mt-3 grid grid-cols-3 gap-2">
              <CountCell label="멈춤" value={view.counts.started} />
              <CountCell label="진행" value={view.counts.proceeded} />
              <CountCell label="취소" value={view.counts.cancelled} />
            </dl>
          )}

          {/* ── seven-day rhythm ──────────────────────────────────────── */}
          <div className="mt-4">
            <div className="flex items-center justify-between">
              <span
                className="font-sans uppercase"
                style={{
                  fontSize: "var(--pq-text-kicker)",
                  letterSpacing: "0.14em",
                  color: "var(--pq-ivory-dim)",
                }}
              >
                최근 7일
              </span>
              <span
                className="font-mono"
                style={{
                  fontSize: "var(--pq-text-kicker)",
                  color: "var(--pq-ivory-dim)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {view.rhythm.filter(Boolean).length}일 기록
              </span>
            </div>
            <ol
              className="mt-2 grid grid-cols-7 gap-1.5"
              aria-label="최근 7일 기록 여부"
            >
              {view.rhythm.map((on, i) => (
                <li
                  key={i}
                  className="h-1.5 rounded-full"
                  style={{
                    backgroundColor: on
                      ? "var(--pq-bronze)"
                      : "var(--pq-ivory-line)",
                  }}
                  aria-label={on ? "기록 있음" : "기록 없음"}
                />
              ))}
            </ol>
          </div>

          {/* ── last records — link into the journal ─────────────────────
               2026-09-19: this list had no visible heading, only an
               aria-label reading "최근 기록", and it sat directly under the
               "최근 7일 · N일 기록" strip. A record from three months ago
               therefore read as one of the last seven days, and the screen
               reader said something the eye could not see.

               Fixed with a visible heading rather than a date window: the
               list's documented job (see the file header, fact 3) is the
               three MOST RECENT records — windowing them to 7 days would
               blank the rail for exactly the users who record rarely, which
               is the beta's open question. The heading states the count and
               drops the word "최근", so it makes no claim about when. Adding
               a year to the date would not have helped either — the
               misread date (6.10) is in the current year. */}
          {view.recent.length > 0 && (
            <div
              className="mt-4 pt-3"
              style={{ borderTop: "0.5pt solid var(--pq-ivory-line)" }}
            >
              <h3
                id="pq-rail-last-records"
                className="font-sans uppercase"
                style={{
                  fontSize: "var(--pq-text-kicker)",
                  letterSpacing: "0.14em",
                  color: "var(--pq-ivory-dim)",
                  margin: 0,
                }}
              >
                마지막 기록 {view.recent.length}건
              </h3>
              <ul
                className="mt-2"
                aria-labelledby="pq-rail-last-records"
              >
                {view.recent.map((r) => (
                  <li key={r.id}>
                    <Link
                      href="/journal"
                      className="flex items-baseline justify-between gap-2 py-1 transition-colors hover:text-[var(--pq-ivory)]"
                      style={{ color: "rgba(245,240,232,0.72)" }}
                    >
                      <span
                        className="min-w-0 truncate font-serif"
                        style={{ fontSize: "var(--pq-text-body-sm)" }}
                      >
                        {r.name}
                      </span>
                      <span
                        className="shrink-0 font-mono"
                        style={{
                          fontSize: "var(--pq-text-kicker)",
                          color: "var(--pq-ivory-dim)",
                          fontVariantNumeric: "tabular-nums",
                          letterSpacing: "0.04em",
                        }}
                      >
                        {STATUS_LABEL[r.status]}
                        {r.date ? ` · ${r.date}` : ""}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function CountCell({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt
        className="font-sans uppercase"
        style={{
          fontSize: "var(--pq-text-kicker)",
          letterSpacing: "0.14em",
          color: "rgba(184, 149, 106, 0.78)",
        }}
      >
        {label}
      </dt>
      <dd
        className="mt-0.5 font-mono"
        style={{
          fontSize: "var(--pq-text-h6)",
          lineHeight: 1.1,
          color: "var(--pq-ivory)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </dd>
    </div>
  );
}
