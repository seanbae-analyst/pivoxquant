"use client";

/**
 * <ProfileHeroV2 />
 *
 * Editorial CFO hero for /profile v2.
 *
 * Visual rules per profile-v2 SPEC §1:
 * - Eyebrow: "Identity · Persona · Living CFO".
 * - H1 Playfair Display 500 / 48px / line-height 1.05 / track-tight, max-width 940.
 * - Bronze italic accent words via <span className="br">.
 * - Editorial body Source Serif 4, max-width 720px.
 * - CTA pair: bronze pill "Retake assessment →" + mono link "Export agent memory".
 * - Eyebrow signature: "Drafted by AI · Reviewed by you".
 *
 * Pure presentational. Caller supplies persona-name + drift state.
 *
 * Legal: no recommend/advice language; persona vocabulary only.
 */

import * as React from "react";
import Link from "next/link";

interface ProfileHeroV2Props {
  /** Observed persona display name (e.g. "Defensive Allocator"). */
  personaName?: string | null;
  /** Optional persona version label, e.g. "v3". */
  personaVersion?: string;
  /** Body sentence — editorial summary of last 90D behaviour vs declared. */
  body?: string | null;
  /** Click handler for "Export agent memory" link (host wires apiFetch). */
  onExport?: () => void;
}

export function ProfileHeroV2({
  personaName,
  personaVersion = "v3",
  body,
  onExport,
}: ProfileHeroV2Props) {
  const headlinePersona = personaName ?? "Observed persona";
  const fallbackBody =
    "Across the last 90 days your declared persona and your trades are in agreement. The classifier reads your behaviour, not your intention.";

  return (
    <section
      className="pq-profile-hero"
      style={{
        padding: "80px 0 48px",
        borderBottom: "1px solid var(--pq-ivory-line)",
        marginBottom: 40,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 28,
        }}
      >
        {/* 2026-09-01: was "Identity · Persona · Living CFO", which left the
            headline below unlabelled. `personaName` is the OBSERVED
            classification (see the prop doc), and a user whose declared
            assessment is still 미설정 read the hero as their declared type —
            collapsing the 선언 vs 관찰 distinction the whole product rests on.
            "관찰됨 · OBSERVED" is the same marker the journal mirrors use. */}
        관찰됨 · Observed persona · Living CFO
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "var(--pq-text-h2-dash)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          maxWidth: 940,
          margin: "0 0 28px 0",
        }}
      >
        Who you are, when the{" "}
        <span
          style={{
            color: "var(--pq-bronze)",
          }}
        >
          tape moves.
        </span>
        <br />
        {headlinePersona}{" "}
        <span
          style={{
            color: "var(--pq-bronze)",
          }}
        >
          · {personaVersion}.
        </span>
      </h1>

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
        {body ?? fallbackBody}
      </p>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <Link
          href="/onboarding"
          className="pq-cta-bronze font-mono"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 22px",
            background: "var(--pq-bronze)",
            color: "var(--pq-ink, #050505)",
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            borderRadius: 2,
            textDecoration: "none",
            transition: "background-color 200ms",
          }}
        >
          Retake assessment →
        </Link>

        {onExport ? (
          <button
            type="button"
            onClick={onExport}
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--pq-bronze)",
              borderBottom: "1px solid rgba(184,149,106,0.35)",
              paddingBottom: 2,
              background: "transparent",
              cursor: "pointer",
            }}
          >
            Export agent memory
          </button>
        ) : null}

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
      </div>
    </section>
  );
}

export default ProfileHeroV2;
