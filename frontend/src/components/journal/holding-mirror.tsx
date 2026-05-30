"use client";

/**
 * Holding-Mirror — the disposition-effect "mirror" panel.
 *
 * A neutral 2-up comparison of the user's average holding period for positions
 * sold while UP vs. sold while DOWN, computed from their OWN closed trade
 * pairs over a trailing window. It is a MIRROR, not a verdict:
 *
 *   - No score, grade, star, badge, gauge, percentile, or "health" number.
 *   - The words 처분효과 / 편향 / hazard / 진단 / 치료 / 개선 are NEVER surfaced.
 *   - Both sides render in neutral ivory (NumDisplay tone="neu"). Carmine/indigo
 *     (price-direction colours) are deliberately NOT used — the mirror passes
 *     no judgement. Asymmetry is shown ONLY through number size + a proportional
 *     bronze hairline bar (opacity .7).
 *   - <5 closed pairs → em-dash sentinel + a "not enough yet" note (no fabricated
 *     average). Zero trades → a calm empty state with NO call-to-action (a CTA
 *     here would nudge trading = 권유 risk).
 *
 * Legal posture: 자본시장법 (no 추천/조언) + PIPA §23 (no profiling/score).
 * The <DisclaimerBanner type="behavior-mirror" /> at the foot states, in
 * legal-confirmed wording, that this is not a medical/psychological service.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT. Mobile-first; the 2-up
 * stays side-by-side at 375px so the comparison is instant (never stacks).
 */

import { motion } from "motion/react";
import { useT, useLocale } from "@/lib/locale";
import { useHoldingMirror } from "@/lib/hooks";
import { fadeUp } from "@/lib/motion";
import {
  RuledKicker,
  EditorialHead,
  NumDisplay,
  FieldLabel,
  Caption,
  StatRow,
  HairlineSoft,
} from "@/components/ui/editorial";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import type { HoldingMirrorResponse } from "@/lib/types";

/** Em-dash sentinel — mirrors lib/format.ts missing-value convention. */
export const EM_DASH = "—";

/** Minimum closed pairs before an average is shown as "stable". */
export const MIN_PAIRS = 5;

/* ────────────────────────────────────────────────────────────────────────
 * Pure view-model — keeps the render path declarative and unit-testable
 * without a DOM. NEVER produces a score/grade; only days, weights, sentinels.
 * ────────────────────────────────────────────────────────────────────── */

export interface MirrorColumnView {
  /** Pre-formatted value: "<n><unit>" when stable, else the em-dash sentinel. */
  value: string;
  /** 0..1 proportional bar weight; 0 when no stable average. */
  weight: number;
  /** Raw days (median preferred, mean fallback) or null. */
  days: number | null;
}

export interface MirrorView {
  enough: boolean;
  winners: MirrorColumnView;
  losers: MirrorColumnView;
}

/**
 * Compute the neutral 2-up view model from the backend payload.
 * @param data    locked HoldingMirrorResponse shape
 * @param daysUnit i18n unit suffix ("일" / "d")
 */
export function computeMirrorView(
  data: HoldingMirrorResponse,
  daysUnit: string,
): MirrorView {
  const enough = data.sufficient_data && data.total_closed_pairs >= MIN_PAIRS;
  // A side can be null (backend nulls the empty side of a one-sided / scarce
  // window). Treat a null side as "no days" → renders an em-dash, never a 0.
  const wDays =
    data.winners == null
      ? null
      : data.winners.median_hold_days ?? data.winners.mean_hold_days;
  const lDays =
    data.losers == null
      ? null
      : data.losers.median_hold_days ?? data.losers.mean_hold_days;
  // Scale both bars against the longer hold so it reaches full width.
  const maxDays = Math.max(wDays ?? 0, lDays ?? 0) || 1;

  const fmt = (d: number | null): string =>
    enough && d != null && Number.isFinite(d)
      ? `${Math.round(d)}${daysUnit}`
      : EM_DASH;

  const weight = (d: number | null): number =>
    enough && d != null && Number.isFinite(d)
      ? Math.max(0, Math.min(1, d / maxDays))
      : 0;

  return {
    enough,
    winners: { value: fmt(wDays), weight: weight(wDays), days: wDays },
    losers: { value: fmt(lDays), weight: weight(lDays), days: lDays },
  };
}

/* ────────────────────────────────────────────────────────────────────────
 * Shell — kicker + heading + framed card body.
 * ────────────────────────────────────────────────────────────────────── */

