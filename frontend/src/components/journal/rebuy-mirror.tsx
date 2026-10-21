"use client";

/**
 * Rebuy Mirror — "the price when you came back" panel.
 *
 * For names the user SOLD and then bought again within the backend's window
 * (`rebuy_window_days`, 90), it shows how many times that happened, how many
 * of those later buys were priced above / below the sale price, the median
 * gap in days, and the median price change between the two fills. It is the
 * one backtest-shaped question this app can answer without vendor prices:
 * both prices are the user's own fills of the same ticker (no market data,
 * no FX), so the panel renders while `MARKET_DATA_DISPLAY_ENABLED` is off.
 *
 * Same posture as averaging-down-mirror.tsx, whose shell / states / editorial
 * primitives this reuses:
 *   - It is a MIRROR, not a verdict. Coming back higher is never called a
 *     mistake and coming back lower is never called a skill.
 *   - Numbers render in neutral ivory (NumDisplay tone="neu"). Carmine/indigo
 *     price-direction colours are deliberately NOT used — even for the signed
 *     median change — so the panel passes no judgement.
 *   - No score, grade, badge, gauge, percentile or "health" number.
 *   - Too few pairs → the calm empty state, no fabricated count. No call-to-
 *     action anywhere (a CTA would nudge trading = 권유 risk).
 *
 * The shared behavior-mirror disclaimer is mounted ONCE at the foot of the
 * mirror section in journal/page.tsx — not inline here.
 */

import { motion } from "motion/react";
import { useT, useLocale } from "@/lib/locale";
import { useRebuyMirror } from "@/lib/hooks";
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
import type { RebuyMirrorResponse } from "@/lib/types";

/** Em-dash sentinel — mirrors lib/format.ts missing-value convention. */
export const EM_DASH = "—";

/** Minimum sale → later-buy pairs before numbers are shown. */
export const MIN_PAIRS = 3;

/* ────────────────────────────────────────────────────────────────────────
 * Pure view-model — unit-testable without a DOM. Never produces a score or
 * grade; only counts, two medians, neutral per-ticker rows and sentinels.
 * ────────────────────────────────────────────────────────────────────── */

export interface RebuyTickerView {
  ticker: string;
  /** Resolved display name (never a naked ticker). */
  name: string;
  rebuy: string;
  higher: string;
  lower: string;
}

export interface RebuyMirrorView {
  enough: boolean;
  /** Window echoed from the backend, for the copy ("90"). */
  windowDays: string;
  rebuy: string;
  higher: string;
  lower: string;
  /** Rounded whole days, unit-less ("12"), or em-dash. */
  gapDays: string;
  /** Signed one-decimal percent ("+4.2%", "-3%", "0%"), or em-dash. */
  change: string;
  tickers: RebuyTickerView[];
}

export function computeRebuyView(data: RebuyMirrorResponse): RebuyMirrorView {
  const enough =
    data.sufficient_data &&
    typeof data.rebuy_count === "number" &&
    data.rebuy_count >= MIN_PAIRS;

  const fmtCount = (n: number | null | undefined): string =>
    enough && typeof n === "number" && Number.isFinite(n) ? String(n) : EM_DASH;

  const gap = data.median_gap_days;
  const gapDays =
    enough && typeof gap === "number" && Number.isFinite(gap)
      ? String(Math.round(gap))
      : EM_DASH;

  // Keep the raw sign — a lower rebuy stays negative, never abs().
  const chg = data.median_price_change_pct;
  let change = EM_DASH;
  if (enough && typeof chg === "number" && Number.isFinite(chg)) {
    const rounded = Math.round(chg * 10) / 10;
    change = `${rounded > 0 ? "+" : ""}${rounded}%`;
  }

  const tickers: RebuyTickerView[] = enough
    ? (data.by_ticker ?? []).map((row) => ({
        ticker: row.ticker,
        name: displayName(row.ticker, row.name),
        rebuy: String(row.rebuy_count),
        higher: String(row.higher_count),
        lower: String(row.lower_count),
      }))
    : [];

  return {
    enough,
    windowDays: String(data.rebuy_window_days ?? 90),
    rebuy: fmtCount(data.rebuy_count),
    higher: fmtCount(data.higher_count),
    lower: fmtCount(data.lower_count),
    gapDays,
    change,
    tickers,
  };
}

