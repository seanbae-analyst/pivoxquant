"use client";

import Link from "next/link";
import { cn, isKoreanTicker } from "@/lib/utils";
import { fmtUsd, fmtPct, pnlColor } from "@/lib/format";
import { Skeleton } from "@/components/ui/loading-skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import type { Position } from "@/lib/types";
import type { PriceDirection } from "@/lib/realtime";
import { useT } from "@/lib/locale";

/* ── Signal badge ── */

function SignalBadge({ signal, score }: { signal: string; score: number }) {
  const cls =
    signal === "POSITIVE"
      ? "signal-positive"
      : signal === "NEGATIVE"
        ? "signal-negative"
        : "signal-neutral";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold tabular-nums whitespace-nowrap",
        cls,
      )}
    >
      {signal === "POSITIVE" ? "POSITIVE" : signal === "NEGATIVE" ? "NEGATIVE" : "NEUTRAL"}{" "}
      {score}
    </span>
  );
}

/* ── Position row ── */

interface PositionRowProps {
  position: Position;
  flash: PriceDirection | undefined;
}

function PositionRow({ position, flash }: PositionRowProps) {
  const pnl = position.pnl_pct;
  const isPositive = pnl >= 0;
  const glowClass = isPositive ? "pnl-glow-positive" : "pnl-glow-negative";

  const flashClass = flash === "up" ? "price-flash-up" : flash === "down" ? "price-flash-down" : "";
  const kr = isKoreanTicker(position.ticker, position.is_korean);

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl bg-white px-4 py-3.5 transition-all duration-300",
        glowClass,
        flashClass,
      )}
    >
      {/* Ticker + Name */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-slate-900">
            {kr ? (position.name || position.ticker) : position.ticker}
          </span>
          {position.signal !== "\u2014" && (
            <SignalBadge signal={position.signal} score={position.score} />
          )}
        </div>
        <p className="text-xs text-slate-500 truncate mt-0.5">
          {kr
            ? `${position.ticker} · KRX · ${position.shares}주`
            : `${position.name} · ${position.shares} share${position.shares > 1 ? "s" : ""}`}
        </p>
      </div>

      {/* Value + P&L */}
      <div className="text-right flex-shrink-0">
        <p className="text-sm font-bold text-slate-900 tabular-nums">
          {fmtUsd(position.market_value)}
        </p>
        <p
          className={cn(
            "text-xs font-semibold tabular-nums mt-0.5",
            pnlColor(pnl),
          )}
        >
          {fmtPct(pnl)}
        </p>
      </div>
    </div>
  );
}

/* ── Positions List ── */

interface PositionsListProps {
  positions: Position[] | undefined;
  updatedTickers: Map<string, PriceDirection>;
  isLoading: boolean;
}

export function PositionsList({
  positions,
  updatedTickers,
  isLoading,
}: PositionsListProps) {
  const t = useT();

  if (isLoading) {
    return (
      <div className="sp-card p-5 space-y-3">
        <Skeleton className="h-5 w-28" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-12 flex-1" />
          </div>
        ))}
      </div>
    );
  }

  const list = positions ?? [];

  return (
    <div className="sp-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-bold text-slate-900">{t("dashboard.positions.title")}</h3>
        {list.length > 0 && (
          <span className="text-xs font-medium text-slate-400 tabular-nums">
            {list.length}{t("dashboard.positions.total")}
          </span>
        )}
      </div>

      {list.length === 0 ? (
        <EmptyState
          icon={
            <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          title={t("dashboard.positions.noPositions")}
          description={t("dashboard.positions.noPositionsDesc")}
          action={{ label: t("dashboard.positions.addPosition"), href: "/portfolio" }}
        />
      ) : (
        <>
          <div className="flex flex-col gap-2">
            {list.map((pos) => (
              <PositionRow
                key={pos.id}
                position={pos}
                flash={updatedTickers.get(pos.ticker)}
              />
            ))}
          </div>

          <div className="mt-4 flex items-center gap-3">
            <Link
              href="/portfolio"
              className="text-sm font-semibold text-violet-600 hover:text-violet-700 transition-colors"
            >
              {t("dashboard.positions.viewPortfolio")} &rarr;
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
