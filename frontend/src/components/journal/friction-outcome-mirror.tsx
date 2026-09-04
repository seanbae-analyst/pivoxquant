"use client";

/**
 * Friction-Outcome Mirror — what the *pause* actually led to.
 *
 * The other five mirrors read TradeHistory: what you did. This one reads
 * PreTradeReflection alongside it, so it is the only surface in the product
 * that can see the trade that did **not** happen. Brokerages and MyData know
 * executions; nobody but this record knows what you almost bought.
 *
 * Until 2026-09-02 `services/pre_trade/friction_outcome.py` was fully built
 * and tested with **zero** consumers except a CLI script — the most analytical
 * thing in the codebase, invisible to every user. This component is its face.
 *
 * Posture — identical to concentration-mirror.tsx / holding-mirror.tsx:
 *   - No score, grade, index, star, badge, gauge, percentile.
 *   - The words 개선 / 악화 / 잘함 / 못함 / 효과 있음 are NEVER surfaced. The
 *     module deliberately computes no verdict and this view adds none.
 *   - 회피 vs 지연 is a *count split*, not a judgement. A cancellation that
 *     later became a purchase is reported as a delay, without saying which is
 *     better — because the data cannot say.
 *
 * ⚠️ Two things must never be dropped from the render:
 *   1. `realised.comparable === false` → the two distributions are NOT shown.
 *      The service refuses the comparison below `min_group_n`; honouring that
 *      refusal is the whole point of it existing.
 *   2. `caveats.not_randomised` → the user chooses which trades to pause, so
 *      the two groups are not equivalent. Rendering the numbers without this
 *      turns an observation into an implied causal claim (자본시장법 경계).
 *
 * Legal: 자본시장법 (no 추천/조언) + PIPA §23 (no profiling/score) +
 * DECISIONS.md (AI 점수화 폐기). The shared behaviour-mirror disclaimer is
 * mounted once at the foot of the mirror section in journal/page.tsx — not
 * inline here.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT, no italic.
 * Mobile-first (375px): every row stacks, no horizontal scroll.
 *
 * Motion + shell match the five sibling mirrors exactly: `animate="visible"`
 * on mount (NOT `whileInView`) inside the same bordered card treatment. The
 * first draft used a scroll-triggered reveal and no border, which both looked
 * wrong beside its five neighbours in one section and broke mirror-render's
 * jsdom mount — jsdom has no IntersectionObserver, which is exactly why that
 * suite exists.
 */

import { motion } from "motion/react";
import { useFrictionOutcome } from "@/lib/hooks";
import { fadeUp } from "@/lib/motion";
import {
  RuledKicker,
  EditorialHead,
  NumDisplay,
  FieldLabel,
  Caption,
} from "@/components/ui/editorial";
import { fmtPctSignedMinus } from "@/lib/format";
import type { FrictionOutcomeResponse } from "@/lib/types";

/* ────────────────────────────────────────────────────────────────────────
 * Pure view-model — declarative render path, unit-testable without a DOM.
 * Produces counts and pre-formatted strings only; never a label of quality.
 * ────────────────────────────────────────────────────────────────────── */

export interface FrictionOutcomeView {
  /** False → render the empty state (no pre-trade record in the window). */
  hasData: boolean;
  started: number;
  proceeded: number;
  cancelled: number;
  open: number;
  /** Cancellations that stuck. */
  neverBought: number;
  /** Cancellations that turned out to be delays. */
  boughtLater: number;
  /** Median days from cancel to the eventual buy, when there was one. */
  medianDaysUntilBought: number | null;
  /** True only when the service itself allowed the comparison. */
  showDistributions: boolean;
  withFriction: { n: number; median: number | null };
  withoutFriction: { n: number; median: number | null };
  minGroupN: number;
  attributionWindowDays: number;
}

export function buildFrictionOutcomeView(
  data: FrictionOutcomeResponse | null,
): FrictionOutcomeView | null {
  if (!data || !data.ok) return null;

  const s = data.stopped;
  const c = data.cancelled_followthrough;
  const r = data.realised;

  return {
    hasData: !data.insufficient && s.started > 0,
    started: s.started,
    proceeded: s.proceeded,
    cancelled: s.cancelled,
    open: s.open,
    neverBought: c.never_bought,
    boughtLater: c.bought_later_anyway,
    medianDaysUntilBought: c.median_days_until_bought,
    // The service's refusal is authoritative — never second-guess it here.
    showDistributions: r.comparable === true,
    withFriction: { n: r.with_friction.n, median: r.with_friction.median_pct },
    withoutFriction: {
      n: r.without_friction.n,
      median: r.without_friction.median_pct,
    },
    minGroupN: r.min_group_n,
    attributionWindowDays: data.caveats.attribution_window_days,
  };
}

/* ────────────────────────────────────────────────────────────────────── */

