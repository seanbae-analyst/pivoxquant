"use client";

/**
 * <RelatedObservationNotes /> — the user's own past observations, read back
 * on the way into the seven questions.
 *
 * docs/design/observation-notes_2026-09-22.md §4-1: this is the "관측 →
 * 성찰·기록" arrow of the product loop. Before answering the deposition the
 * user sees what they themselves wrote about this symbol over the last 30
 * days, in their own words, unedited.
 *
 * STRICTLY READ-ONLY. There is no composer here and no link to one (§5
 * 진입점, §9 리스크): a write affordance on this screen would turn the
 * observation note into a way around the seven questions, which is the one
 * thing this feature must never become. It renders text and nothing else —
 * no button, no anchor, no form.
 *
 * Renders nothing while loading, on error, and when the count is zero: an
 * empty block on the deposition would be noise, and a "0개" line reads as a
 * nudge to go write one, which is the affordance we just refused.
 *
 * No quote is read here — notes carry no price (§0 시세 전제).
 */

import { useLocale } from "@/lib/locale";
import { useObservationNotesByTicker } from "@/lib/hooks";
import { relativeTime } from "@/lib/relative-time";

/** How many excerpts are shown, however many the window holds. */
export const RELATED_NOTES_MAX_SHOWN = 3;
/** Excerpt budget in characters, before the ellipsis. */
export const RELATED_NOTES_EXCERPT_CHARS = 120;
/** Trailing window, in days. Matches the backend default. */
export const RELATED_NOTES_WINDOW_DAYS = 30;

/**
 * One line of the user's note: whitespace collapsed (their line breaks would
 * blow the compact block open) and cut to the excerpt budget. Pure — exported
 * for `__tests__/related-notes.test.tsx`.
 */
export function noteExcerpt(
  body: string,
  max: number = RELATED_NOTES_EXCERPT_CHARS,
): string {
  const flat = (body ?? "").replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  return `${flat.slice(0, max)}…`;
}

export interface RelatedObservationNotesProps {
  /** The symbol chosen in setup. Null/empty disables the fetch entirely. */
  ticker: string | null | undefined;
  /** Trailing window in days; the backend defaults to the same 30. */
  days?: number;
}

export function RelatedObservationNotes({
  ticker,
  days = RELATED_NOTES_WINDOW_DAYS,
}: RelatedObservationNotesProps) {
  const { locale } = useLocale();
  const symbol = (ticker ?? "").trim();
  const { notes, count, isLoading, error } = useObservationNotesByTicker(
    symbol ? symbol.toUpperCase() : null,
    days,
  );

  if (isLoading || error || count <= 0) return null;

  const shown = notes.slice(0, RELATED_NOTES_MAX_SHOWN);

  return (
    <section
      aria-label="이 종목에 대한 내 관찰 노트"
      data-testid="related-observation-notes"
      className="rounded-[2px] border px-4 py-3"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <p
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.16em",
          color: "var(--pq-bronze)",
        }}
      >
        이 종목에 대해 최근 {days}일 관찰 노트 {count}개
      </p>

      {shown.length > 0 && (
        <ul className="mt-2 list-none space-y-2 p-0">
          {shown.map((note) => (
            <li key={note.id}>
              <p
                className="font-serif"
                style={{
                  fontSize: "var(--pq-text-body-sm)",
                  lineHeight: 1.55,
                  color: "var(--pq-ivory-strong)",
                  wordBreak: "keep-all",
                }}
              >
                {noteExcerpt(note.body)}
              </p>
              <span
                className="font-mono"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  color: "var(--pq-ivory-faint)",
                }}
              >
                {relativeTime(note.created_at, locale)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default RelatedObservationNotes;
