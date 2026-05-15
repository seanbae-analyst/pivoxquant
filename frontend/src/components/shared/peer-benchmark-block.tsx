"use client";

/**
 * <PeerBenchmarkBlock /> — anonymized peer-group comparison card.
 *
 * Extracted from <PersonaV2Card /> so it can be reused in any surface
 * that wants to show "you vs the median of your persona group":
 *
 *   • /profile — rich 9-dim classifier card (Persona v2)
 *   • /reports — Weekly Memo / Brag Card context row
 *   • /reports/<artifact> — future web preview
 *
 * Legal contract (HANDOVER v7 P1-7):
 *   1. N >= 20 floor — otherwise `available: false` with reason
 *      "insufficient_group_size" → we render an explicit suppression
 *      notice (never leak individual records).
 *   2. Observational language only — every string below is descriptive.
 *      No "추천"/"조언"/"buy"/"sell" — KISA / 자본시장법 safe.
 *   3. Own metrics (CAGR / Sharpe / holding days) are passed in as
 *      props — this block does not fetch the caller's private numbers.
 *      Callers pass `null` when the data isn't available and the delta
 *      pill is simply hidden.
 *
 * Styling: Bronze-on-ink tokens (`var(--pq-bronze)`, `var(--pq-ivory)`)
 * so it drops straight into the existing editorial surfaces.
 */

import * as React from "react";
import {
  usePersonaBenchmark,
  type PersonaBenchmarkWindow,
} from "@/lib/cfo/hooks";

/* ── Locale ── */

const MISTAKE_LABELS_KR: Record<string, string> = {
  disposition_effect: "손실은 오래 들고 이익은 빨리 판다",
  herding: "남이 사면 따라 산다",
  anchoring: "매수가에 집착한다",
};

/* ── Shared styling tokens ── */

const PAPER_BG = "rgba(255,255,255,0.02)";
const PAPER_BORDER = "var(--pq-ivory-line)";

/* ── Utilities ── */

function fmt(
  n: number | null | undefined,
  digits = 1,
  suffix = "",
): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return `${n.toFixed(digits)}${suffix}`;
}

/* ── Atoms ── */

function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
      {children}
    </div>
  );
}

function BenchmarkCompareRow({
  label,
  own,
  group,
  suffix = "",
  digits = 1,
}: {
  label: string;
  own: number | null | undefined;
  group: number | null | undefined;
  suffix?: string;
  digits?: number;
}) {
  const delta =
    own !== null && own !== undefined && group !== null && group !== undefined
      ? own - group
      : null;
  return (
    <div className="flex items-baseline justify-between gap-3 py-2 border-b border-[var(--pq-ivory-line-soft)] last:border-0">
      <span className="text-xs text-[rgba(245,240,232,0.6)]">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="font-mono tabular-nums text-sm text-[var(--pq-ivory)]">
          {fmt(group, digits, suffix)}
        </span>
        {delta !== null && (
          <span
            className="font-mono tabular-nums text-pq-eyebrow"
            style={{
              color:
                delta > 0
                  ? "rgba(184,149,106,0.85)"
                  : delta < 0
                    ? "rgba(245,240,232,0.45)"
                    : "rgba(245,240,232,0.55)",
            }}
            aria-label={`Your ${label} vs group median: delta ${fmt(delta, digits, suffix)}`}
          >
            you {delta >= 0 ? "+" : ""}
            {fmt(delta, digits, suffix)}
          </span>
        )}
      </div>
    </div>
  );
}

/* ── Main ── */

export interface PeerBenchmarkBlockProps {
  /** Display label for the current persona (e.g. "Growth CFO"). */
  personaLabel: string;
  /** User's own CAGR %, if known. `null` hides the delta pill. */
  ownCagr?: number | null;
  /** User's own Sharpe ratio. */
  ownSharpe?: number | null;
  /** User's own median holding days. */
  ownHolding?: number | null;
  /** Rolling window for the benchmark — 30 | 90 | 365 days. */
  windowDays?: PersonaBenchmarkWindow;
  /** Optional kicker override (e.g. "Weekly Memo · peer view"). */
  kicker?: string;
  /** Extra className — lets the caller control width / margins. */
  className?: string;
}

/**
 * Anonymized peer benchmark card. Fetches `/api/profile/persona-benchmark`
 * and renders own-vs-median comparison when N >= 20; otherwise a
 * suppression notice. Returns `null` on hard error so callers can
 * fail-quiet next to other editorial surfaces.
 */
