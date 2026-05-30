"use client";

/**
 * Profit/Loss-Mirror — the realised-return "mirror" panel.
 *
 * A neutral 2-up comparison of the user's OWN closed trade pairs, split by
 * whether each pair realised a PROFIT or a LOSS. For each side it mirrors two
 * plain facts: the average holding period (median preferred) and the average
 * realised return percentage. It is a MIRROR, not a verdict — the same posture
 * as holding-mirror.tsx, whose MirrorShell / states / editorial primitives /
 * shared DisclaimerBanner pattern this component reuses verbatim:
 *
 *   - No score, grade, star, badge, gauge, percentile, or "health" number.
 *   - The words 처분효과 / 편향 / hazard / 진단 / 치료 / 개선 / 과속 / 지연 are
 *     NEVER surfaced. Labels are the neutral "이익 실현 매도 / 손실 실현 매도"
 *     ("익절/손절" carry a trade-instruction nuance — legal recommends the
 *     descriptive "실현 매도" form instead).
 *   - The realised return % renders with its raw sign in neutral ivory mono
 *     (NumDisplay tone="neu") — a loss stays negative, never abs(). Carmine/
 *     indigo (price-direction colours) are deliberately NOT used so the mirror
 *     passes no judgement. The hold-day asymmetry is shown ONLY through number
 *     size + a proportional bronze hairline bar (opacity .7).
 *   - <5 classified pairs → em-dash sentinels + a "not enough yet" note (no
 *     fabricated average). Zero pairs → a calm empty state with NO call-to-
 *     action (a CTA here would nudge trading = 권유 risk).
 *
 * Legal posture: 자본시장법 (no 추천/조언) + PIPA §23 (no profiling/score) +
 * DECISIONS.md (AI 점수화 폐기). The behavior-mirror disclaimer is mounted ONCE
 * at the foot of the mirror SECTION in journal/page.tsx — shared across all
 * mirrors — not inline here (2026-05-30).
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT. Mobile-first; the 2-up
 * stays side-by-side at 375px so the comparison is instant (never stacks).
 */

import { motion } from "motion/react";
import { useT, useLocale } from "@/lib/locale";
import { useProfitLossMirror } from "@/lib/hooks";
import { fadeUp } from "@/lib/motion";
import {
  RuledKicker,
  EditorialHead,
  NumDisplay,
  FieldLabel,
  Caption,
  StatRow,
} from "@/components/ui/editorial";
import type { ProfitLossMirrorResponse } from "@/lib/types";

/** Em-dash sentinel — mirrors lib/format.ts missing-value convention. */
export const EM_DASH = "—";

/** Minimum classified pairs before averages are shown as "stable". */
export const MIN_PAIRS = 5;

/* ────────────────────────────────────────────────────────────────────────
 * Pure view-model — keeps the render path declarative and unit-testable
 * without a DOM. NEVER produces a score/grade; only days, return %, bar
 * weights, and sentinels.
 * ────────────────────────────────────────────────────────────────────── */

export interface PLColumnView {
  /** Pre-formatted hold days: "<n><unit>" when stable, else em-dash. */
  hold: string;
  /** Pre-formatted realised return %: "+<n>%" / "<n>%" (sign kept), else em-dash. */
  ret: string;
  /** 0..1 proportional hold-day bar weight; 0 when no stable average. */
  weight: number;
  /** Raw hold days (median preferred, mean fallback) or null. */
  days: number | null;
}

export interface PLMirrorView {
  enough: boolean;
  takeProfit: PLColumnView;
  stopLoss: PLColumnView;
}

/** Median-preferred, mean-fallback numeric pick (null when neither finite). */
function pick(
  median: number | null | undefined,
  mean: number | null | undefined,
): number | null {
  const m = median ?? mean;
  return typeof m === "number" && Number.isFinite(m) ? m : null;
}

/**
 * Compute the neutral 2-up view model from the backend payload.
 * @param data    locked ProfitLossMirrorResponse shape
 * @param daysUnit i18n unit suffix ("일" / "d")
 */
