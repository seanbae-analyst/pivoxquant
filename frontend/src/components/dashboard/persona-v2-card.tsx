"use client";

/**
 * <PersonaV2Card /> — 9-dim classifier visualisation for /profile.
 *
 * Wires `/api/profile/persona-detail` and `/api/profile/persona-benchmark`
 * into the Identity section. Renders:
 *
 *   1. Persona badge (one of 8 codes: growth/value/balanced/income/quant/
 *      speculator/daytrader/beginner) + confidence + sparsity warning.
 *   2. 9-dimension bar chart — observed value vs. centroid of the winning
 *      persona, sorted by contribution (closeness × weight).
 *   3. "Why this persona?" explanation card reading the top-3 contributing
 *      features from `breakdown`.
 *   4. Peer benchmark: own vs. group median (N >= 20, anonymized).
 *
 * Pure inline SVG — no recharts dep for the 9-dim chart so we inherit the
 * ink-on-ivory aesthetic of `rolling-window.tsx` exactly. Degrades cleanly
 * when the user has <10 observed trades (data_sparse flag from backend).
 *
 * Legal: every string is descriptive/observational. No advice language.
 */

import * as React from "react";
import {
  usePersonaDetail,
  usePersonaBenchmark,
  PERSONA_LABELS,
  PERSONA_TAGLINES,
  type PersonaFeatureKey,
  type PersonaBreakdownRow,
  type PersonaId,
} from "@/lib/cfo/hooks";

/* ── Locale ── */

const MISTAKE_LABELS_KR: Record<string, string> = {
  disposition_effect: "손실은 오래 들고 이익은 빨리 판다",
  herding: "남이 사면 따라 산다",
  anchoring: "매수가에 집착한다",
};

/* ── Shared styling ── */

const PAPER_BG = "rgba(255,255,255,0.02)";
const PAPER_BORDER = "rgba(245,240,232,0.08)";

function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
      {children}
    </div>
  );
}

function fmt(n: number | null | undefined, digits = 1, suffix = ""): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return `${n.toFixed(digits)}${suffix}`;
}

/* ── Persona header ── */

