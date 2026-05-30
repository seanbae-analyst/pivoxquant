"use client";

/**
 * Concentration-Mirror — the cost-basis composition "mirror" panel.
 *
 * A neutral, factual statement of how much of the user's OWN open portfolio
 * sits in their single largest holding, measured at 평균매입가 (average cost,
 * NOT market price). It is a MIRROR, not a verdict — the exact same posture as
 * holding-mirror.tsx, whose MirrorShell / EmptyState / editorial primitives /
 * DisclaimerBanner pattern this component reuses verbatim:
 *
 *   - No score, grade, index, ratio, star, badge, gauge, or percentile.
 *   - The words 집중 위험 / 과집중 / 분산 필요 / 위험도 are NEVER surfaced. The
 *     kicker is the neutral "보유 비중 현황" (holdings composition), never
 *     "집중 위험도".
 *   - The weight (e.g. "67.3%") renders in neutral ivory (NumDisplay
 *     tone="neu"). Carmine/indigo (price-direction colours) are deliberately
 *     NOT used — the mirror passes no judgement.
 *   - `cost_basis_note` ("평균매입가 기준 (시장가 아님)") is shown verbatim so the
 *     figure is never mistaken for a live market-value weight.
 *   - Zero holdings → a calm empty state with NO call-to-action (a CTA here
 *     would nudge a trade = 권유 risk). A single holding naturally reports
 *     100% — shown as plain fact, no warning.
 *
 * Legal posture: 자본시장법 (no 추천/조언) + PIPA §23 (no profiling/score) +
 * DECISIONS.md (AI 점수화 폐기). The behavior-mirror disclaimer (not a
 * medical/psychological service, not a recommendation) is mounted ONCE at the
 * foot of the mirror SECTION in journal/page.tsx — shared across all mirrors —
 * not inline here, so a screen with N mirrors shows a single legal banner
 * (2026-05-30).
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT. Mobile-first (375px):
 * the count + weight stack cleanly with no horizontal scroll.
 */

import { motion } from "motion/react";
import { useT, useLocale } from "@/lib/locale";
import { useConcentrationMirror } from "@/lib/hooks";
import { fadeUp } from "@/lib/motion";
import {
  RuledKicker,
  EditorialHead,
  NumDisplay,
  FieldLabel,
  Caption,
  StatRow,
} from "@/components/ui/editorial";
import type { ConcentrationMirrorResponse } from "@/lib/types";

/** Em-dash sentinel — mirrors lib/format.ts missing-value convention. */
export const EM_DASH = "—";

/* ────────────────────────────────────────────────────────────────────────
 * Pure view-model — keeps the render path declarative and unit-testable
 * without a DOM. NEVER produces a score/grade/label; only a pre-formatted
 * weight string, the holding count, and the largest holding's name/note.
 * ────────────────────────────────────────────────────────────────────── */

export interface ConcentrationView {
  /** True only when the backend has a meaningful cost-basis composition. */
  enough: boolean;
  /** Holding count (positive shares × positive avg cost). */
  count: number;
  /** Largest holding's display name, or the em-dash sentinel when absent. */
  largest: string;
  /** Pre-formatted weight: "<pct>%" when stable, else the em-dash sentinel. */
  weight: string;
  /** Cost-basis clarifier — backend value preferred, i18n fallback. */
  note: string;
}

/**
 * Compute the neutral fact view-model from the backend payload.
 * @param data       locked ConcentrationMirrorResponse shape
 * @param noteFallback i18n cost-basis note used only if the backend omits one
 */
