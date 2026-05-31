"use client";

/**
 * Averaging-Down Mirror — the follow-on-add "mirror" panel.
 *
 * A neutral reflection of HOW the user's own adds-to-an-already-held-position
 * fell relative to that position's running average cost at the moment of each
 * add: how many follow-on buys, and how many of those landed BELOW / ABOVE /
 * AT the running average. It is a MIRROR, not a verdict — the same posture as
 * turnover-mirror.tsx, whose MirrorShell / states / editorial primitives /
 * shared DisclaimerBanner pattern this component reuses verbatim:
 *
 *   - There is deliberately NO ratio / percentage. We show absolute integer
 *     counts only — never "X% of your adds were below average".
 *   - No score, grade, star, badge, gauge, percentile, or "health" number.
 *   - The slang 물타기 — which carries a judgement — is NEVER surfaced. Nor is
 *     과도 / 손실 / 위험 / 진단 / 치료 / 편향. Labels are the neutral
 *     "추가 매수 / 평균가 아래 / 평균가 위".
 *   - We never claim adding below (or above) the average is good or bad, and
 *     never assert a cause ("물타기가 손실을 키운다"). The mirror counts; the
 *     interpretation is the user's. (research_cbt_bias_model.md.)
 *   - Counts render in neutral ivory mono (NumDisplay tone="neu"). Carmine/
 *     indigo (price-direction colours) are deliberately NOT used so the mirror
 *     passes no judgement.
 *   - <min follow-on adds → em-dash sentinels + a "not enough yet" note (no
 *     fabricated count). Zero trades → a calm empty state with NO call-to-
 *     action (a CTA here would nudge trading = 권유 risk).
 *
 * Legal posture: 자본시장법 (no 추천/조언) + PIPA §23 (no profiling/score) +
 * DECISIONS.md (AI 점수화 폐기). The behavior-mirror disclaimer is mounted ONCE
 * at the foot of the mirror SECTION in journal/page.tsx — shared across all
 * mirrors — not inline here.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT. Mobile-first.
 */

import { motion } from "motion/react";
import { useT, useLocale } from "@/lib/locale";
import { useAveragingDownMirror } from "@/lib/hooks";
import { fadeUp } from "@/lib/motion";
import { displayName } from "@/lib/format";
import {
  RuledKicker,
  EditorialHead,
  NumDisplay,
  FieldLabel,
  Caption,
  StatRow,
} from "@/components/ui/editorial";
import type { AveragingDownMirrorResponse } from "@/lib/types";

/** Em-dash sentinel — mirrors lib/format.ts missing-value convention. */
export const EM_DASH = "—";

/** Minimum follow-on adds before counts are shown as "stable". */
export const MIN_FOLLOW_ON = 3;

/* ────────────────────────────────────────────────────────────────────────
 * Pure view-model — keeps the render path declarative and unit-testable
 * without a DOM. NEVER produces a score/grade/ratio; only counts, neutral
 * per-ticker rows, and sentinels.
 * ────────────────────────────────────────────────────────────────────── */

export interface AvgDownTickerView {
  ticker: string;
  /** Resolved display name (never a naked ticker). */
  name: string;
  /** Pre-formatted follow-on count for this ticker: "<n>". */
  followOn: string;
  /** Pre-formatted below-average count: "<n>". */
  below: string;
  /** Pre-formatted above-average count: "<n>". */
  above: string;
}

export interface AveragingDownMirrorView {
  enough: boolean;
  /** Pre-formatted total follow-on count, or em-dash when not stable. */
  followOn: string;
  /** Pre-formatted below-average count, or em-dash. */
  below: string;
  /** Pre-formatted above-average count, or em-dash. */
  above: string;
  /** Pre-formatted at-average count, or em-dash. */
  flat: string;
  /** Per-ticker rows (empty when not stable). */
  tickers: AvgDownTickerView[];
}

/**
 * Compute the neutral view model from the backend payload. Pure — no DOM,
 * no network. Resolves ticker display names so a naked code is never shown.
 */
export function computeAveragingDownView(
  data: AveragingDownMirrorResponse,
): AveragingDownMirrorView {
  const enough =
    data.sufficient_data &&
    typeof data.follow_on_count === "number" &&
    data.follow_on_count >= MIN_FOLLOW_ON;

  const fmtCount = (n: number | null | undefined): string =>
    enough && typeof n === "number" && Number.isFinite(n)
      ? String(n)
      : EM_DASH;

  const tickers: AvgDownTickerView[] = enough
    ? (data.by_ticker ?? []).map((row) => ({
        ticker: row.ticker,
        name: displayName(row.ticker, row.name),
        followOn: String(row.follow_on),
        below: String(row.below_avg),
        above: String(row.above_avg),
      }))
    : [];

  return {
    enough,
    followOn: fmtCount(data.follow_on_count),
    below: fmtCount(data.below_avg_count),
    above: fmtCount(data.above_avg_count),
    flat: fmtCount(data.flat_count),
    tickers,
  };
}