function PersonaHeader({
  persona,
  confidence,
  dataSparse,
  tradeCount,
  windowDays,
  declared,
}: {
  persona: PersonaId;
  confidence: number;
  dataSparse: boolean;
  tradeCount: number;
  windowDays: number;
  declared: PersonaId | null;
}) {
  const label = PERSONA_LABELS[persona];
  const tagline = PERSONA_TAGLINES[persona];
  const drift = declared && declared !== persona;

  return (
    <div
      className="p-5 rounded-[2px]"
      style={{
        background: PAPER_BG,
        border: `1px solid ${PAPER_BORDER}`,
      }}
    >
      <Kicker>
        Observed persona · {windowDays}-day window
      </Kicker>

      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <div className="font-serif text-2xl text-[var(--pq-ivory)]">
            {label}
          </div>
          <div className="mt-1 font-serif italic text-[13px] text-[rgba(184,149,106,0.85)]">
            {tagline}
          </div>
        </div>

        <div className="flex flex-col items-end">
          <div
            className="font-mono tabular-nums text-sm"
            style={{ color: "rgba(245,240,232,0.6)" }}
            aria-label={`Classification confidence: ${confidence} out of 100`}
          >
            confidence · {confidence}
          </div>
          <div className="mt-1 text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.45)]">
            {tradeCount} {tradeCount === 1 ? "trade" : "trades"} observed
          </div>
        </div>
      </div>

      {/* Confidence meter — bronze hairline bar, ink ground */}
      <div
        className="mt-4 h-[3px] w-full overflow-hidden rounded-full"
        style={{ background: "rgba(245,240,232,0.08)" }}
        role="progressbar"
        aria-valuenow={confidence}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.max(0, Math.min(100, confidence))}%`,
            background: "var(--pq-bronze)",
            transition: "width 600ms cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        />
      </div>

      {/* Drift vs declared */}
      {drift && (
        <p className="mt-3 text-xs text-[rgba(245,240,232,0.6)]">
          Declared persona is{" "}
          <strong className="text-[var(--pq-ivory)]">
            {PERSONA_LABELS[declared!]}
          </strong>{" "}
          — your recent behaviour reads differently.
        </p>
      )}

      {dataSparse && (
        <p className="mt-3 text-xs text-[rgba(245,240,232,0.5)]">
          Fewer than 10 closed trades in window — confidence is
          preliminary. More activity sharpens this classification.
        </p>
      )}
    </div>
  );
}

/* ── 9-dim feature bars ── */

function FeatureBars({
  features,
  present,
  breakdown,
}: {
  features: Record<PersonaFeatureKey, number>;
  present: Record<PersonaFeatureKey, 0 | 1>;
  breakdown: PersonaBreakdownRow[];
}) {
  // `breakdown` is already ordered by closeness * weight desc — preserve that.
  return (
    <div
      className="p-5 rounded-[2px]"
      style={{
        background: PAPER_BG,
        border: `1px solid ${PAPER_BORDER}`,
      }}
    >
      <Kicker>9-dimension profile</Kicker>
      <p className="mt-2 text-xs text-[rgba(245,240,232,0.55)]">
        Each bar compares your observed behaviour (filled) against the
        centroid of your classified persona (hairline). Closer bars
        pushed harder toward the classification.
      </p>

      <ul className="mt-5 flex flex-col gap-3.5">
        {breakdown.map((row) => {
          const observed = Math.max(
            0,
            Math.min(1, features[row.feature] ?? row.value),
          );
          const centroid = Math.max(0, Math.min(1, row.centroid));
          const sparse = present[row.feature] === 0;
          return (
            <li
              key={row.feature}
              className="grid grid-cols-[180px_1fr_54px] items-center gap-3"
            >
              <div className="min-w-0">
                <div
                  className={
                    "font-serif text-[13px] truncate " +
                    (sparse
                      ? "text-[rgba(245,240,232,0.35)]"
                      : "text-[var(--pq-ivory)]")
                  }
                >
                  {row.label}
                </div>
                {sparse && (
                  <div className="text-[9.5px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.3)]">
                    no evidence · default
                  </div>
                )}
              </div>

              {/* Bar track */}
              <div
                className="relative h-[10px] rounded-sm"
                style={{
                  background: "rgba(245,240,232,0.06)",
                  border: "0.5px solid rgba(245,240,232,0.08)",
                }}
                aria-hidden
              >
                {/* Centroid hairline marker */}
                <div
                  className="absolute top-0 bottom-0"
                  style={{
                    left: `${centroid * 100}%`,
                    width: "1px",
                    background: "rgba(184,149,106,0.55)",
                  }}
                  title={`centroid ${fmt(centroid, 2)}`}
                />
                {/* Observed fill */}
                <div
                  className="absolute top-0 bottom-0 left-0 rounded-sm"
                  style={{
                    width: `${observed * 100}%`,
                    background: sparse
                      ? "rgba(184,149,106,0.2)"
                      : "rgba(184,149,106,0.6)",
                    transition:
                      "width 600ms cubic-bezier(0.16, 1, 0.3, 1)",
                  }}
                />
              </div>

              <div className="text-right font-mono tabular-nums text-[12px] text-[rgba(245,240,232,0.65)]">
                {fmt(observed, 2)}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ── "Why this persona" top-3 contributors ── */

function WhyThisPersona({
  breakdown,
  label,
}: {
  breakdown: PersonaBreakdownRow[];
  label: string;
}) {
  const top = breakdown.slice(0, 3);
  return (
    <div
      className="p-5 rounded-[2px]"
      style={{
        background: PAPER_BG,
        border: `1px solid ${PAPER_BORDER}`,
      }}
    >
      <Kicker>Why {label}?</Kicker>
      <p className="mt-2 text-xs text-[rgba(245,240,232,0.55)]">
        The three strongest signals pulling your profile toward this
        persona — ordered by closeness to the centroid × feature weight.
      </p>

      <ul className="mt-4 flex flex-col gap-3">
        {top.map((row, i) => (
          <li
            key={row.feature}
            className="flex items-start gap-3"
            style={{
              paddingBottom: i < top.length - 1 ? 12 : 0,
              borderBottom:
                i < top.length - 1
                  ? "0.5px solid rgba(245,240,232,0.06)"
                  : "none",
            }}
          >
            <span
              className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px]"
              style={{
                border: "0.5px solid var(--pq-bronze)",
                color: "var(--pq-bronze)",
              }}
              aria-hidden
            >
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="font-serif text-[14px] text-[var(--pq-ivory)]">
                {row.label}
              </div>
              <div className="mt-1 text-xs text-[rgba(245,240,232,0.55)]">
                Observed{" "}
                <span className="font-mono tabular-nums text-[var(--pq-ivory)]">
                  {fmt(row.value, 2)}
                </span>{" "}
                vs centroid{" "}
                <span className="font-mono tabular-nums text-[var(--pq-ivory)]">
                  {fmt(row.centroid, 2)}
                </span>
                <span className="text-[rgba(245,240,232,0.4)]">
                  {" "}
                  · closeness {fmt(row.closeness, 2)}
                </span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ── Benchmark (peer median) ── */

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
    <div className="flex items-baseline justify-between gap-3 py-2 border-b border-[rgba(245,240,232,0.06)] last:border-0">
      <span className="text-xs text-[rgba(245,240,232,0.6)]">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="font-mono tabular-nums text-sm text-[var(--pq-ivory)]">
          {fmt(group, digits, suffix)}
        </span>
        {delta !== null && (
          <span
            className="font-mono tabular-nums text-[10px]"
            style={{
              color:
                delta > 0
                  ? "rgba(184,149,106,0.85)"
                  : delta < 0
                    ? "rgba(245,240,232,0.45)"
                    : "rgba(245,240,232,0.35)",
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

function BenchmarkCard({
  personaLabel,
  ownCagr,
  ownSharpe,
  ownHolding,
}: {
  personaLabel: string;
  ownCagr: number | null;
  ownSharpe: number | null;
  ownHolding: number | null;
}) {
  const { data, isLoading, error } = usePersonaBenchmark(90);

  if (isLoading) {
    return (
      <div
        className="p-5 rounded-[2px]"
        style={{ background: PAPER_BG, border: `1px solid ${PAPER_BORDER}` }}
      >
        <Kicker>Peer benchmark · 90-day</Kicker>
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
        className="p-5 rounded-[2px]"
        style={{ background: PAPER_BG, border: `1px solid ${PAPER_BORDER}` }}
      >
        <Kicker>Peer benchmark · 90-day</Kicker>
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
      className="p-5 rounded-[2px]"
      style={{ background: PAPER_BG, border: `1px solid ${PAPER_BORDER}` }}
    >
      <div className="flex items-baseline justify-between gap-3">
        <Kicker>Peer benchmark · 90-day</Kicker>
        <span className="text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.45)]">
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
          <div className="text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.45)]">
            Most-held sectors
          </div>
          <ul className="mt-2 flex flex-wrap gap-2">
            {s.most_held_sectors.slice(0, 5).map((sec) => (
              <li
                key={sec.sector}
                className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-[11px]"
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
          <div className="text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.45)]">
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

/* ── Main ── */

interface Props {
  className?: string;
}

export function PersonaV2Card({ className = "" }: Props) {
  const { data, isLoading, error } = usePersonaDetail(90);

  if (isLoading) {
    return (
      <div
        className={className + " p-5 rounded-[2px]"}
        style={{ background: PAPER_BG, border: `1px solid ${PAPER_BORDER}` }}
      >
        <Kicker>Persona classifier</Kicker>
        <p className="mt-3 text-xs text-[rgba(245,240,232,0.4)]">
          Analysing your 9-dimension behavioural vector…
        </p>
      </div>
    );
  }

  if (error || !data) {
    // Fail-quiet: the hero-card `usePersona()` already owns the "who are
    // you" summary. This richer surface is additive — don't nag the user.
    return null;
  }

  return (
    <div className={className + " space-y-4"}>
      <PersonaHeader
        persona={data.persona}
        confidence={data.confidence}
        dataSparse={data.data_sparse}
        tradeCount={data.trade_count}
        windowDays={data.window_days}
        declared={data.declared_persona}
      />
      <FeatureBars
        features={data.features}
        present={data.present}
        breakdown={data.breakdown}
      />
      <WhyThisPersona breakdown={data.breakdown} label={data.label} />
      <BenchmarkCard
        personaLabel={data.label}
        ownCagr={null}
        ownSharpe={null}
        ownHolding={null}
      />
    </div>
  );
}

export default PersonaV2Card;
