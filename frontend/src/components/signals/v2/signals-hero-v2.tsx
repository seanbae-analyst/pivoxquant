"use client";

/**
 * <SignalsHeroV2 /> — editorial hero for /signals v2.
 *
 * Source: design-mockups/signals-v2/SPEC.md §1.
 * 80/64 padding, no card border, hairline-bottom seal.
 * H1 Playfair 500 / 48px / 1.05 line. Bronze italic accents on
 * "observed" and "filtered". Inline counts use mono tabular.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. Static editorial copy.
 */

import * as React from "react";

interface Counts {
  positive: number;
  negative: number;
  neutral: number;
  symbols: number;
}

interface Props {
  eyebrow?: string;
  counts: Counts;
  loading?: boolean;
}

export function SignalsHeroV2({ eyebrow = "Signals · live", counts, loading = false }: Props) {
  return (
    <header
      style={{
        padding: "80px 0 64px",
        borderBottom: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
        marginBottom: 0,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: 12,
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
        The stream is{" "}
        <span
          style={{
            fontStyle: "italic",
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          observed
        </span>
        ,
        <br />
        not advised — {" "}
        <span
          style={{
            fontStyle: "italic",
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          filtered
        </span>{" "}
        to what you own.
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-lead)",
          lineHeight: 1.6,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          marginTop: 22,
        }}
      >
        {loading ? (
          <>Reading the tape — counting today&apos;s observations across your book.</>
        ) : (
          <>
            Today the system surfaced{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-positive, #dc2626)",
              }}
            >
              {counts.positive}
            </span>{" "}
            positive,{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-negative, #2563eb)",
              }}
            >
              {counts.negative}
            </span>{" "}
            negative, and{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "rgba(245,240,232,0.55)",
              }}
            >
              {counts.neutral}
            </span>{" "}
            neutral observations across{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              {counts.symbols}
            </span>{" "}
            symbols. None of these are instructions to trade.
          </>
        )}
      </p>
    </header>
  );
}
