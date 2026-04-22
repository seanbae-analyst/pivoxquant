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
  weekHigh52: number;
  weekLow52: number;
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

function fmtLevel(v: number, kind: IndexQuote["format"] = "en"): string {
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
  low: number;
  high: number;
  level: number;
}) {
  const pct = Math.max(0, Math.min(1, (level - low) / (high - low)));
  return (
    <div>
      <div className="relative h-1 rounded-full bg-slate-100">
        <div
          className="absolute top-0 h-1 w-1 -translate-x-1/2 rounded-full bg-[var(--pq-bronze,#8B6F47)]"
          style={{ left: `${pct * 100}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-slate-400">
        <span>{fmtLevel(low, "en")}</span>
        <span className="text-[10px] uppercase tracking-wider text-slate-400">
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
  const stroke = isUp ? "#8B6F47" : "#B04A3A";

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
      ? "text-[var(--pq-bronze,#8B6F47)]"
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
          <p className="text-[10px] uppercase tracking-widest text-slate-400">
            {quote.symbol}
          </p>
          <h3 className="font-serif italic text-base font-bold text-slate-900 truncate">
            {quote.name}
          </h3>
          {quote.observed_at && (
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-slate-400 tabular-nums">
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
          <p className="font-serif italic text-2xl font-bold tabular-nums text-slate-900">
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
