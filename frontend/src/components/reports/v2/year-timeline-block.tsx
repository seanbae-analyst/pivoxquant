"use client";

/**
 * <YearTimelineBlock /> — rolling 12-month archive list. Each row:
 *   [Month abbrev] [Year mono] [Titles preview] [Count]
 *
 * 종목명 main pattern at the month/year pair: Playfair month name on top,
 * mono dim "YYYY" beneath. Whole row is an `<a>` to `?month=YYYY-MM`.
 *
 * Source: design-mockups/reports-v2/SPEC.md §5.
 */

import * as React from "react";
import Link from "next/link";
import type { Artifact } from "@/lib/types";
import { deriveArchiveMonths } from "@/lib/hooks";

const MONTH_ABBREV = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

interface Props {
  artifacts: Artifact[];
  loading?: boolean;
}

export function YearTimelineBlock({ artifacts, loading }: Props) {
  const months = React.useMemo(
    () => deriveArchiveMonths(artifacts, 12),
    [artifacts],
  );

  return (
    <section
      aria-labelledby="year-heading"
      style={{ marginTop: "clamp(48px, 8vw, 80px)", paddingBottom: 24 }}
    >
      <h2
        id="year-heading"
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(26px, 3.4vw, 40px)",
          lineHeight: 1.1,
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "0 0 24px",
        }}
      >
        The year, briefly.
      </h2>

      {loading ? (
        <div
          className="animate-pulse"
          style={{
            height: 320,
            border:
              "1px solid var(--pq-hairline, var(--pq-ivory-line))",
            borderRadius: 4,
            background: "rgba(255,255,255,0.02)",
          }}
          aria-label="Loading year timeline"
        />
      ) : (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
            borderRadius: 4,
          }}
        >
          {months.map((m, idx) => {
            const [year, mm] = m.month.split("-");
            const monthIdx = parseInt(mm, 10) - 1;
            const monthAbbrev = MONTH_ABBREV[monthIdx] ?? "—";
            const titlesPreview = m.artifacts
              .slice(0, 3)
              .map((a) => a.title)
              .join(" · ");

            return (
              <li
                key={m.month}
                style={{
                  borderBottom:
                    idx === months.length - 1
                      ? "none"
                      : "1px solid var(--pq-hairline, var(--pq-ivory-line))",
                }}
              >
                <Link
                  href={`/reports?month=${m.month}`}
                  aria-label={`${monthAbbrev} ${year} — ${m.count} artifacts`}
                  className="hover:bg-[rgba(184,149,106,0.04)] pq-year-timeline-row"
                  style={{
                    display: "grid",
                    gridTemplateColumns: "80px 60px 1fr 90px",
                    alignItems: "center",
                    gap: 16,
                    padding: "20px 28px",
                    textDecoration: "none",
                    transition: "background-color 200ms ease",
                  }}
                >
                  <style jsx>{`
                    @media (max-width: 640px) {
                      :global(.pq-year-timeline-row) {
                        grid-template-columns: 56px 48px 1fr 64px !important;
                        gap: 10px !important;
                        padding: 14px 16px !important;
                      }
                    }
                  `}</style>
                  {/* 종목명 main pattern: month name + year */}
                  <div
                    className="font-display"
                    style={{
                      fontWeight: 500,
                      fontSize: "var(--pq-text-quote)",
                      color: "var(--pq-ivory, #F5F0E8)",
                      lineHeight: 1.1,
                    }}
                  >
                    {monthAbbrev}
                  </div>
                  <div
                    className="font-mono"
                    style={{
                      fontVariantNumeric: "tabular-nums",
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.16em",
                      color: "rgba(245,240,232,0.45)",
                    }}
                  >
                    {year}
                  </div>
                  <div
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-body)",
                      color: "rgba(245,240,232,0.78)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {titlesPreview || (
                      <span style={{ color: "rgba(245,240,232,0.55)" }}>
                        — no artifacts —
                      </span>
                    )}
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div
                      className="font-mono"
                      style={{
                        fontVariantNumeric: "tabular-nums",
                        fontSize: "var(--pq-text-body)",
                        color:
                          m.count > 0
                            ? "var(--pq-ivory, #F5F0E8)"
                            : "rgba(245,240,232,0.45)",
                      }}
                    >
                      {m.count}
                    </div>
                    <div
                      className="font-mono uppercase"
                      style={{
                        fontSize: "var(--pq-text-kicker)",
                        letterSpacing: "0.18em",
                        color: "rgba(245,240,232,0.45)",
                        marginTop: 2,
                      }}
                    >
                      artifacts
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default YearTimelineBlock;
