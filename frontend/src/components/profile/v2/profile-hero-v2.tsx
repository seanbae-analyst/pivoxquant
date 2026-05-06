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
        borderBottom: "1px solid rgba(245,240,232,0.08)",
        marginBottom: 40,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: 10.5,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 28,
        }}
      >
        Identity · Persona · Living CFO
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
        Who you are, when the{" "}
        <span
          style={{
            color: "var(--pq-bronze)",
            fontStyle: "italic",
          }}
        >
          tape moves.
        </span>
        <br />
        {headlinePersona}{" "}
        <span
          style={{
            color: "var(--pq-bronze)",
            fontStyle: "italic",
          }}
        >
          · {personaVersion}.
        </span>
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: 17,
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
            fontSize: 11,
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
              fontSize: 11,
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

export default ProfileHeroV2;