/* ────────────────────────────────────────────────────────────────────────
 * Shell + states
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
      className="rounded-[var(--pq-radius-card)] border p-5 sm:p-6"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
      aria-label={t("journal.rebuyMirror.heading")}
    >
      <RuledKicker>{t("journal.rebuyMirror.kicker")}</RuledKicker>
      <EditorialHead as="h2" size={26} tone="ivory" className="mt-3">
        {t("journal.rebuyMirror.heading")}
      </EditorialHead>
      {children}
    </motion.section>
  );
}

function LoadingState({ t }: { t: (k: string) => string }) {
  return (
    <MirrorShell t={t}>
      <div className="mt-5 grid grid-cols-3 gap-3" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-[var(--pq-radius-card)]"
            style={{ background: "var(--pq-ivory-line-faint)" }}
          />
        ))}
      </div>
    </MirrorShell>
  );
}

/** Too few pairs → calm, NO call-to-action (avoid nudging a trade). */
function EmptyState({
  t,
  windowDays,
}: {
  t: (k: string) => string;
  windowDays: string;
}) {
  return (
    <MirrorShell t={t}>
      <EditorialHead as="p" size={18} tone="muted" className="mt-4">
        {t("journal.rebuyMirror.emptyTitle")}
      </EditorialHead>
      <Caption className="mt-2 max-w-md">
        {t("journal.rebuyMirror.emptyDesc").replace("{window}", windowDays)}
      </Caption>
    </MirrorShell>
  );
}

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

function LoadedMirror({
  data,
  t,
}: {
  data: RebuyMirrorResponse;
  t: (k: string) => string;
}) {
  const view = computeRebuyView(data);
  const daysUnit = t("journal.rebuyMirror.daysUnit");

  return (
    <MirrorShell t={t}>
      <div className="mt-5 grid grid-cols-3 gap-3 sm:gap-5">
        <CountCell label={t("journal.rebuyMirror.rebuyLabel")} value={view.rebuy} />
        <CountCell label={t("journal.rebuyMirror.higherLabel")} value={view.higher} />
        <CountCell label={t("journal.rebuyMirror.lowerLabel")} value={view.lower} />
      </div>

      <div className="mt-6 flex flex-col gap-px">
        <StatRow
          label={t("journal.rebuyMirror.gapLabel")}
          value={view.gapDays === EM_DASH ? EM_DASH : `${view.gapDays}${daysUnit}`}
        />
        <StatRow label={t("journal.rebuyMirror.changeLabel")} value={view.change} />
      </div>

      {view.enough && view.tickers.length > 0 && (
        <div className="mt-6">
          <FieldLabel tone="bronze">{t("journal.rebuyMirror.byTickerLabel")}</FieldLabel>
          <div className="mt-3 flex flex-col gap-px">
            {view.tickers.map((row) => (
              <StatRow
                key={row.ticker}
                label={row.name}
                value={t("journal.rebuyMirror.tickerRow")
                  .replace("{rebuy}", row.rebuy)
                  .replace("{higher}", row.higher)
                  .replace("{lower}", row.lower)}
              />
            ))}
          </div>
        </div>
      )}

      <Caption className="mt-4 max-w-lg">
        {t("journal.rebuyMirror.framing").replace("{window}", view.windowDays)}
      </Caption>
    </MirrorShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Public component — own SWR + own loading/error boundary so a mirror failure
 * NEVER takes down the Decision Journal feed beneath it.
 * ────────────────────────────────────────────────────────────────────── */

export function RebuyMirror() {
  const t = useT();
  useLocale();
  const { data, isLoading, error } = useRebuyMirror();

  if (error) return null;
  if (isLoading) return <LoadingState t={t} />;
  if (!data || !data.sufficient_data) {
    return <EmptyState t={t} windowDays={String(data?.rebuy_window_days ?? 90)} />;
  }
  return <LoadedMirror data={data} t={t} />;
}
