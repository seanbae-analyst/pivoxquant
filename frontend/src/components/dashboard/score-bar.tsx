"use client";

import { cn } from "@/lib/utils";

interface ScoreBarProps {
  score: number;
  signal?: string;
  /** Compact mode for list items */
  mini?: boolean;
  className?: string;
}

function signalLabel(signal: string): string {
  switch (signal) {
    case "POSITIVE":
      return "Positive";
    case "NEGATIVE":
      return "Negative";
    case "NEUTRAL":
      return "Neutral";
    default:
      return signal;
  }
}

function signalBadgeClass(signal: string): string {
  switch (signal) {
    case "POSITIVE":
      return "signal-positive";
    case "NEGATIVE":
      return "signal-negative";
    default:
      return "signal-neutral";
  }
}

export function ScoreBar({ score, signal, mini = false, className }: ScoreBarProps) {
  const clampedScore = Math.max(0, Math.min(100, score));

  if (mini) {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <div className="relative h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
          <div
            className="absolute inset-y-0 left-0 rounded-full"
            style={{
              width: `${clampedScore}%`,
              background: `linear-gradient(90deg, #ef4444, #f59e0b, #10b981)`,
              backgroundSize: "100px 100%",
              backgroundPosition: `${100 - clampedScore}% 0`,
            }}
          />
        </div>
        <span className="text-xs font-semibold tabular-nums text-slate-700">
          {clampedScore}
        </span>
      </div>
    );
  }

  return (
    <div className={cn("sp-card p-5", className)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-500">
            Quant Score
          </span>
          {signal && signal !== "\u2014" && (
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
                signalBadgeClass(signal),
              )}
            >
              {signalLabel(signal)}
            </span>
          )}
        </div>
        <span className="text-2xl font-bold tabular-nums text-slate-900">
          {clampedScore}
          <span className="text-sm font-medium text-slate-400">/100</span>
        </span>
      </div>

      {/* Gradient bar */}
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background: "linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #10b981 100%)",
          }}
        />
        {/* Mask: clip to score width */}
        <div
          className="absolute inset-y-0 right-0 bg-slate-100"
          style={{ width: `${100 - clampedScore}%` }}
        />
        {/* Score indicator dot */}
        <div
          className="absolute top-1/2 -translate-y-1/2 h-5 w-5 rounded-full border-2 border-white bg-slate-900 shadow-md transition-all duration-500"
          style={{ left: `calc(${clampedScore}% - 10px)` }}
        />
      </div>

      {/* Scale labels */}
      <div className="mt-1.5 flex justify-between text-[10px] font-medium text-slate-400">
        <span>0 Negative</span>
        <span>50</span>
        <span>100 Positive</span>
      </div>
    </div>
  );
}
