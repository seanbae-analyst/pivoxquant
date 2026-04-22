"use client";

/**
 * Editorial index card — level, 1D change, 52W range bar, 30-day sparkline.
 * Inline SVG, hand-crafted, no chart lib dependency.
 */

import { cn } from "@/lib/utils";
import { fmtPct } from "@/lib/format";

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
  const w = 200;
  const h = 36;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const step = w / (points.length - 1);
  const path = points
    .map((v, i) => {
      const x = i * step;
      const y = h - ((v - min) / range) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const isUp = points[points.length - 1] >= points[0];
  const stroke = isUp ? "#8B6F47" : "#B04A3A";
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      className="block w-full"
      role="img"
      aria-label="30-day sparkline"
    >
      <path d={path} fill="none" stroke={stroke} strokeWidth={1.25} />
    </svg>
  );
}

export function IndexCard({ quote }: { quote: IndexQuote }) {
  const tone =
    quote.changePct > 0
      ? "text-[var(--pq-bronze,#8B6F47)]"
      : quote.changePct < 0
        ? "text-[#B04A3A]"
        : "text-slate-500";
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