export function computeProfitLossView(
  data: ProfitLossMirrorResponse,
  daysUnit: string,
): PLMirrorView {
  const enough =
    data.sufficient_data && data.total_closed_pairs >= MIN_PAIRS;

  // A side can be null (backend nulls the empty side of a one-sided / scarce
  // window). Treat a null side as "no data" → em-dash, never a fabricated 0.
  const tpDays =
    data.take_profit == null
      ? null
      : pick(data.take_profit.median_hold_days, data.take_profit.mean_hold_days);
  const slDays =
    data.stop_loss == null
      ? null
      : pick(data.stop_loss.median_hold_days, data.stop_loss.mean_hold_days);
  const tpRet =
    data.take_profit == null
      ? null
      : pick(data.take_profit.median_gain_pct, data.take_profit.mean_gain_pct);
  const slRet =
    data.stop_loss == null
      ? null
      : pick(data.stop_loss.median_loss_pct, data.stop_loss.mean_loss_pct);

  // Scale both hold bars against the longer hold so it reaches full width.
  const maxDays = Math.max(tpDays ?? 0, slDays ?? 0) || 1;

  const fmtDays = (d: number | null): string =>
    enough && d != null && Number.isFinite(d)
      ? `${Math.round(d)}${daysUnit}`
      : EM_DASH;

  // Return %: keep the raw sign. A positive gain shows a leading "+"; a loss
  // keeps its native "-" (the minus is part of the number string itself).
  const fmtRet = (r: number | null): string => {
    if (!enough || r == null || !Number.isFinite(r)) return EM_DASH;
    const rounded = Math.round(r * 10) / 10;
    const sign = rounded > 0 ? "+" : "";
    return `${sign}${rounded}%`;
  };

  const weight = (d: number | null): number =>
    enough && d != null && Number.isFinite(d)
      ? Math.max(0, Math.min(1, d / maxDays))
      : 0;

  return {
    enough,
    takeProfit: {
      hold: fmtDays(tpDays),
      ret: fmtRet(tpRet),
      weight: weight(tpDays),
      days: tpDays,
    },
    stopLoss: {
      hold: fmtDays(slDays),
      ret: fmtRet(slRet),
      weight: weight(slDays),
      days: slDays,
    },
  };
}

/* ────────────────────────────────────────────────────────────────────────
 * Shell — kicker + heading + framed card body. Mirrors holding-mirror.tsx.
 * ────────────────────────────────────────────────────────────────────── */

