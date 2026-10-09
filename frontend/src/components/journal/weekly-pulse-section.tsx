"use client";

/**
 * <WeeklyPulseSection /> — the weekly pulse, on the record page.
 *
 * Moved from /profile on 2026-09-12 (profile decomposition, decided
 * 2026-09-10). A pulse is something the user writes about themselves, so it
 * sits with the rest of what they wrote. Behaviour is unchanged: the three
 * most recent answers, then the inline <WeeklyPulseCard /> form and its
 * mood / confidence history.
 *
 * The copy describes what the form actually asks — five fields. The old
 * /profile copy said "One question, every Monday at 07:00 KST"; the form has
 * five fields and the inline card runs on no schedule.
 *
 * This is the pulse's ONLY input surface (2026-09-29). /portfolio shows a
 * Monday-only link here (<WeeklyPulsePrompt />, `/journal#weekly-pulse`)
 * instead of its old auto-opening modal copy of the same form.
 *
 * Legal: self-reported sentiment only, not investment advice. Mood bands
 * render as 차분 / 보통 / 방어적 / 신중 (Korean since 2026-10-07, CEO "영문
 * 라벨도 한글로") — never the literal "HOLD" token (CEO + legal 2026-04-28).
 */

import * as React from "react";

import { usePulse } from "@/lib/cfo/hooks";
import { parseUtcSafe } from "@/lib/relative-time";
import { RuledKicker, EditorialHead, Caption } from "@/components/ui/editorial";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";

/**
 * Posture mapping for pulse history rows. The backend may still emit `hold`
 * as a posture key — the UI label renders the same as `steady`.
 */
const POSTURE_LABEL: Record<string, string> = {
  calm: "차분",
  protective: "방어적",
  steady: "보통",
  hold: "보통", // ← never the "HOLD" token (legal, 2026-04-28)
  wait: "기다림",
  cautious: "신중",
};

interface PulseHistoryRow {
  date: string;
  question: string;
  posture: string;
}

/** `PulseEntry` carries a 1..5 mood, not a posture — band it. */
function moodToPosture(mood: number | undefined): string {
  if (typeof mood !== "number") return "steady";
  if (mood >= 4) return "calm";
  if (mood >= 3) return "steady";
  if (mood >= 2) return "protective";
  return "cautious";
}

function PulseRow({ row }: { row: PulseHistoryRow }) {
  const label = POSTURE_LABEL[row.posture.toLowerCase()] ?? row.posture;
  return (
    <div
      role="listitem"
      style={{
        display: "grid",
        gridTemplateColumns: "64px 1fr auto",
        gap: 14,
        alignItems: "baseline",
        padding: "10px 0",
        borderBottom: "1px solid var(--pq-ivory-line)",
      }}
    >
      <span
        className="font-mono"
        style={{
          fontVariantNumeric: "tabular-nums",
          fontSize: "var(--pq-text-eyebrow)",
          color: "var(--pq-bronze)",
        }}
      >
        {row.date}
      </span>
      <span
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          color: "var(--pq-ivory-strong)",
        }}
      >
        &ldquo;{row.question}&rdquo;
      </span>
      <span
        className="font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          color: "var(--pq-bronze)",
        }}
      >
        {label}
      </span>
    </div>
  );
}

export function WeeklyPulseSection() {
  const { data: pulse } = usePulse();
  const sectionRef = React.useRef<HTMLElement>(null);

  // Arriving from /portfolio's Monday link (`/journal#weekly-pulse`): the
  // dashboard layout mounts this page after auth resolves and the feed above
  // grows as it loads, so the router's own hash scroll can land short. Scroll
  // once more after the first paint settles.
  React.useEffect(() => {
    if (window.location.hash !== "#weekly-pulse") return;
    // The window is scrolled by hand rather than with scrollIntoView: on a
    // phone this section sits inside the journal's horizontal page track
    // (journal-pager.tsx), and Chromium drops the scroll-margin for the outer
    // scroller there, parking the heading under the sticky tab strip.
    const id = window.setTimeout(() => {
      const el = sectionRef.current;
      if (!el) return;
      const margin = parseFloat(getComputedStyle(el).scrollMarginTop) || 0;
      window.scrollTo({
        top: el.getBoundingClientRect().top + window.scrollY - margin,
      });
    }, 400);
    return () => window.clearTimeout(id);
  }, []);

  // The 3 most recent submissions, newest first. An empty history renders as
  // empty — never as sample rows (see lib/cfo/hooks.ts, 2026-09-06).
  const rows: PulseHistoryRow[] =
    pulse?.history && pulse.history.length > 0
      ? pulse.history
          .slice(-3)
          .reverse()
          .map((p) => ({
            date: p.submitted_at
              ? new Date(parseUtcSafe(p.submitted_at)).toLocaleDateString(
                  "ko-KR",
                  { month: "long", day: "numeric", timeZone: "Asia/Seoul" },
                )
              : "—",
            question: p.worry?.trim() ? p.worry : "주간 회고.",
            posture: moodToPosture(p.mood),
          }))
      : [];

  return (
    <section
      ref={sectionRef}
      id="weekly-pulse"
      aria-label="주간 회고"
      style={{ scrollMarginTop: "calc(var(--pq-aux-sticky-top, 56px) + 16px)" }}
    >
      <RuledKicker>주간 회고</RuledKicker>
      <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
        이번 주를 스스로 적어 두기
      </EditorialHead>
      <Caption className="mt-2 max-w-lg">
        투자 기분과 자신감(1–5), 마음에 걸리는 것 하나, 지켜보는 주제, 배우고
        싶은 것 — 다섯 칸입니다. 남긴 답은 여기에 쌓입니다.
      </Caption>

      <div role="list" aria-label="최근 회고" className="mt-5">
        {rows.length === 0 ? (
          <p className="font-serif text-pq-body-sm text-[var(--pq-ivory-dim)]">
            아직 남긴 회고가 없습니다.
          </p>
        ) : (
          rows.map((r, i) => <PulseRow key={`${r.date}-${i}`} row={r} />)
        )}
      </div>

      <div style={{ marginTop: 20 }}>
        <WeeklyPulseCard />
      </div>
    </section>
  );
}

export default WeeklyPulseSection;
