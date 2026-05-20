"use client";

/**
 * <TodayMemoHeroV2 />
 *
 * Editorial CFO hero for /home v2 (Direction B · Gallery).
 *
 * Visual rules per home-v2 SPEC §1:
 * - Padding 80px top / 64px bottom — no card border, only hairline-bottom seal.
 * - H1 Playfair Display 500 / 48px / line-height 1.05 / track-tight.
 * - Bronze italic accent words via <span className="br">.
 * - Editorial body Source Serif 4, max-width 720px.
 * - Two CTAs: bronze pill (Read full memo) + mono underline (Listen · 4:12).
 * - Eyebrow signature: "Drafted by AI · Reviewed by you".
 *
 * Data source: caller passes prepared `headline`, `body`, `audioDuration`,
 * `displayName`, `loading`. (Morning Brief data source deprecated 2026-04-29) →
 * brief.insight / brief.summary as in V1.
 *
 * Legal: NO predictive/recommendation language; mockup body verified clean.
 */

import * as React from "react";
import Link from "next/link";
import { renderEditorialHeadline } from "@/lib/editorial-html";
import { WEEKLY_MEMO_WHEN_SHORT } from "@/lib/cfo/memo-schedule";

interface TodayMemoHeroV2Props {
  /** H1 line. May contain <span class="br">…</span> markup, rendered as-is. */
  headline: string | null;
  /** Optional editorial body paragraph. */
  body?: string | null;
  /** Optional audio duration label, e.g. "4:12". */
  audioDuration?: string | null;
  /** Greeting / first-name display, used in the eyebrow seal. */
  displayName?: string;
  /** SWR loading flag. */
  loading?: boolean;
  /**
   * P0-2: when the user has zero positions, the hero shows a first-run
   * activation CTA ("Add your first position") instead of the "Read full
   * memo" link, which would dead-end in an empty archive. The page passes
   * this once positions SWR resolves.
   */
  hasPositions?: boolean;
}

function weekIndexOf(d: Date): number {
  // ISO-ish week number (Mon-start). Acceptable for editorial display.
  const yearStart = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - yearStart.getTime()) / 86_400_000);
  return Math.min(52, Math.max(1, Math.ceil((days + yearStart.getDay() + 1) / 7)));
}

function weekdayOf(d: Date): string {
  return d.toLocaleDateString("en-US", { weekday: "long" });
}

export function TodayMemoHeroV2({
  headline,
  body,
  audioDuration,
  loading,
  hasPositions = true,
}: TodayMemoHeroV2Props) {
  const now = new Date();

  // P0-1 (2026-05-20 ux-flow fix): the previous build hard-coded a fake CFO
  // insight ("You held through noise. Cash buffer is doing the work…") as the
  // fallback headline AND always rendered the "Drafted by AI · Reviewed by
  // you" seal — so EVERY user (incl. brand-new accounts with zero data) saw a
  // fabricated personal memo signed as if a real analysis ran. Trust killer.
  //
  // Now three explicit states:
  //   - loading      → neutral "drafting" placeholder, no seal
  //   - empty        → honest "first memo is on its way" copy, no seal,
  //                    no insight sentence
  //   - real memo    → caller-fed headline/body + the AI/reviewed seal
  const hasRealMemo = !loading && headline != null;

  const eyebrow = hasRealMemo
    ? `Memo · ${weekIndexOf(now)} of 52 · ${weekdayOf(now)}`
    : "Memo · Coming soon";

  // Empty-state copy: NO fabricated insight, NO predictive language. Plain
  // ivory text (no bronze "br" accent — that styling is reserved for a real
  // editorial line).
  const emptyHeadline = "Your first weekly memo is on its way.";
  const emptyBody = `Once you have a position on the book, your CFO drafts a weekly editorial — what moved, what held, and where the risk sits. It lands ${WEEKLY_MEMO_WHEN_SHORT} and archives below.`;

  const headlineHtml = loading
    ? "Drafting today's memo…"
    : hasRealMemo
      ? (headline as string)
      : emptyHeadline;
  const bodyText = loading
    ? null
    : hasRealMemo
      ? body ?? null
      : emptyBody;

  return (
    <section
      className="pq-hero-v2"
      style={{
        padding: "80px 0 64px",
        borderBottom: "1px solid var(--pq-hairline-ink)",
        marginBottom: 40,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow, 10.5px)",
          letterSpacing: "0.22em",
          color: "rgba(245, 240, 232, 0.6)",
          marginBottom: 28,
        }}
      >
        {eyebrow}
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(32px, 4.2vw, 48px)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          maxWidth: 940,
          margin: "0 0 28px 0",
        }}
      >
        {/* Strict tag allowlist (<br/>, <span class="br">) — see
            lib/editorial-html. Replaces dangerouslySetInnerHTML so any
            future server-fed headline can't smuggle scripts. */}
        {renderEditorialHeadline(headlineHtml)}
      </h1>

      {bodyText ? (
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-h5)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.82)",
            maxWidth: 720,
            margin: "0 0 40px 0",
          }}
        >
          {bodyText}
        </p>
      ) : (
        <div style={{ height: 28, marginBottom: 40 }} aria-hidden />
      )}

      <div
        className="flex items-center"
        style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}
      >
        {/* P0-2: first-run activation. Zero positions → the only sensible
            next step is adding one, so the primary bronze CTA points to the
            Book instead of an empty memo archive. */}
        {!loading && !hasPositions ? (
          <Link
            href="/portfolio"
            className="pq-cta-bronze font-mono"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 22px",
              background: "var(--pq-bronze)" /* SOLE Accent Gold per design-principles-cfo.md §2 — do not duplicate */,
              color: "var(--pq-ink, #050505)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              borderRadius: 2,
              textDecoration: "none",
              transition: "background-color 200ms",
            }}
          >
            Add your first position →
          </Link>
        ) : hasRealMemo ? (
          <Link
            href="/reports"
            className="pq-cta-bronze font-mono"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 22px",
              background: "var(--pq-bronze)" /* SOLE Accent Gold per design-principles-cfo.md §2 — do not duplicate */,
              color: "var(--pq-ink, #050505)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              borderRadius: 2,
              textDecoration: "none",
              transition: "background-color 200ms",
            }}
          >
            Read full memo →
          </Link>
        ) : (
          /* Has positions but no memo yet → quiet link to the (real) archive
             rather than a primary CTA that implies a memo is ready. */
          <Link
            href="/reports"
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "rgba(245, 240, 232, 0.6)",
              borderBottom: "1px solid rgba(184,149,106,0.35)",
              paddingBottom: 2,
              textDecoration: "none",
            }}
          >
            Browse the archive →
          </Link>
        )}

        {hasRealMemo && audioDuration ? (
          <Link
            href="/reports"
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "rgba(245, 240, 232, 0.6)",
              borderBottom: "1px solid rgba(184,149,106,0.35)",
              paddingBottom: 2,
              textDecoration: "none",
            }}
          >
            Listen · {audioDuration}
          </Link>
        ) : null}

        {/* P0-1: the "Drafted by AI · Reviewed by you" seal only appears on a
            REAL memo. Showing it over empty/placeholder copy was the original
            trust bug (it signed a memo that never ran). */}
        {hasRealMemo ? (
          <span
            className="font-mono uppercase"
            style={{
              marginLeft: 16,
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.55)",
              textTransform: "uppercase",
            }}
          >
            Drafted by AI · Reviewed by you
          </span>
        ) : null}
      </div>
    </section>
  );
}

export default TodayMemoHeroV2;