export function PeerBenchmarkBlock({
  personaLabel,
  ownCagr = null,
  ownSharpe = null,
  ownHolding = null,
  windowDays = 90,
  kicker,
  className = "",
}: PeerBenchmarkBlockProps) {
  const { data, isLoading, error } = usePersonaBenchmark(windowDays);
  const _kicker = kicker ?? `Peer benchmark · ${windowDays}-day`;

  if (isLoading) {
    return (
      <div
        className={className + " p-5 rounded-[2px]"}
        style={{ background: PAPER_BG, border: `1px solid ${PAPER_BORDER}` }}
      >
        <Kicker>{_kicker}</Kicker>
        <p className="mt-3 text-xs text-[rgba(245,240,232,0.4)]">Loading…</p>
      </div>
    );
  }

  if (error || !data) {
    return null;
  }

  if (!data.available) {
    return (
      <div
        className={className + " p-5 rounded-[2px]"}
        style={{ background: PAPER_BG, border: `1px solid ${PAPER_BORDER}` }}
      >
        <Kicker>{_kicker}</Kicker>
        <p className="mt-2 text-xs text-[rgba(245,240,232,0.55)]">
          {data.reason === "insufficient_group_size"
            ? `The ${personaLabel} group currently has fewer than 20 members — peer stats are withheld for privacy.`
            : "Peer stats are being computed. Check back soon."}
        </p>
      </div>
    );
  }

  const s = data.stats;

  return (
    <div
      className={className + " p-5 rounded-[2px]"}
      style={{ background: PAPER_BG, border: `1px solid ${PAPER_BORDER}` }}
    >
      <div className="flex items-baseline justify-between gap-3">
        <Kicker>{_kicker}</Kicker>
        <span className="text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.45)]">
          N ≥ 20 · anonymized
        </span>
      </div>
      <p className="mt-2 text-xs text-[rgba(245,240,232,0.55)]">
        Median statistics across everyone classified as{" "}
        <span className="text-[var(--pq-ivory)]">{personaLabel}</span>.
        Observational — no individual record is exposed.
      </p>

      <div className="mt-4">
        <BenchmarkCompareRow
          label="CAGR (median)"
          own={ownCagr}
          group={s.avg_cagr}
          digits={2}
          suffix="%"
        />
        <BenchmarkCompareRow
          label="Sharpe (median)"
          own={ownSharpe}
          group={s.avg_sharpe}
          digits={2}
        />
        <BenchmarkCompareRow
          label="Holding days (median)"
          own={ownHolding}
          group={s.median_holding_days}
          digits={1}
        />
        <BenchmarkCompareRow
          label="Win rate"
          own={null}
          group={s.win_rate}
          digits={1}
          suffix="%"
        />
        <BenchmarkCompareRow
          label="Max drawdown (avg)"
          own={null}
          group={s.max_drawdown_avg}
          digits={1}
          suffix="%"
        />
      </div>

      {s.most_held_sectors && s.most_held_sectors.length > 0 && (
        <div className="mt-4">
          <div className="text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.45)]">
            Most-held sectors
          </div>
          <ul className="mt-2 flex flex-wrap gap-2">
            {s.most_held_sectors.slice(0, 5).map((sec) => (
              <li
                key={sec.sector}
                className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-pq-mono-sm"
                style={{
                  background: "rgba(184,149,106,0.08)",
                  border: "0.5px solid rgba(184,149,106,0.25)",
                  color: "rgba(245,240,232,0.75)",
                }}
              >
                <span className="font-serif">{sec.sector}</span>
                <span className="font-mono tabular-nums text-[rgba(184,149,106,0.85)]">
                  {fmt(sec.share, 1)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {s.common_mistakes && s.common_mistakes.length > 0 && (
        <div className="mt-4">
          <div className="text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.45)]">
            Common behavioural patterns in this group
          </div>
          <ul className="mt-2 flex flex-col gap-1.5">
            {s.common_mistakes.slice(0, 3).map((m) => (
              <li
                key={m.label}
                className="flex items-baseline justify-between gap-3 text-xs"
              >
                <span className="text-[rgba(245,240,232,0.65)]">
                  {MISTAKE_LABELS_KR[m.label] ?? m.label}
                </span>
                <span className="font-mono tabular-nums text-[rgba(245,240,232,0.45)]">
                  {m.count}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default PeerBenchmarkBlock;