export function FrictionOutcomeMirror() {
  const { data, isLoading, error } = useFrictionOutcome();
  const view = buildFrictionOutcomeView(data);

  // Soft-fail like the sibling mirrors: one mirror going quiet must not take
  // the section down.
  if (error) return null;

  if (isLoading) {
    return (
      <div className="py-6" aria-busy="true">
        <div
          className="pq-skeleton-dark rounded-sm"
          style={{ height: 2, width: 120 }}
        />
      </div>
    );
  }

  // null data (no rows yet, or a 404 soft-empty) renders the EMPTY state, not
  // nothing — that is the shared contract with the five sibling mirrors, and
  // mirror-render.test.tsx pins it. Bailing to null here made this mirror
  // silently vanish on a fresh account while its five neighbours showed their
  // empty states.
  if (!view || !view.hasData) {
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
        aria-label="멈춤의 귀결"
      >
        <RuledKicker>멈춤의 귀결</RuledKicker>
        <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
          아직 되비출 멈춤이 없습니다.
        </EditorialHead>
        {/* No CTA — nudging a pre-trade record here would be a nudge toward a
            trade. The empty state stays calm and does nothing. */}
        <Caption>
          사기 전에 기록을 남기면, 그 기록이 무엇으로 이어졌는지 여기에 쌓입니다.
        </Caption>
      </motion.section>
    );
  }

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
      aria-label="멈춤의 귀결"
    >
      <RuledKicker>멈춤의 귀결</RuledKicker>
      <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
        멈춘 {view.started}번은 무엇이 되었나.
      </EditorialHead>

      {/* ── how the pauses resolved ─────────────────────────────── */}
      <div className="mt-5 grid grid-cols-3 gap-4 sm:gap-6">
        <div>
          <FieldLabel>진행</FieldLabel>
          <NumDisplay tone="neu">{view.proceeded}</NumDisplay>
        </div>
        <div>
          <FieldLabel>취소</FieldLabel>
          <NumDisplay tone="neu">{view.cancelled}</NumDisplay>
        </div>
        <div>
          <FieldLabel>미결</FieldLabel>
          <NumDisplay tone="neu">{view.open}</NumDisplay>
        </div>
      </div>

      {/* ── avoidance vs delay ──────────────────────────────────── */}
      {view.cancelled > 0 && (
        <div
          className="mt-6 pt-5"
          style={{ borderTop: "0.5pt solid var(--pq-ivory-line)" }}
        >
          <FieldLabel>취소한 뒤</FieldLabel>
          <p
            className="mt-2 font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.7,
              color: "rgba(245,240,232,0.78)",
              wordBreak: "keep-all",
            }}
          >
            {view.cancelled}건 중 {view.neverBought}건은 그 뒤로 사지 않았고,{" "}
            {view.boughtLater}건은 결국 샀습니다
            {view.medianDaysUntilBought !== null && (
              <> (중앙값 {view.medianDaysUntilBought}일 뒤)</>
            )}
            .
          </p>
          {/* Naming the distinction is the observation. Ranking them is not
              ours to do — the data cannot say which was better. */}
          <Caption>
            취소 이후 {view.attributionWindowDays}일 안의 같은 종목 매수를 그
            취소에 귀속한 추정입니다. 같은 종목을 자주 거래하면 실제와 다를 수
            있습니다.
          </Caption>
        </div>
      )}

      {/* ── the two distributions, only if the service allowed it ── */}
      <div
        className="mt-6 pt-5"
        style={{ borderTop: "0.5pt solid var(--pq-ivory-line)" }}
      >
        <FieldLabel>실현 수익률 분포</FieldLabel>
        {view.showDistributions ? (
          <>
            <div className="mt-3 grid grid-cols-2 gap-4 sm:gap-6">
              <div>
                <Caption>멈춤을 거친 매수 · {view.withFriction.n}건</Caption>
                <NumDisplay tone="neu">
                  {fmtPctSignedMinus(view.withFriction.median, 1)}
                </NumDisplay>
              </div>
              <div>
                <Caption>
                  거치지 않은 매수 · {view.withoutFriction.n}건
                </Caption>
                <NumDisplay tone="neu">
                  {fmtPctSignedMinus(view.withoutFriction.median, 1)}
                </NumDisplay>
              </div>
            </div>
            {/* The caveat travels with the numbers, always. Without it these
                two figures read as cause and effect, which they are not. */}
            <Caption>
              중앙값입니다. 어느 거래에 멈춤을 쓸지는 당신이 고르므로 두 무리는
              애초에 같은 조건이 아닙니다 — 나란히 놓을 뿐, 멈춤이 수익률을
              바꿨다는 뜻이 아닙니다.
            </Caption>
          </>
        ) : (
          <Caption>
            비교하기에 아직 표본이 적습니다. 두 무리가 각각{" "}
            {view.minGroupN}건을 넘으면 나란히 보여드립니다.
          </Caption>
        )}
      </div>
    </motion.section>
  );
}

export default FrictionOutcomeMirror;
