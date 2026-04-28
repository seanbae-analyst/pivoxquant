"use client";

/**
 * <RiskHeroV2 /> — editorial hero for /risk v2.
 *
 * Mirrors the home-v2 / portfolio-v2 hero rhythm: 80px / 64px padding,
 * hairline-bottom seal, no border. H1 Playfair 500 / 48px with bronze
 * italic accents. Posture vocabulary is legal-safe (composed / attentive
 * / strained / breached) — observation language only, never action.
 */

import * as React from "react";

type Posture = "composed" | "attentive" | "strained" | "breached";

interface Props {
  eyebrow: string;
  posture: Posture;
  breachedCount: number;
  strainedCount: number;
  loudestSignal?: string | null;
  observedAtKst?: string | null;
}

const POSTURE_KR: Record<Posture, string> = {
  composed: "composed",
  attentive: "attentive",
  strained: "strained",
  breached: "breached",
};

export function RiskHeroV2({
  eyebrow,
  posture,
  breachedCount,
  strainedCount,
  loudestSignal,
  observedAtKst,
}: Props) {
  const observedClause = observedAtKst
    ? `Seven layers observed at ${observedAtKst}.`
    : "Seven layers observed at the latest market close.";

  const strainClause =
    breachedCount > 0
      ? `${breachedCount} layer${breachedCount === 1 ? "" : "s"} breached`
      : strainedCount > 0
        ? `${strainedCount} under strain, none breached`
        : "All layers within band, none breached";

  return (
    <section
      style={{
        padding: "80px 64px 64px",
        borderBottom: "1px solid var(--pq-hairline, rgba(245,240,232,0.08))",
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontFamily: 'var(--pq-font-mono,"JetBrains Mono",monospace)',
          fontSize: 10.5,
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
            'var(--pq-font-display,"Playfair Display","Source Serif 4",Georgia,serif)',
          fontWeight: 500,
          fontSize: 48,
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          maxWidth: 940,
          margin: "0 0 28px 0",
        }}
      >
        Risk{" "}
        <span
          style={{
            color: "var(--pq-bronze)",
            fontStyle: "italic",
          }}
        >
          board.
        </span>
      </h1>

      <p
        className="font-serif"
        style={{
          fontFamily:
            'var(--pq-font-serif,"Source Serif 4","Iowan Old Style",Georgia,serif)',
          fontSize: 17,
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          margin: "0 0 40px 0",
        }}
      >
        {observedClause.replace(
          "observed",
          "OBS_PLACEHOLDER",
        )
          .split("OBS_PLACEHOLDER")
          .flatMap((part, i, arr) =>
            i < arr.length - 1
              ? [
                  part,
                  <span
                    key={`obs-${i}`}
                    style={{
                      color: "var(--pq-bronze)",
                      fontStyle: "italic",
                    }}
                  >
                    observed
                  </span>,
                ]
              : [part],
          )}
        {" "}
        {strainClause}. Posture:{" "}
        <span
          style={{
            color: "var(--pq-bronze)",
            fontStyle: "italic",
          }}
        >
          {POSTURE_KR[posture]}.
        </span>
        {loudestSignal ? (
          <>
            {" "}
            {loudestSignal}
          </>
        ) : null}
      </p>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <a
          href="#defense-layers"
          className="font-mono uppercase"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 22px",
            background: "var(--pq-bronze)",
            color: "var(--pq-ink, #050505)",
            fontFamily: 'var(--pq-font-mono,"JetBrains Mono",monospace)',
            fontSize: 11,
            letterSpacing: "0.2em",
            borderRadius: 2,
            textDecoration: "none",
          }}
        >
          Open layers ↓
        </a>
        <span
          className="font-mono uppercase"
          style={{
            fontFamily: 'var(--pq-font-mono,"JetBrains Mono",monospace)',
            fontSize: 10.5,
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.40)",
          }}
        >
          Drafted by AI · Reviewed by you
        </span>
      </div>
    </section>
  );
}

export default RiskHeroV2;
