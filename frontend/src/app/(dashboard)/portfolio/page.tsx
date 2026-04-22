"use client";

import { useMemo, useState } from "react";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { SummaryCards } from "@/components/portfolio/summary-cards";
import { PositionsTable } from "@/components/portfolio/positions-table";
import { RecentTrades } from "@/components/portfolio/recent-trades";
import { SectorAllocation } from "@/components/portfolio/sector-allocation";
import { AddPositionModal } from "@/components/portfolio/add-position-modal";
import { TradeModal } from "@/components/portfolio/trade-modal";
import { MOCK_POSITIONS, MOCK_TRADES } from "@/components/portfolio/mock-data";
import type { Position, TradeAction } from "@/components/portfolio/types";

/**
 * Portfolio — editorial Vantablack-tone surface.
 * Records-only UX: Add / Buy More / Sell / Edit create local log entries.
 * Not a trading interface; not investment advice.
 */
export default function PortfolioPage() {
  const [addOpen, setAddOpen] = useState(false);
  const [tradeAction, setTradeAction] = useState<TradeAction | null>(null);
  const [targetPosition, setTargetPosition] = useState<Position | null>(null);

  const positions = MOCK_POSITIONS;

  const totals = useMemo(() => {
    let mv = 0;
    let cost = 0;
    for (const p of positions) {
      mv += p.shares * p.current;
      cost += p.shares * p.avgCost;
    }
    const unrealized = mv - cost;
    // Illustrative values — replace with analytics feed when wired.
    return {
      totalNav: mv,
      todayPnl: 680,
      todayPnlPct: 0.54,
      unrealized,
      realizedYtd: 3420,
    };
  }, [positions]);

  function openAction(action: TradeAction, position: Position) {
    setTargetPosition(position);
    setTradeAction(action);
  }

  function closeTrade() {
    setTradeAction(null);
    setTargetPosition(null);
  }

  return (
    <ErrorBoundary>
      <div className="space-y-8 pb-12">
        {/* ── Header ── */}
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Holdings
            </p>
            <h1 className="mt-1 font-serif text-[40px] italic leading-tight text-slate-900">
              Portfolio
            </h1>
            <p className="mt-1 text-[13px] text-slate-500">
              Your self-reported book of record. Update as you transact elsewhere.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="inline-flex h-10 items-center justify-center rounded-sm bg-[#8B6F47] px-5 text-[13px] font-medium tracking-wide text-white transition-colors hover:bg-[#6F5636]"
          >
            Add Position
          </button>
        </header>

        {/* ── Summary ── */}
        <SummaryCards
          totalNav={totals.totalNav}
          todayPnl={totals.todayPnl}
          todayPnlPct={totals.todayPnlPct}
          unrealized={totals.unrealized}
          realizedYtd={totals.realizedYtd}
        />

        {/* ── Positions ── */}
        <PositionsTable
          positions={positions}
          totalMarketValue={totals.totalNav}
          onAction={openAction}
        />

        {/* ── Trades + Allocation ── */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <RecentTrades trades={MOCK_TRADES} />
          </div>
          <div className="lg:col-span-2">
            <SectorAllocation
              positions={positions}
              totalMarketValue={totals.totalNav}
            />
          </div>
        </div>

        {/* ── Disclaimer ── */}
        <div className="pt-2">
          <DisclaimerBanner type="signal" />
          <p className="mt-2 text-[11px] italic text-slate-500">
            Not investment advice — user-entered records only.
          </p>
        </div>

        {/* ── Modals ── */}
        <AddPositionModal open={addOpen} onClose={() => setAddOpen(false)} />
        <TradeModal
          key={targetPosition?.id ?? "none"}
          open={tradeAction !== null && targetPosition !== null}
          onClose={closeTrade}
          action={tradeAction ?? "buy"}
          position={targetPosition}
        />
      </div>
    </ErrorBoundary>
  );
}
