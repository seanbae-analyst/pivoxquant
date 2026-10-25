"use client";

/**
 * <RelatedResearch /> — the user's own research on this symbol, read back on
 * the way into the seven questions.
 *
 * docs/design/research-notes_2026-10-15.md §4. Q1 (이유) and Q2 (틀린 선)
 * overlap with what the research form already holds; showing the cold
 * version here means the hot moment of buying meets what the user wrote
 * before it, in their own words.
 *
 * STRICTLY READ-ONLY, like <RelatedObservationNotes />: no form, no link to
 * one. A write affordance on the 멈춤 screen would become a way around the
 * seven questions. Renders nothing while loading, on error, or when there is
 * no research on this symbol (an empty block would read as a nudge).
 */
import { useResearchByTicker } from "@/lib/hooks";
import { kstDateOf, researchDate } from "@/lib/research";

export function RelatedResearch({ ticker }: { ticker: string | null | undefined }) {
  const symbol = (ticker ?? "").trim();
  const { note, count, isLoading } = useResearchByTicker(symbol ? symbol.toUpperCase() : null);
  if (isLoading || !note) return null;

  return (
    <section
      aria-label="이 종목에 대한 내 리서치"
      data-testid="related-research"
      className="rounded-[var(--pq-radius-card)] border px-4 py-3"
      style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
    >
      <p style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--pq-bronze)" }}>
        {researchDate(kstDateOf(note.created_at))}에 쓴 내 리서치{count > 1 ? ` (${count}개 중 최근)` : ""}
      </p>
      <dl className="mt-2 space-y-1.5" style={{ fontSize: "var(--pq-text-body-sm)", lineHeight: 1.55 }}>
        <div>
          <dt className="sr-only">이유</dt>
          <dd className="m-0" style={{ color: "var(--pq-ivory-strong)", wordBreak: "keep-all" }}>
            {note.theses.map((t, i) => (
              <span key={i} className="block">
                · {t}
              </span>
            ))}
          </dd>
        </div>
        {note.invalidation && (
          <div>
            <dt className="inline" style={{ color: "var(--pq-ivory-faint)" }}>
              틀렸다고 볼 신호 ·{" "}
            </dt>
            <dd className="inline m-0" style={{ color: "var(--pq-ivory-strong)" }}>
              {note.invalidation}
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}

export default RelatedResearch;
