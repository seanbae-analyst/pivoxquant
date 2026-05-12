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

interface Props {
  /**
   * Up to 6 dimensions sourced from the backend persona breakdown.
   * When omitted, null, or empty, the grid renders an empty-state
   * placeholder instead of fabricated sample numbers.
   * Bug-hunter 2026-05-07: removed editorial DEFAULT_DIMS fallback —
   * was leaking fake AAPL/MSFT/005930.KS anchors + invented scores
   * to every signed-in user (CEO escalation NEW-A).
   */
  dimensions?: DimensionEntry[] | null;
  /** Section eyebrow + title visible above the grid. */
  showHeader?: boolean;
  /** Methodology link href; rendered in the section header when shown. */
  methodologyHref?: string;
  /** True while the upstream hook is loading — show skeleton copy. */
  loading?: boolean;
}

export function SixDimensionsGrid({
  dimensions,
  showHeader = true,
  /* /methodology was a stub that 404s. Point at /docs (which carries the
     Signals & Risk methodology section) until a dedicated methodology
     page is shipped. Bug-hunter 2026-05-05 HIGH finding. */
  methodologyHref = "/docs",
  loading = false,
}: Props) {
  const list = dimensions && dimensions.length > 0 ? dimensions.slice(0, 6) : null;

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
                fontSize: 12,
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
                fontSize: 32,
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
              fontSize: 12,
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

      {!list ? (
        <div
          style={{
            gridColumn: "span 12",
            background: "rgba(255,255,255,0.02)",
            border: "1px dashed rgba(245,240,232,0.14)",
            borderRadius: 4,
            padding: 32,
            textAlign: "center",
          }}
          role="status"
          aria-live="polite"
        >
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-micro)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 10,
            }}
          >
            {loading ? "Loading…" : "Awaiting data"}
          </div>
          <p
            className="font-serif"
            style={{
              fontSize: 14,
              lineHeight: 1.55,
              color: "rgba(245,240,232,0.55)",
              maxWidth: 520,
              margin: "0 auto",
            }}
          >
            {loading
              ? "Computing your six-dimension persona breakdown…"
              : "거래 기록이 누적되면 6개 차원으로 본인의 페르소나가 표시됩니다. Six-dimension persona surfaces here once your trade history accumulates."}
          </p>
        </div>
      ) : null}

      {list?.map((dim, idx) => {
        const widthPct = Math.min(100, Math.max(0, dim.score * 10));
        const corner = String(idx + 1).padStart(2, "0");
        return (
          <div
            key={dim.name}
            style={{
              gridColumn: "span 6",
              background: "rgba(255,255,255,0.02)",
              border: "1px solid var(--pq-ivory-line)",
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
                fontSize: 12,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.55)",
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
                    fontSize: 18,
                    color: "var(--pq-ivory)",
                  }}
                >
                  {dim.name}
                </div>
                <p
                  className="font-serif"
                  style={{
                    fontSize: 14,
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
                  fontSize: 14,
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
                background: "var(--pq-ivory-line-soft)",
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