function MirrorShell({
  t,
  period,
  children,
}: {
  t: (k: string) => string;
  period?: string;
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
      aria-label={t("journal.holdingMirror.kicker")}
    >
      <RuledKicker>{t("journal.holdingMirror.kicker")}</RuledKicker>
      <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
        {period || t("journal.holdingMirror.heading")}
      </EditorialHead>
      {children}
    </motion.section>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * One side of the 2-up. Value is a pre-formatted string (already days or
 * em-dash). `weight` (0..1) scales the proportional bronze hairline bar.
 * Always neutral ivory — no price-direction colour.
 * ────────────────────────────────────────────────────────────────────── */

function MirrorColumn({
  label,
  value,
  caption,
  weight,
}: {
  label: string;
  value: string;
  caption: string;
  weight: number;
}) {
  const pct = Math.max(0, Math.min(1, weight)) * 100;
  return (
    <div className="min-w-0">
      <FieldLabel tone="bronze">{label}</FieldLabel>
      <div className="mt-2">
        <NumDisplay size={40} tone="neu">
          {value}
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
      <Caption className="mt-2">{caption}</Caption>
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
            className="h-28 animate-pulse rounded-[2px]"
            style={{ background: "var(--pq-ivory-line-faint)" }}
          />
        ))}
      </div>
    </MirrorShell>
  );
}

/** Zero closed trades → calm, NO call-to-action (avoid nudging a trade). */
function EmptyState({ t }: { t: (k: string) => string }) {
  return (
    <MirrorShell t={t}>
      <EditorialHead as="p" size={18} tone="muted" className="mt-4">
        {t("journal.holdingMirror.emptyTitle")}
      </EditorialHead>
      <Caption className="mt-2 max-w-md">
        {t("journal.holdingMirror.emptyDesc")}
      </Caption>
      <div className="mt-5">
        <HairlineSoft />
      </div>
      <div className="mt-4">
        <DisclaimerBanner type="behavior-mirror" alwaysExpanded={false} />
      </div>
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
  data: HoldingMirrorResponse;
  t: (k: string) => string;
}) {
  const view = computeMirrorView(data, t("journal.holdingMirror.daysUnit"));

  return (
    <MirrorShell t={t} period={data.period}>
      <div className="mt-5 grid grid-cols-2 gap-3 sm:gap-5">
        <MirrorColumn
          label={t("journal.holdingMirror.winnersLabel")}
          value={view.winners.value}
          caption={t("journal.holdingMirror.avgHold")}
          weight={view.winners.weight}
        />
        <MirrorColumn
          label={t("journal.holdingMirror.losersLabel")}
          value={view.losers.value}
          caption={t("journal.holdingMirror.avgHold")}
          weight={view.losers.weight}
        />
      </div>

      {/* Insufficient-data note — sits in place of a stable average. */}
      {!view.enough && (
        <Caption className="mt-4 max-w-md">
          {t("journal.holdingMirror.insufficient")}
        </Caption>
      )}

      {/* Factual counts line — only meaningful when we have an average. */}
      {view.enough && (
        <div className="mt-5">
          <StatRow
            label={t("journal.holdingMirror.countsLabel")}
            value={t("journal.holdingMirror.countsValue")
              .replace("{total}", String(data.total_closed_pairs))
              .replace("{winners}", String(data.winners?.count ?? 0))
              .replace("{losers}", String(data.losers?.count ?? 0))}
          />
        </div>
      )}

      {/* Neutral framing line — "we mirror, we do not judge." */}
      <Caption className="mt-4 max-w-lg">
        {t("journal.holdingMirror.framing")}
      </Caption>

      <div className="mt-5">
        <HairlineSoft />
      </div>
      <div className="mt-4">
        <DisclaimerBanner type="behavior-mirror" alwaysExpanded={false} />
      </div>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Public component — own SWR + own loading/error boundary so a mirror failure
 * NEVER takes down the Decision Journal feed beneath it.
 * ────────────────────────────────────────────────────────────────────── */

export function HoldingMirror() {
  const t = useT();
  // Locale subscription keeps period/units re-rendering on language switch.
  useLocale();
  const { data, isLoading, error } = useHoldingMirror();

  // Hard failure (5xx / network) → render nothing rather than a broken card.
  // A 404 (backend not yet wired) is normalised to `data === null` by the hook.
  if (error) return null;
  if (isLoading) return <LoadingState t={t} />;
  if (!data || data.total_closed_pairs <= 0) return <EmptyState t={t} />;
  return <LoadedMirror data={data} t={t} />;
}
