"use client";

/**
 * Turnover Mirror — the trade-activity "mirror" panel.
 *
 * A neutral reflection of HOW ACTIVE the user's own trading was over the
 * window: the BUY/SELL fill count, and the gross traded value summed PER
 * CURRENCY. It is a MIRROR, not a verdict — the same posture as
 * profit-loss-mirror.tsx, whose MirrorShell / states / editorial primitives
 * / shared DisclaimerBanner pattern this component reuses verbatim:
 *
 *   - There is deliberately NO turnover ratio / percentage. A ratio needs a
 *     live portfolio-valuation denominator (breaking determinism) and a
 *     KRW/USD mixed denominator is meaningless. We show the absolute fill
 *     count + per-currency gross value only.
 *   - No score, grade, star, badge, gauge, percentile, or "health" number.
 *   - The words 회전율 / 과잉거래 / 과속 / 잦다 / 많다 / 줄이세요 / 진단 / 치료
 *     are NEVER surfaced. Labels are the neutral "매매 빈도 / 매수·매도 횟수 /
 *     통화별 거래대금 / 평균 보유 기간".
 *   - Efficacy statistics (Barber&Odean, KCMI 회전율, etc.) are NEVER cited.
 *   - Counts/value render in neutral ivory mono (NumDisplay tone="neu").
 *     Carmine/indigo (price-direction colours) are deliberately NOT used so
 *     the mirror passes no judgement.
 *   - <min fills → em-dash sentinels + a "not enough yet" note (no fabricated
 *     count). Zero trades → a calm empty state with NO call-to-action (a CTA
 *     here would nudge trading = 권유 risk).
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
import { useTurnoverMirror } from "@/lib/hooks";
import { fadeUp } from "@/lib/motion";
import { fmtMoneyCompact } from "@/lib/format";
import {
  RuledKicker,
  EditorialHead,
  NumDisplay,
  FieldLabel,
  Caption,
  StatRow,
} from "@/components/ui/editorial";
import type { TurnoverMirrorResponse } from "@/lib/types";

/** Em-dash sentinel — mirrors lib/format.ts missing-value convention. */
export const EM_DASH = "—";

/** Minimum fills before counts are shown as "stable". */
export const MIN_TRADES = 8;

/* ────────────────────────────────────────────────────────────────────────
 * Pure view-model — keeps the render path declarative and unit-testable
 * without a DOM. NEVER produces a score/grade/ratio; only counts, per-currency
 * value strings, hold days, and sentinels.
 * ────────────────────────────────────────────────────────────────────── */

export interface TurnoverCurrencyView {
  currency: string;
  /** Pre-formatted gross value: "KRW 3.0억" / "USD 4.0K", currency-aware. */
  gross: string;
  /** Pre-formatted fill count for this currency: "<n>". */
  count: string;
}

