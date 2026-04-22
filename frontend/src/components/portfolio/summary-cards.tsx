"use client";

import { fmtUsd, fmtPct } from "@/lib/format";

interface SummaryCardsProps {
  totalNav: number;
  todayPnl: number;
  todayPnlPct: number;
  unrealized: number;
  realizedYtd: number;
}

function Card({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "pos" | "neg" | "neutral";
}) {
  const subColor =
    tone === "pos"
      ? "text-emerald-600"
      : tone === "neg"
        ? "text-red-600"
        : "text-slate-500";
  return (
    <div className="flex flex-col border-t border-slate-900/90 bg-white px-5 pt-4 pb-5">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </span>
      <span className="mt-1 font-mono text-[26px] font-medium tabular-nums text-slate-900">
        {value}
      </span>
      {sub ? (
        <span className={"mt-1 font-mono text-[12px] tabular-nums " + subColor}>
          {sub}
        </span>
      ) : null}
    </div>
  );
}

export function SummaryCards({
  totalNav,
  todayPnl,
  todayPnlPct,
  unrealized,
  realizedYtd,
}: SummaryCardsProps) {
  const todayTone: "pos" | "neg" | "neutral" =
    todayPnl > 0 ? "pos" : todayPnl < 0 ? "neg" : "neutral";
  const unrealTone: "pos" | "neg" | "neutral" =
    unrealized > 0 ? "pos" : unrealized < 0 ? "neg" : "neutral";
  const realTone: "pos" | "neg" | "neutral" =
    realizedYtd > 0 ? "pos" : realizedYtd < 0 ? "neg" : "neutral";

  return (
    <div className="grid grid-cols-2 gap-px bg-slate-200 lg:grid-cols-4">
      <Card label="Total NAV" value={fmtUsd(totalNav)} />
      <Card
        label="Today's P&L"
        value={fmtUsd(todayPnl)}
        sub={fmtPct(todayPnlPct)}
        tone={todayTone}
      />
      <Card
        label="Unrealized P&L"
        value={fmtUsd(unrealized)}
        tone={unrealTone}
      />
      <Card
        label="Realized YTD"
        value={fmtUsd(realizedYtd)}
        tone={realTone}
      />
    </div>
  );
}
