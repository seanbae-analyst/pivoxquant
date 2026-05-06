"use client";

/**
 * <PeerBenchmarkBlockV2 />
 *
 * Block 5 of /profile v2 — peer benchmark.
 * Mirror of profile-v2 mockup §608 ("05 · Peer benchmark · cohort").
 *
 * Renders a 2×2 grid of metrics. Each metric has:
 *   - eyebrow label (e.g. "Sharpe (90d)")
 *   - mono value + percentile callout (e.g. "1.42 · top 18%")
 *   - peer-track gauge: median tick (1px ivory) + you bar (2px bronze)
 *
 * Pure presentational. Caller supplies metrics array + cohort metadata.
 *
 * Legal: persona vocabulary only. No advice/recommend strings.
 */

import * as React from "react";

export interface PeerMetric {
  /** Metric label, e.g. "Sharpe (90d)". */
  label: string;
  /** Display value, e.g. "1.42" or "-6.8%". */
  value: string;
  /** Percentile callout, e.g. "top 18%" or "bottom 30%". */
  percentile?: string;
  /** 0–100 — percent position of the user's value relative to cohort. */
  youPct: number;
  /** 0–100 — median tick position. Defaults to 50. */
  medianPct?: number;
  /** Accessible label, e.g. "You: top 18% in cohort". */
  ariaLabel?: string;
}

const DEFAULT_METRICS: PeerMetric[] = [
  {
    label: "Sharpe (90d)",
    value: "1.42",
    percentile: "top 18%",
    youPct: 82,
    medianPct: 50,
    ariaLabel: "Sharpe ratio: 1.42, top 18% of cohort",
  },
  {
    label: "Max drawdown",
    value: "-6.8%",
    percentile: "top 24%",
    youPct: 76,
    medianPct: 50,
    ariaLabel: "Max drawdown: -6.8%, top 24% of cohort",
  },
  {
    label: "Turnover",
    value: "0.41",
    percentile: "bottom 30%",
    youPct: 30,
    medianPct: 50,
    ariaLabel: "Turnover: 0.41, bottom 30% of cohort",
  },
  {
    label: "Concentration",
    value: "41%",
    percentile: "in cohort",
    youPct: 47,
    medianPct: 50,
    ariaLabel: "Concentration: 41%, near cohort median",
  },
];

interface Props {
  metrics?: PeerMetric[];
  /** Cohort label, e.g. "Defensive Allocator". */
  cohortName?: string;
  /** Sample size, e.g. 412. */
  cohortSize?: number;
  /** Window in days. */
  windowDays?: number;
}

export function PeerBenchmarkBlockV2({
  metrics,
  cohortName = "Defensive Allocator",
  cohortSize = 412,
  windowDays = 90,
}: Props) {
  const list = metrics && metrics.length > 0 ? metrics : DEFAULT_METRICS;

  return (
    <section
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(245,240,232,0.08)",
        borderRadius: 4,
        padding: 32,
        position: "relative",
        marginBottom: 48,
      }}
      aria-label={`Peer benchmark · ${cohortName} cohort`}
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
        All cohorts ›
      </span>

      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 24,
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
            05 · Peer benchmark · {cohortName} cohort
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
            How you read against{" "}
            <span style={{ color: "var(--pq-bronze)", fontStyle: "italic" }}>
              your tribe.
            </span>
          </div>
        </div>
        <div
          className="font-mono uppercase"
          style={{
            fontVariantNumeric: "tabular-nums",
            fontSize: 11,
            color: "rgba(245,240,232,0.40)",
            letterSpacing: "0.18em",
          }}
        >
          n = {cohortSize.toLocaleString()} · {windowDays}D
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          columnGap: 48,
          rowGap: 28,
        }}
      >
        {list.map((m) => {
          const youPct = Math.min(100, Math.max(0, m.youPct));
          const medianPct = Math.min(100, Math.max(0, m.medianPct ?? 50));
          return (
            <div key={m.label}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 10,
                  alignItems: "baseline",
                }}
              >
                <span
                  className="font-mono uppercase"
                  style={{
                    fontSize: 10.5,
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                  }}
                >
                  {m.label}
                </span>
                <span
                  className="font-mono"
                  style={{
                    fontVariantNumeric: "tabular-nums",
                    fontSize: 12.5,
                    color: "rgba(245,240,232,0.82)",
                  }}
                >
                  {m.value}
                  {m.percentile ? (
                    <>
                      {" "}
                      ·{" "}
                      <span style={{ color: "rgba(245,240,232,0.55)" }}>
                        {m.percentile}
                      </span>
                    </>
                  ) : null}
                </span>
              </div>
              <div
                role="meter"
                aria-label={m.ariaLabel ?? `${m.label} vs cohort`}
                aria-valuenow={youPct}
                aria-valuemin={0}
                aria-valuemax={100}
                style={{
                  position: "relative",
                  height: 6,
                  background: "rgba(245,240,232,0.06)",
                  borderRadius: 1,
                }}
              >
                <span
                  aria-hidden
                  style={{
                    position: "absolute",
                    top: 0,
                    left: `${medianPct}%`,
                    width: 1,
                    height: 6,
                    background: "rgba(245,240,232,0.40)",
                  }}
                />
                <span
                  aria-hidden
                  style={{
                    position: "absolute",
                    top: -5,
                    left: `${youPct}%`,
                    width: 2,
                    height: 16,
                    background: "var(--pq-bronze)",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div
        className="font-mono uppercase"
        style={{
          marginTop: 16,
          fontSize: 9.5,
          letterSpacing: "0.16em",
          color: "rgba(245,240,232,0.40)",
        }}
      >
        YOU · BRONZE BAR &nbsp; · &nbsp; MEDIAN · IVORY TICK
      </div>
    </section>
  );
}

export default PeerBenchmarkBlockV2;