export interface TurnoverMirrorView {
  enough: boolean;
  /** Pre-formatted total fill count, or em-dash when not stable. */
  trades: string;
  /** Pre-formatted buy count, or em-dash. */
  buys: string;
  /** Pre-formatted sell count, or em-dash. */
  sells: string;
  /** Pre-formatted average hold days ("<n><unit>"), or em-dash. */
  hold: string;
  /** Per-currency rows (empty when not stable). */
  currencies: TurnoverCurrencyView[];
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
 * Format one currency's gross value. USD/KRW get the locale-aware myriad/
 * SI compact scale; any other currency falls back to a grouped integer with
 * the raw currency code prefix (still never FX-converted).
 */
function fmtGross(currency: string, value: number): string {
  const c = currency.toUpperCase();
  if (c === "USD" || c === "KRW") {
    return fmtMoneyCompact(value, c);
  }
  const n = Number.isFinite(value) ? Math.round(value) : 0;
  return `${c} ${n.toLocaleString()}`;
}

/**
 * Compute the neutral view model from the backend payload.
 * @param data     locked TurnoverMirrorResponse shape
 * @param daysUnit i18n unit suffix ("일" / "d")
 */
export function computeTurnoverView(
  data: TurnoverMirrorResponse,
  daysUnit: string,
): TurnoverMirrorView {
  const enough =
    data.sufficient_data && data.trade_count >= MIN_TRADES;

  const fmtCount = (n: number | null | undefined): string =>
    enough && typeof n === "number" && Number.isFinite(n)
      ? String(n)
      : EM_DASH;

  const holdDays = pick(data.median_hold_days, data.mean_hold_days);
  const fmtHold = (d: number | null): string =>
    enough && d != null && Number.isFinite(d)
      ? `${Math.round(d)}${daysUnit}`
      : EM_DASH;

  const currencies: TurnoverCurrencyView[] = enough
    ? (data.by_currency ?? []).map((row) => ({
        currency: row.currency,
        gross: fmtGross(row.currency, row.gross_value),
        count: String(row.trade_count),
      }))
    : [];

  return {
    enough,
    trades: fmtCount(data.trade_count),
    buys: fmtCount(data.buy_count),
    sells: fmtCount(data.sell_count),
    hold: fmtHold(holdDays),
    currencies,
  };
}

/* ────────────────────────────────────────────────────────────────────────
 * Shell — kicker + heading + framed card body. Mirrors profit-loss-mirror.tsx.
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
      aria-label={t("journal.turnoverMirror.kicker")}
    >
      <RuledKicker>{t("journal.turnoverMirror.kicker")}</RuledKicker>
      <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
        {t("journal.turnoverMirror.heading")}
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

/** Zero trades → calm, NO call-to-action (avoid nudging a trade). */
function EmptyState({ t }: { t: (k: string) => string }) {
  return (
    <MirrorShell t={t}>
      <EditorialHead as="p" size={18} tone="muted" className="mt-4">
        {t("journal.turnoverMirror.emptyTitle")}
      </EditorialHead>
      <Caption className="mt-2 max-w-md">
        {t("journal.turnoverMirror.emptyDesc")}
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
  data: TurnoverMirrorResponse;
  t: (k: string) => string;
}) {
  const view = computeTurnoverView(
    data,
    t("journal.turnoverMirror.daysUnit"),
  );

  return (
    <MirrorShell t={t}>
      {/* Primary counts row — total fills, buys, sells, neutral ivory. */}
      <div className="mt-5 grid grid-cols-3 gap-3 sm:gap-5">
        <CountCell
          label={t("journal.turnoverMirror.tradesLabel")}
          value={view.trades}
        />
        <CountCell
          label={t("journal.turnoverMirror.buysLabel")}
          value={view.buys}
        />
        <CountCell
          label={t("journal.turnoverMirror.sellsLabel")}
          value={view.sells}
        />
      </div>

      {/* Insufficient-data note — sits in place of stable counts. */}
      {!view.enough && (
        <Caption className="mt-4 max-w-md">
          {t("journal.turnoverMirror.insufficient")}
        </Caption>
      )}

      {/* Per-currency gross traded value — only when we have stable data. */}
      {view.enough && view.currencies.length > 0 && (
        <div className="mt-6">
          <FieldLabel tone="bronze">
            {t("journal.turnoverMirror.grossLabel")}
          </FieldLabel>
          <div className="mt-3 flex flex-col gap-px">
            {view.currencies.map((row) => (
              <StatRow
                key={row.currency}
                label={t("journal.turnoverMirror.currencyRow")
                  .replace("{currency}", row.currency)
                  .replace("{count}", row.count)}
                value={row.gross}
              />
            ))}
          </div>
        </div>
      )}

      {/* Average hold days for context — only when stable + closed pairs. */}
      {view.enough && view.hold !== EM_DASH && (
        <div className="mt-5">
          <StatRow
            label={t("journal.turnoverMirror.avgHold")}
            value={view.hold}
          />
        </div>
      )}

      {/* Neutral framing line — "we mirror, we do not judge." */}
      <Caption className="mt-4 max-w-lg">
        {t("journal.turnoverMirror.framing")}
      </Caption>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Public component — own SWR + own loading/error boundary so a mirror failure
 * NEVER takes down the Decision Journal feed beneath it.
 * ────────────────────────────────────────────────────────────────────── */

export function TurnoverMirror() {
  const t = useT();
  // Locale subscription keeps copy/units re-rendering on language switch.
  useLocale();
  const { data, isLoading, error } = useTurnoverMirror();

  // Hard failure (5xx / network) → render nothing rather than a broken card.
  // A 404 (backend not yet wired) is normalised to `data === null` by the hook.
  if (error) return null;
  if (isLoading) return <LoadingState t={t} />;
  if (!data || data.trade_count <= 0) return <EmptyState t={t} />;
  return <LoadedMirror data={data} t={t} />;
}