/* ────────────────────────────────────────────────────────────────────────
 * Shell — kicker + heading + framed card body. Mirrors turnover-mirror.tsx.
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
      aria-label={t("journal.averagingDownMirror.kicker")}
    >
      <RuledKicker>{t("journal.averagingDownMirror.kicker")}</RuledKicker>
      <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
        {t("journal.averagingDownMirror.heading")}
      </EditorialHead>
      {children}
    </motion.section>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * States
 * ────────────────────────────────────────────────────────────────────── */

function LoadingState({ t }: { t: (k: string) => string }) {
  return (
    <MirrorShell t={t}>
      <div className="mt-5 grid grid-cols-3 gap-3" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-[2px]"
            style={{ background: "var(--pq-ivory-line-faint)" }}
          />
        ))}
      </div>
    </MirrorShell>
  );
}

/** Zero follow-on history → calm, NO call-to-action (avoid nudging a trade). */
function EmptyState({ t }: { t: (k: string) => string }) {
  return (
    <MirrorShell t={t}>
      <EditorialHead as="p" size={18} tone="muted" className="mt-4">
        {t("journal.averagingDownMirror.emptyTitle")}
      </EditorialHead>
      <Caption className="mt-2 max-w-md">
        {t("journal.averagingDownMirror.emptyDesc")}
      </Caption>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * A single neutral count cell — label + protagonist number, ivory only.
 * ────────────────────────────────────────────────────────────────────── */

function CountCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <FieldLabel tone="bronze">{label}</FieldLabel>
      <div className="mt-2">
        <NumDisplay size={40} tone="neu">
          {value}
        </NumDisplay>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Loaded — sufficient OR insufficient data both render the panel; insufficient
 * shows em-dash sentinels + an explanatory note instead of fabricated numbers.
 * ────────────────────────────────────────────────────────────────────── */

function LoadedMirror({
  data,
  t,
}: {
  data: AveragingDownMirrorResponse;
  t: (k: string) => string;
}) {
  const view = computeAveragingDownView(data);

  return (
    <MirrorShell t={t}>
      {/* Primary counts row — follow-on adds, below-avg, above-avg, neutral. */}
      <div className="mt-5 grid grid-cols-3 gap-3 sm:gap-5">
        <CountCell
          label={t("journal.averagingDownMirror.followOnLabel")}
          value={view.followOn}
        />
        <CountCell
          label={t("journal.averagingDownMirror.belowLabel")}
          value={view.below}
        />
        <CountCell
          label={t("journal.averagingDownMirror.aboveLabel")}
          value={view.above}
        />
      </div>

      {/* Per-ticker breakdown — only when we have stable data. */}
      {view.enough && view.tickers.length > 0 && (
        <div className="mt-6">
          <FieldLabel tone="bronze">
            {t("journal.averagingDownMirror.byTickerLabel")}
          </FieldLabel>
          <div className="mt-3 flex flex-col gap-px">
            {view.tickers.map((row) => (
              <StatRow
                key={row.ticker}
                label={row.name}
                value={t("journal.averagingDownMirror.tickerRow")
                  .replace("{followOn}", row.followOn)
                  .replace("{below}", row.below)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Neutral framing line — "we mirror, we do not judge." */}
      <Caption className="mt-4 max-w-lg">
        {t("journal.averagingDownMirror.framing")}
      </Caption>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Public component — own SWR + own loading/error boundary so a mirror failure
 * NEVER takes down the Decision Journal feed beneath it.
 * ────────────────────────────────────────────────────────────────────── */

export function AveragingDownMirror() {
  const t = useT();
  // Locale subscription keeps copy re-rendering on language switch.
  useLocale();
  const { data, isLoading, error } = useAveragingDownMirror();

  // Hard failure (5xx / network) → render nothing rather than a broken card.
  // A 404 (backend not yet wired) is normalised to `data === null` by the hook.
  if (error) return null;
  if (isLoading) return <LoadingState t={t} />;
  // The backend nulls every count below the follow-on threshold (contract:
  // insufficient → counts None), so the client cannot distinguish "a few
  // adds" from "none" — both surface the same calm empty state. Only a stable
  // payload renders the loaded counts + per-ticker breakdown.
  if (!data || !data.sufficient_data) return <EmptyState t={t} />;
  return <LoadedMirror data={data} t={t} />;
}
