"use client";

/**
 * Editorial index card — level, 1D change, 52W range bar, 30-day sparkline.
 * Inline SVG, hand-crafted, no chart lib dependency.
 */

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import { InteractiveLineChart } from "@/components/charts/interactive-line-chart";

export interface IndexQuote {
  symbol: string;
  name: string;
  level: number;
  changePct: number;
  /**
   * 52-week extremes. Null when the upstream source cannot be trusted
   * (e.g. KIS daily-history endpoint lagging the live level by more
   * than 15% — see routes/market.py _kis_index_snapshot 2026-05-15).
   * Renderers MUST treat null as "—" and never as 0.
   */
  weekHigh52: number | null;
  weekLow52: number | null;
  /** 30-point mini series (relative movement) */
  spark: number[];
  /** How to display the level (e.g. 2_612.34 → "2,612.34") */
  format?: "en" | "kr" | "int";
  /** Unit suffix (e.g. " KRW") */
  unit?: string;
  /** ISO8601 from backend — last observation time for this level */
  observed_at?: string;
  /** Backend-flagged stale (quote older than freshness policy) */
  is_stale?: boolean;
  /**
   * Liquid ETF proxy used to source the level when the caret-prefixed
   * index symbol (e.g. ^GSPC) is gated on the FMP Starter tier.
   * Present ONLY for US indices served via ETF proxy
   * (SPY for ^GSPC, QQQ for ^IXIC, DIA for ^DJI, IWM for ^RUT, VIXY for ^VIX).
   * KR indices and FX pairs do NOT carry this field.
   *
   * When present, the UI MUST surface the proxy so the user does not
   * mistake SPY ($708) for S&P 500 level (7108). The level itself is
   * NEVER converted — a ratio would drift. See routes/market.py:529.
   */
  proxy_ticker?: string;
}

/**
 * Short descriptor text for the ETF proxy badge.
 * Example: `proxyLabel("SPY") === "via SPY · ETF proxy"`.
 * Returns empty string when no proxy (caller guards on truthiness).
 */
export function proxyLabel(proxy: string | undefined): string {
  if (!proxy) return "";
  return `via ${proxy} · ETF proxy`;
}

/**
 * Render an ISO8601 timestamp as a short relative string.
 * Observational language only — "Xs ago", "Xm ago", "just now".
 * Returns "—" when no timestamp is present.
 */
export function relativeTime(iso: string | undefined, nowMs?: number): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const now = nowMs ?? Date.now();
  const diff = Math.max(0, Math.floor((now - t) / 1000));
  if (diff < 3) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/** 1s tick for re-rendering relative timestamps. */
export function useNowTick(intervalMs = 1000): number {
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function fmtLevel(
  v: number | null | undefined,
  kind: IndexQuote["format"] = "en",
): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (kind === "int") return Math.round(v).toLocaleString("en-US");
  if (kind === "kr") {
    return v.toLocaleString("ko-KR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return v.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function RangeBar({
  low,
  high,
  level,
}: {
  low: number | null;
  high: number | null;
  level: number;
}) {
  // 2026-05-15 (verify-ux fail on PR #385 follow-up): low/high are
  // nullable now (backend nulls range_52w when upstream history lags
  // — _kis_index_snapshot 2026-05-15). When either bound is missing,
  // collapse the marker to the centre and render "—" for the bounds
  // rather than computing on null (which previously rendered as
  // "0.00 · 0.00" via the bogus `?? [0, 0]` fallback upstream).
  const haveRange =
    low != null && high != null && Number.isFinite(low) && Number.isFinite(high) && high > low;
  const pct = haveRange
    ? Math.max(0, Math.min(1, (level - (low as number)) / ((high as number) - (low as number))))
    : 0.5;
  return (
    <div>
      <div className="relative h-1 rounded-full bg-slate-100">
        <div
          className="absolute top-0 h-1 w-1 -translate-x-1/2 rounded-full bg-[var(--pq-bronze,#B8956A)]"
          style={{
            left: `${pct * 100}%`,
            opacity: haveRange ? 1 : 0.4,
          }}
        />
      </div>
      <div className="mt-1 flex justify-between text-pq-eyebrow tabular-nums text-slate-400">
        <span>{fmtLevel(low, "en")}</span>
        <span className="text-pq-eyebrow uppercase tracking-wider text-slate-400">
          52W
        </span>
        <span>{fmtLevel(high, "en")}</span>
      </div>
    </div>
  );
}

function Sparkline({ points }: { points: number[] }) {
  if (!points || points.length < 2) return null;
  const isUp = points[points.length - 1] >= points[0];
  const stroke = isUp ? "#B8956A" : "#B04A3A";

  // Back-date a synthetic series: we don't have real dates for the 30-pt
  // mini array, so we render day indices from today minus N. Observational.
  const today = new Date();
  const dated = points.map((v, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() - (points.length - 1 - i));
    return { date: d.toISOString().slice(0, 10), value: v };
  });

  return (
    <InteractiveLineChart
      points={dated}
      height={36}
      color={stroke}
      compact
      ariaLabel="30-day sparkline"
      valueFormatter={(val) => val.toFixed(2)}
      dateFormatter={(d) => {
        const parsed = new Date(d);
        return isNaN(parsed.getTime())
          ? d
          : parsed.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      }}
    />
  );
}

export function IndexCard({ quote }: { quote: IndexQuote }) {
  const tone =
    quote.changePct > 0
      ? "text-[var(--pq-bronze,#B8956A)]"
      : quote.changePct < 0
        ? "text-[#B04A3A]"
        : "text-slate-500";
  const now = useNowTick(1000);
  const rel = relativeTime(quote.observed_at, now);
  const stale = Boolean(quote.is_stale);
  return (
    <article className="border-t border-slate-200 pt-4">
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <p className="text-pq-eyebrow uppercase tracking-widest text-slate-400">
            {quote.symbol}
          </p>
          <h3 className="font-serif text-base font-bold text-slate-900 truncate">
            {quote.name}
          </h3>
          {quote.proxy_ticker && (
            <p
              className="mt-0.5 font-mono text-pq-caption uppercase tracking-[0.18em] text-slate-500"
              title="Level sourced from a liquid ETF proxy (data provider does not serve the caret-prefixed index symbol). No ratio conversion is applied."
            >
              {proxyLabel(quote.proxy_ticker)}
            </p>
          )}
          {quote.observed_at && (
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-pq-caption uppercase tracking-[0.16em] text-slate-400 tabular-nums">
                {rel}
              </span>
              {stale ? (
                <span
                  aria-label="Stale quote"
                  title="Quote has not refreshed recently"
                  className="inline-block h-1.5 w-1.5 rounded-full bg-yellow-500/70"
                />
              ) : (
                <span
                  aria-label="Live"
                  title="Live"
                  className="pq-live-dot inline-block h-1.5 w-1.5 rounded-full bg-[#7db487]"
                />
              )}
            </div>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="font-serif text-2xl font-bold tabular-nums text-slate-900">
            {fmtLevel(quote.level, quote.format)}
            {quote.unit && (
              <span className="ml-1 text-xs font-normal text-slate-400">
                {quote.unit}
              </span>
            )}
          </p>
          <p
            className={cn(
              "text-xs font-semibold tabular-nums",
              tone,
            )}
          >
            {fmtPct(quote.changePct)}
          </p>
        </div>
      </div>
      <div className="mt-3">
        <Sparkline points={quote.spark} />
      </div>
      <div className="mt-2">
        <RangeBar
          low={quote.weekLow52}
          high={quote.weekHigh52}
          level={quote.level}
        />
      </div>
    </article>
  );
}
