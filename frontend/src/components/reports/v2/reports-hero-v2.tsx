"use client";

/**
 * <ReportsHeroV2 /> — editorial hero for /reports v2 ("CFO Archive").
 *
 * Source: design-mockups/reports-v2/SPEC.md §1.
 * 80/64 padding, hairline-bottom seal, no card border.
 * H1 Playfair 500 / 48px / 1.05 line. Bronze italic accents on
 * "published" and "artifacts". Inline counts use mono tabular.
 *
 * Legal: pure editorial copy. No banned vocabulary.
 */

import * as React from "react";

interface Counts {
  memos: number;
  briefs: number;
  bragCards: number;
}

interface Props {
  eyebrow?: string;
  counts: Counts;
  loading?: boolean;
}

export function ReportsHeroV2({
  eyebrow = "Archive · CFO",
  counts,
  loading = false,
}: Props) {
  return (
    <header
      style={{
        padding: "80px 0 64px",
        borderBottom: "1px solid var(--pq-hairline, rgba(245,240,232,0.08))",
        marginBottom: 0,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: 10.5,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze, #B8956A)",
          marginBottom: 14,
        }}
      >
        {eyebrow}
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(34px, 5vw, 48px)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory, #F5F0E8)",
          margin: 0,
          maxWidth: 880,
        }}
      >
        Everything we&apos;ve{" "}
        <span
          style={{
            fontStyle: "italic",
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          published
        </span>
        ,
        <br />
        kept as quiet{" "}
        <span
          style={{
            fontStyle: "italic",
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          artifacts
        </span>
        .
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: 15,
          lineHeight: 1.6,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          marginTop: 22,
        }}
      >
        {loading ? (
          <>Indexing the library — counting every memo and brief on the shelf.</>
        ) : (
          <>
            On the shelf this year:{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              {counts.memos}
            </span>{" "}
            memos,{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              {counts.briefs}
            </span>{" "}
            pre-briefs, and{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              {counts.bragCards}
            </span>{" "}
            brag cards. Drafted by AI, reviewed by you. None of it is
            instruction to trade.
          </>
        )}
      </p>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: 10,
          letterSpacing: "0.22em",
          color: "rgba(245,240,232,0.45)",
          marginTop: 18,
        }}
      >
        Drafted by AI · Reviewed by you
      </div>
    </header>
  );
}

export default ReportsHeroV2;
