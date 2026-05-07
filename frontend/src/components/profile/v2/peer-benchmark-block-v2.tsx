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

interface Props {
  /**
   * Cohort metric set sourced from `/api/profile/persona-benchmark`.
   * When omitted, null, or empty, renders an empty-state placeholder
   * instead of fabricated peer figures.
   * Bug-hunter 2026-05-07: removed editorial DEFAULT_METRICS fallback —
   * was leaking invented Sharpe 1.42 / MaxDD -6.8% / Turnover 0.41 /
   * Concentration 41% to every signed-in user (CEO escalation NEW-B).
   */
  metrics?: PeerMetric[] | null;
  /** Cohort label, e.g. "Defensive Allocator". Null when not yet classified. */
  cohortName?: string | null;
  /** Sample size. Null when cohort unavailable / suppressed (N < 20). */
  cohortSize?: number | null;
  /** Window in days. */
  windowDays?: number;
  /** True while upstream hook is loading. */
  loading?: boolean;
  /**
   * Reason for empty state — surfaces a tailored message:
   *   - "insufficient_group_size": N < 20, suppressed for privacy
   *   - "not_computed": pending compute
   *   - "no_data": new user / no trade history
   */
  emptyReason?: "insufficient_group_size" | "not_computed" | "no_data";
}

export function PeerBenchmarkBlockV2({
  metrics,
  cohortName,
  cohortSize,
  windowDays = 90,
  loading = false,
  emptyReason = "no_data",
}: Props) {
  const list = metrics && metrics.length > 0 ? metrics : null;
  const hasCohort = Boolean(cohortName);

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
      aria-label={
        hasCohort
          ? `Peer benchmark · ${cohortName} cohort`
          : "Peer benchmark"
      }
    >
      <span
        className="font-mono uppercase"
        style={{
          position: "absolute",
          top: 14,
          right: 14,
          fontSize: 12,
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
              fontSize: 12,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            05 · Peer benchmark{hasCohort ? ` · ${cohortName} cohort` : ""}
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
            fontSize: 12,
            color: "rgba(245,240,232,0.40)",
            letterSpacing: "0.18em",
          }}
        >
          {typeof cohortSize === "number"
            ? `n = ${cohortSize.toLocaleString()} · ${windowDays}D`
            : `${windowDays}D · cohort pending`}
        </div>
      </div>

      {!list ? (
        <div
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px dashed rgba(245,240,232,0.14)",
            borderRadius: 4,
            padding: 28,
            textAlign: "center",
          }}
          role="status"
          aria-live="polite"
        >
          <div
            className="font-mono uppercase"
            style={{
              fontSize: 11,
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
              maxWidth: 560,
              margin: "0 auto",
            }}
          >
            {loading
              ? "Computing your peer benchmark…"
              : emptyReason === "insufficient_group_size"
                ? "동일 페르소나 그룹 인원이 20명 미만이라 통계가 보호됩니다 (PIPA). Cohort suppressed for privacy until N ≥ 20."
                : emptyReason === "not_computed"
                  ? "동료 통계가 아직 계산되지 않았습니다. Peer statistics are still being computed."
                  : "거래 기록이 누적되면 동일 페르소나 그룹 대비 통계가 표시됩니다. Peer benchmark surfaces here once your trade history accumulates."}
          </p>
        </div>
      ) : null}

      <div
        style={{
          display: list ? "grid" : "none",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          columnGap: 48,
          rowGap: 28,
        }}
      >
        {list?.map((m) => {
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
                    fontSize: 12,
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
                    fontSize: 14,
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

      {list ? (
        <div
          className="font-mono uppercase"
          style={{
            marginTop: 16,
            fontSize: 12,
            letterSpacing: "0.16em",
            color: "rgba(245,240,232,0.40)",
          }}
        >
          YOU · BRONZE BAR &nbsp; · &nbsp; MEDIAN · IVORY TICK
        </div>
      ) : null}
    </section>
  );
}

export default PeerBenchmarkBlockV2;
