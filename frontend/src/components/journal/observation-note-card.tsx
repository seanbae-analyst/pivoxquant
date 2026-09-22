"use client";

/**
 * <ObservationNoteCard /> — one 관찰 노트 in the /journal timeline.
 *
 * docs/design/observation-notes_2026-09-22.md §5. The timeline mixes two
 * kinds of record, so this card always wears its kind label ("관찰 노트") —
 * an observation is the *front* of the loop and must stay visibly distinct
 * from a 멈춤 기록, which is evidence attached to a decision (§9 리스크).
 *
 * Read-only apart from delete. Notes are append-only by design (§8 Q1), so
 * there is no edit affordance; delete asks once inline rather than through a
 * browser `confirm()`, which would sit outside the v3 surface.
 *
 * Renders only what the user wrote — no score, no label, no judgement, and
 * no price. The body is shown with whitespace preserved because the user's
 * own line breaks are part of the record.
 */

import * as React from "react";
import { useLocale } from "@/lib/locale";
import { displayName, normalizeTicker, parseIsoUtc } from "@/lib/format";
import { relativeTime } from "@/lib/relative-time";
import { deleteObservationNote } from "@/lib/hooks";
import type { ObservationNote } from "@/lib/types";

/**
 * Absolute KST-rendered date for the inline metadata row.
 *
 * Deliberately a local copy of the same three lines in
 * `app/(dashboard)/journal/page.tsx` rather than an import: that module is a
 * page that pulls in six mirrors, the weekly pulse and the import inbox, and
 * a card should not drag the whole page into its graph. Both spellings use
 * `parseIsoUtc` (naive backend stamps read as UTC) and pin the zone to KST
 * so the date never rolls a day for a viewer outside Korea.
 */
export function noteAbsoluteDate(iso: string | null): string {
  const d = parseIsoUtc(iso);
  if (!d) return "";
  return d.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "Asia/Seoul",
  });
}

export interface ObservationNoteCardProps {
  note: ObservationNote;
  /** Called after the server confirms the delete, with the removed id. */
  onDeleted?: (id: number) => void;
  /** Tighter spacing for sidebar/modal hosts. */
  compact?: boolean;
}

export function ObservationNoteCard({
  note,
  onDeleted,
  compact = false,
}: ObservationNoteCardProps) {
  const { locale } = useLocale();
  const [confirming, setConfirming] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteObservationNote(note.id);
      onDeleted?.(note.id);
    } catch (err) {
      setConfirming(false);
      setError(
        err instanceof Error && err.message
          ? err.message
          : "노트를 지우지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setDeleting(false);
    }
  }

  return (
    <article
      data-testid="observation-note-card"
      className={compact ? "py-3" : "py-4"}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.16em",
            color: "var(--pq-bronze)",
          }}
        >
          관찰 노트
        </span>
        <span
          className="font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-ivory-faint)",
          }}
        >
          {relativeTime(note.created_at, locale)}
          <span className="opacity-70">
            {" · "}
            {noteAbsoluteDate(note.created_at)}
          </span>
        </span>
      </div>

      <p
        className="mt-2 font-serif leading-relaxed"
        style={{
          whiteSpace: "pre-wrap",
          fontSize: "var(--pq-text-body-sm)",
          color: "var(--pq-ivory)",
        }}
      >
        {note.body}
      </p>

      {note.tickers.length > 0 && (
        <ul className="mt-2 flex list-none flex-wrap gap-x-3 gap-y-1 p-0">
          {note.tickers.map((t) => (
            <li
              key={t.ticker}
              className="flex items-baseline gap-2"
              style={{ fontSize: "var(--pq-text-eyebrow)" }}
            >
              <span className="font-serif" style={{ color: "var(--pq-ivory-dim)" }}>
                {displayName(t.ticker, t.name)}
              </span>
              <span
                className="font-mono uppercase"
                style={{ letterSpacing: "0.12em", color: "var(--pq-bronze)" }}
              >
                {normalizeTicker(t.ticker)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {note.tags.length > 0 && (
        <ul className="mt-2 flex list-none flex-wrap gap-2 p-0">
          {note.tags.map((tag) => (
            <li
              key={tag}
              className="rounded-[2px] border border-[rgba(245,240,232,0.15)] px-2 py-0.5 font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: "var(--pq-ivory-dim)",
              }}
            >
              {tag}
            </li>
          ))}
        </ul>
      )}

      {error && (
        <p
          role="alert"
          className="mt-2 font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-negative)",
          }}
        >
          {error}
        </p>
      )}

      <div className="mt-2 flex items-center gap-2">
        {!confirming ? (
          <button
            type="button"
            onClick={() => {
              setError(null);
              setConfirming(true);
            }}
            className="pq-ink-btn-ghost px-3 text-pq-eyebrow uppercase tracking-[0.16em]"
          >
            삭제
          </button>
        ) : (
          <>
            <span
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: "var(--pq-ivory-dim)",
              }}
            >
              지우면 되돌릴 수 없습니다.
            </span>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              aria-disabled={deleting}
              className="pq-ink-btn-ghost px-3 text-pq-eyebrow uppercase tracking-[0.16em] disabled:cursor-not-allowed disabled:opacity-30"
            >
              {deleting ? "지우는 중" : "확인"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              disabled={deleting}
              className="pq-ink-btn-ghost px-3 text-pq-eyebrow uppercase tracking-[0.16em] disabled:cursor-not-allowed disabled:opacity-30"
            >
              취소
            </button>
          </>
        )}
      </div>
    </article>
  );
}

export default ObservationNoteCard;
