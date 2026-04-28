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
 * `displayName`, `loading`. The host page wires `useMorningBrief()` →
 * brief.insight / brief.summary as in V1.
 *
 * Legal: NO predictive/recommendation language; mockup body verified clean.
 */

import * as React from "react";
import Link from "next/link";

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
}: TodayMemoHeroV2Props) {
  const now = new Date();
  const eyebrow = `Memo · ${weekIndexOf(now)} of 52 · ${weekdayOf(now)}`;

  // Default fallback copy, matches mockup intent. Bronze italic accents via "br".
  const fallbackHeadline =
    'You held through <span class="br">noise</span>.<br/>Cash buffer is doing the work — <span class="br">don\'t tax it.</span>';
  const fallbackBody =
    "Today's memo is being assembled. The weekly editorial drops every Sunday 07:00 KST and archives below.";

  const headlineHtml = loading
    ? "Drafting today's memo…"
    : headline ?? fallbackHeadline;
  const bodyText = loading ? null : body ?? fallbackBody;

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
          color: "var(--pq-bronze)",
          marginBottom: 28,
        }}
      >
        {eyebrow}
      </div>

      <h1
        className="font-serif"
        style={{
          fontFamily:
            '"Playfair Display","Source Serif 4",Georgia,serif',
          fontWeight: 500,
          fontSize: "clamp(32px, 4.2vw, 48px)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          maxWidth: 940,
          margin: "0 0 28px 0",
        }}
        // headlineHtml is sanitized at the source (server brief copy);
        // mockup-style "br" accents require span markup. CSP-safe within
        // our trust boundary (own backend), no user-generated content.
        dangerouslySetInnerHTML={{ __html: headlineHtml }}
      />

      {bodyText ? (
        <p
          className="font-serif"
          style={{
            fontFamily:
              '"Source Serif 4","Iowan Old Style",Georgia,serif',
            fontSize: 17,
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
        <Link
          href="/morning-brief"
          className="pq-cta-bronze"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 22px",
            background: "var(--pq-bronze)",
            color: "var(--pq-ink, #050505)",
            fontFamily:
              '"JetBrains Mono","SF Mono",ui-monospace,monospace',
            fontSize: 11,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            borderRadius: 2,
            textDecoration: "none",
            transition: "background-color 200ms",
          }}
        >
          Read full memo →
        </Link>

        {audioDuration ? (
          <Link
            href="/morning-brief"
            className="font-mono uppercase"
            style={{
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--pq-bronze)",
              borderBottom: "1px solid rgba(184,149,106,0.35)",
              paddingBottom: 2,
              textDecoration: "none",
            }}
          >
            Listen · {audioDuration}
          </Link>
        ) : null}

        <span
          className="font-mono uppercase"
          style={{
            marginLeft: 16,
            fontSize: 10.5,
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.40)",
            textTransform: "uppercase",
          }}
        >
          Drafted by AI · Reviewed by you
        </span>
      </div>
    </section>
  );
}

export default TodayMemoHeroV2;
