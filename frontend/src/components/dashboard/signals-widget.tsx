"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/loading-skeleton";
import type { Position } from "@/lib/types";
import { useT } from "@/lib/locale";

/* ── Signal badge ── */

function SignalBadge({ signal, score }: { signal: string; score: number }) {
  const cls =
    signal === "POSITIVE"
      ? "signal-positive"
      : signal === "NEGATIVE"
        ? "signal-negative"
        : "signal-neutral";

  const label =
    signal === "POSITIVE"
      ? "Positive"
      : signal === "NEGATIVE"
        ? "Negative"
        : "Neutral";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums",
        cls,
      )}
    >
      {label} {score}
    </span>
  );
}

/* ── Signals Widget ── */

interface SignalsWidgetProps {
  positions: Position[] | undefined;
  isLoading: boolean;
}

export function SignalsWidget({ positions, isLoading }: SignalsWidgetProps) {
  const t = useT();

  if (isLoading) {
    return (
      <div className="sp-card p-5 space-y-4">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  // Sort by score descending, take top 5
  const sorted = [...(positions ?? [])]
    .filter((p) => p.signal !== "\u2014")
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);

  return (
    <div className="sp-card p-5 flex flex-col">
      <h3 className="text-base font-bold text-slate-900 mb-4">{t("dashboard.signals.title")}</h3>

      {sorted.length === 0 ? (
        <p className="text-sm text-slate-400 py-4">
          {t("dashboard.signals.noSignals")}. {t("dashboard.signals.noSignalsDesc")}
        </p>
      ) : (
        <div className="flex flex-col gap-2.5 flex-1">
          {sorted.map((p) => (
            <div
              key={p.ticker}
              className="flex items-center justify-between rounded-xl bg-slate-50 px-3.5 py-2.5 transition-colors hover:bg-slate-100"
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-slate-900 w-14">
                  {p.ticker}
                </span>
                <span className="text-xs text-slate-500 truncate max-w-[100px] hidden sm:inline">
                  {p.name}
                </span>
              </div>
              <SignalBadge signal={p.signal} score={p.score} />
            </div>
          ))}
        </div>
      )}

      <Link
        href="/signals"
        className="mt-4 text-sm font-semibold text-violet-600 hover:text-violet-700 transition-colors self-start"
      >
        {t("dashboard.signals.viewAllSignals")} &rarr;
      </Link>
    </div>
  );
}
