"use client";

/**
 * <SixDimensionsGrid />
 *
 * Block 4 of /profile v2 — six dimensions (2×3 grid).
 * Mirror of profile-v2 mockup §506 ("04 · The six dimensions").
 *
 * Renders 6 cards (one per dimension), each with:
 *   - corner number (01-06, mono)
 *   - dim-name (Playfair 17px)
 *   - editorial dim-quote (Source Serif 12.5px italic)
 *   - mono score "x.x / 10" right-aligned
 *   - 4px gauge bar (bronze-deep → bronze gradient)
 *
 * Pure presentational. Caller supplies dimensions array and section header.
 *
 * Legal: persona vocabulary only. No advice/recommend strings.
 */

import * as React from "react";

export interface DimensionEntry {
  /** Dimension display name, e.g. "Risk tolerance". */
  name: string;
  /** Editorial single-sentence reflection, AI-drafted. */
  quote: string;
  /** Score on 0–10 scale. */
  score: number;
}

const DEFAULT_DIMS: DimensionEntry[] = [
  {
    name: "Risk tolerance",
    quote:
      "You sized down twice in February before VIX spiked. Tail-aware, not tail-chasing.",
    score: 7.2,
  },
  {
    name: "Time horizon",
    quote:
      "Median holding period 47 days. Top decile of your peer cohort by patience.",
    score: 8.1,
  },
  {
    name: "Diversification",
    quote:
      "Twelve open names across six sectors. Concentration ratio 41% in Tech — flagged.",
    score: 6.4,
  },
  {
    name: "Sector lean",
    quote:
      "Tech-heavy with a defensive tilt: AAPL, MSFT, 005930.KS as anchors.",
    score: 7.0,
  },
  {
    name: "Behavioral pattern",
    quote:
      "No disposition effect detected. You let winners run; you cut losers within 2σ moves.",
    score: 8.6,
  },
  {
    name: "Reaction style",
    quote:
      "Slower than median peer to chase post-earnings moves. Reads the second day.",
    score: 7.4,
  },
];

interface Props {
  /** 6 dimensions. Falls back to editorial defaults when omitted. */
  dimensions?: DimensionEntry[];
  /** Section eyebrow + title visible above the grid. */
  showHeader?: boolean;
  /** Methodology link href; rendered in the section header when shown. */
  methodologyHref?: string;
}

export function SixDimensionsGrid({
  dimensions,
  showHeader = true,
  /* /methodology was a stub that 404s. Point at /docs (which carries the
     Signals & Risk methodology section) until a dedicated methodology
     page is shipped. Bug-hunter 2026-05-05 HIGH finding. */
  methodologyHref = "/docs",
}: Props) {
  const list = dimensions && dimensions.length === 6 ? dimensions : DEFAULT_DIMS;

  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(12, minmax(0, 1fr))",
        gap: 12,
        marginBottom: 48,
      }}
      aria-label="Six dimensions of observed persona"
    >
      {showHeader ? (
        <div
          style={{
            gridColumn: "span 12",
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            marginBottom: 12,
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>
            <div
              className="font-mono uppercase"
              style={{
                fontSize: 10.5,
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
                marginBottom: 8,
              }}
            >
              04 · The six dimensions
            </div>
            <div
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: 30,
                lineHeight: 1.15,
                letterSpacing: "-0.02em",
                color: "var(--pq-ivory)",
              }}
            >
              What the persona is made of.
            </div>
          </div>
          <a
            href={methodologyHref}
            className="font-mono uppercase"
            style={{
              fontSize: 11,
              letterSpacing: "0.18em",
              color: "var(--pq-bronze)",
              borderBottom: "1px solid rgba(184,149,106,0.15)",
              paddingBottom: 2,
              textDecoration: "none",
            }}
          >
            Methodology ›
          </a>
        </div>
      ) : null}

      {list.map((dim, idx) => {
        const widthPct = Math.min(100, Math.max(0, dim.score * 10));
        const corner = String(idx + 1).padStart(2, "0");
        return (
          <div
            key={dim.name}
            style={{
              gridColumn: "span 6",
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(245,240,232,0.08)",
              borderRadius: 4,
              padding: 24,
              position: "relative",
            }}
          >
            <span
              className="font-mono uppercase"
              style={{
                position: "absolute",
                top: 14,
                right: 14,
                fontSize: 9.5,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.40)",
              }}
            >
              {corner}
            </span>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 14,
                alignItems: "baseline",
              }}
            >
              <div>
                <div
                  className="font-display"
                  style={{
                    fontWeight: 500,
                    fontSize: 17,
                    color: "var(--pq-ivory)",
                  }}
                >
                  {dim.name}
                </div>
                <p
                  className="font-serif"
                  style={{
                    fontSize: 12.5,
                    lineHeight: 1.5,
                    color: "rgba(245,240,232,0.55)",
                    marginTop: 4,
                  }}
                >
                  {`"${dim.quote}"`}
                </p>
              </div>
              <div
                className="font-mono"
                style={{
                  fontVariantNumeric: "tabular-nums",
                  fontSize: 13.5,
                  color: "var(--pq-bronze)",
                  whiteSpace: "nowrap",
                }}
                aria-label={`${dim.name}: ${dim.score.toFixed(1)} of 10`}
              >
                {dim.score.toFixed(1)} / 10
              </div>
            </div>

            <div
              style={{
                marginTop: 16,
                height: 4,
                background: "rgba(245,240,232,0.06)",
                position: "relative",
                overflow: "hidden",
              }}
            >
              <i
                style={{
                  display: "block",
                  height: "100%",
                  width: `${widthPct}%`,
                  background:
                    "linear-gradient(90deg, var(--pq-bronze-deep, #6F5636), var(--pq-bronze, #B8956A))",
                }}
              />
            </div>
          </div>
        );
      })}
    </section>
  );
}

export default SixDimensionsGrid;