function MirrorShell({
  t,
  children,
}: {
  t: (k: string) => string;
  children: React.ReactNode;
}) {
  return (
    <motion.section
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="rounded-[2px] border p-5 sm:p-6"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
      aria-label={t("journal.profitLossMirror.kicker")}
    >
      <RuledKicker>{t("journal.profitLossMirror.kicker")}</RuledKicker>
      <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
        {t("journal.profitLossMirror.heading")}
      </EditorialHead>
      {children}
    </motion.section>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * One side of the 2-up. `hold`/`ret` are pre-formatted strings (already days/
 * % or em-dash). `weight` (0..1) scales the proportional bronze hairline bar.
 * Always neutral ivory — no price-direction colour, no verdict.
 * ────────────────────────────────────────────────────────────────────── */

function PLColumn({
  label,
  hold,
  ret,
  holdCaption,
  retCaption,
  weight,
}: {
  label: string;
  hold: string;
  ret: string;
  holdCaption: string;
  retCaption: string;
  weight: number;
}) {
  const pct = Math.max(0, Math.min(1, weight)) * 100;
  return (
    <div className="min-w-0">
      <FieldLabel tone="bronze">{label}</FieldLabel>

      {/* Average hold — the protagonist number, neutral ivory. */}
      <div className="mt-2">
        <NumDisplay size={40} tone="neu">
          {hold}
        </NumDisplay>
      </div>
      {/* Proportional bronze hairline — the ONLY asymmetry cue besides size. */}
      <div
        className="mt-3 h-px w-full overflow-hidden"
        style={{ background: "var(--pq-ivory-line-faint)" }}
        aria-hidden="true"
      >
        <div
          className="h-px"
          style={{
            width: `${pct}%`,
            background: "var(--pq-bronze)",
            opacity: 0.7,
            transition: "width 500ms cubic-bezier(0.16,1,0.3,1)",
          }}
        />
      </div>
      <Caption className="mt-2">{holdCaption}</Caption>

      {/* Realised return % — secondary fact, raw sign, neutral mono. */}
      <div className="mt-4">
        <NumDisplay size={24} tone="neu">
          {ret}
        </NumDisplay>
      </div>
      <Caption className="mt-1.5">{retCaption}</Caption>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * States
 * ────────────────────────────────────────────────────────────────────── */

function LoadingState({ t }: { t: (k: string) => string }) {
  return (
    <MirrorShell t={t}>
      <div className="mt-5 grid grid-cols-2 gap-3" aria-hidden="true">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="h-40 animate-pulse rounded-[2px]"
            style={{ background: "var(--pq-ivory-line-faint)" }}
          />
        ))}
      </div>
    </MirrorShell>
  );
}

/** Zero classified pairs → calm, NO call-to-action (avoid nudging a trade). */
function EmptyState({ t }: { t: (k: string) => string }) {
  return (
    <MirrorShell t={t}>
      <EditorialHead as="p" size={18} tone="muted" className="mt-4">
        {t("journal.profitLossMirror.emptyTitle")}
      </EditorialHead>
      <Caption className="mt-2 max-w-md">
        {t("journal.profitLossMirror.emptyDesc")}
      </Caption>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Loaded — sufficient OR insufficient data both render the 2-up; insufficient
 * shows em-dash sentinels + an explanatory note instead of fabricated numbers.
 * ────────────────────────────────────────────────────────────────────── */

function LoadedMirror({
  data,
  t,
}: {
  data: ProfitLossMirrorResponse;
  t: (k: string) => string;
}) {
  const view = computeProfitLossView(
    data,
    t("journal.profitLossMirror.daysUnit"),
  );

  return (
    <MirrorShell t={t}>
      <div className="mt-5 grid grid-cols-2 gap-3 sm:gap-5">
        <PLColumn
          label={t("journal.profitLossMirror.takeProfitLabel")}
          hold={view.takeProfit.hold}
          ret={view.takeProfit.ret}
          holdCaption={t("journal.profitLossMirror.avgHold")}
          retCaption={t("journal.profitLossMirror.avgReturn")}
          weight={view.takeProfit.weight}
        />
        <PLColumn
          label={t("journal.profitLossMirror.stopLossLabel")}
          hold={view.stopLoss.hold}
          ret={view.stopLoss.ret}
          holdCaption={t("journal.profitLossMirror.avgHold")}
          retCaption={t("journal.profitLossMirror.avgReturn")}
          weight={view.stopLoss.weight}
        />
      </div>

      {/* Insufficient-data note — sits in place of stable averages. */}
      {!view.enough && (
        <Caption className="mt-4 max-w-md">
          {t("journal.profitLossMirror.insufficient")}
        </Caption>
      )}

      {/* Factual counts line — only meaningful when we have averages. */}
      {view.enough && (
        <div className="mt-5">
          <StatRow
            label={t("journal.profitLossMirror.countsLabel")}
            value={t("journal.profitLossMirror.countsValue")
              .replace("{total}", String(data.total_closed_pairs))
              .replace("{profit}", String(data.take_profit?.count ?? 0))
              .replace("{loss}", String(data.stop_loss?.count ?? 0))}
          />
        </div>
      )}

      {/* Neutral framing line — "we mirror, we do not judge." */}
      <Caption className="mt-4 max-w-lg">
        {t("journal.profitLossMirror.framing")}
      </Caption>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Public component — own SWR + own loading/error boundary so a mirror failure
 * NEVER takes down the Decision Journal feed beneath it.
 * ────────────────────────────────────────────────────────────────────── */

export function ProfitLossMirror() {
  const t = useT();
  // Locale subscription keeps copy/units re-rendering on language switch.
  useLocale();
  const { data, isLoading, error } = useProfitLossMirror();

  // Hard failure (5xx / network) → render nothing rather than a broken card.
  // A 404 (backend not yet wired) is normalised to `data === null` by the hook.
  if (error) return null;
  if (isLoading) return <LoadingState t={t} />;
  if (!data || data.total_closed_pairs <= 0) return <EmptyState t={t} />;
  return <LoadedMirror data={data} t={t} />;
}