export function computeConcentrationView(
  data: ConcentrationMirrorResponse,
  noteFallback: string,
): ConcentrationView {
  // "Enough" requires the backend flag AND a finite weight to display. A null
  // weight (insufficient / zero-cost portfolio) renders an em-dash, never a 0.
  const pct = data.max_weight_pct;
  const enough =
    data.sufficient_data && pct != null && Number.isFinite(pct);

  const weight = enough ? `${pct}%` : EM_DASH;
  const largest =
    enough && data.largest_ticker ? data.largest_ticker : EM_DASH;

  // Prefer the backend's own clarifier verbatim (oversight guard) — fall back
  // to the localised string only if the backend omitted it.
  const note =
    typeof data.cost_basis_note === "string" &&
    data.cost_basis_note.trim().length > 0
      ? data.cost_basis_note
      : noteFallback;

  return {
    enough,
    count: data.ticker_count ?? 0,
    largest,
    weight,
    note,
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
      aria-label={t("journal.concentrationMirror.kicker")}
    >
      <RuledKicker>{t("journal.concentrationMirror.kicker")}</RuledKicker>
      <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
        {t("journal.concentrationMirror.heading")}
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
      <div
        className="mt-5 h-28 animate-pulse rounded-[2px]"
        style={{ background: "var(--pq-ivory-line-faint)" }}
        aria-hidden="true"
      />
    </MirrorShell>
  );
}

/** Zero holdings → calm, NO call-to-action (a CTA would nudge a trade). */
function EmptyState({ t }: { t: (k: string) => string }) {
  return (
    <MirrorShell t={t}>
      <EditorialHead as="p" size={18} tone="muted" className="mt-4">
        {t("journal.concentrationMirror.emptyTitle")}
      </EditorialHead>
      <Caption className="mt-2 max-w-md">
        {t("journal.concentrationMirror.emptyDesc")}
      </Caption>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Loaded — the factual composition. The weight is the protagonist
 * (large NumDisplay, neutral ivory); the holding name + count sit beside it
 * as plain facts. No bar, no colour judgement, no "위험/분산" framing.
 * ────────────────────────────────────────────────────────────────────── */

function LoadedMirror({
  data,
  t,
}: {
  data: ConcentrationMirrorResponse;
  t: (k: string) => string;
}) {
  const view = computeConcentrationView(
    data,
    t("journal.concentrationMirror.costBasisNote"),
  );

  return (
    <MirrorShell t={t}>
      <div className="mt-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        {/* Largest holding — name + lead-in, the subject of the weight. */}
        <div className="min-w-0">
          <FieldLabel tone="bronze">
            {t("journal.concentrationMirror.factLead")}
          </FieldLabel>
          <div className="mt-2">
            <EditorialHead
              as="p"
              size={26}
              tone="ivory"
              style={{ wordBreak: "keep-all" }}
            >
              {view.largest}
            </EditorialHead>
          </div>
        </div>

        {/* Weight — the protagonist number, neutral ivory (no judgement). */}
        <div className="min-w-0 text-right">
          <FieldLabel tone="bronze">
            {t("journal.concentrationMirror.factWeightLabel")}
          </FieldLabel>
          <div className="mt-2">
            <NumDisplay size={44} tone="neu">
              {view.weight}
            </NumDisplay>
          </div>
        </div>
      </div>

      {/* Cost-basis clarifier — backend wording verbatim (oversight guard). */}
      <Caption className="mt-3">{view.note}</Caption>

      {/* Holding count — plain fact, hairline-separated. */}
      <div className="mt-5">
        <StatRow
          label={t("journal.concentrationMirror.factCountLabel")}
          value={`${view.count.toLocaleString()}${t(
            "journal.concentrationMirror.factCountUnit",
          )}`}
        />
      </div>

      {/* Neutral framing line — "we mirror, we do not judge." */}
      <Caption className="mt-4 max-w-lg">
        {t("journal.concentrationMirror.framing")}
      </Caption>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Public component — own SWR + own loading/error boundary so a mirror failure
 * NEVER takes down the Decision Journal feed beneath it.
 * ────────────────────────────────────────────────────────────────────── */

export function ConcentrationMirror() {
  const t = useT();
  // Locale subscription keeps copy re-rendering on language switch.
  useLocale();
  const { data, isLoading, error } = useConcentrationMirror();

  // Hard failure (5xx / network) → render nothing rather than a broken card.
  // A 404 (backend not yet wired) is normalised to `data === null` by the hook.
  if (error) return null;
  if (isLoading) return <LoadingState t={t} />;
  if (!data || !data.sufficient_data || data.ticker_count <= 0) {
    return <EmptyState t={t} />;
  }
  return <LoadedMirror data={data} t={t} />;
}
