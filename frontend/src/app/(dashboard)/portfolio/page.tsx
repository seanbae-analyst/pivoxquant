"use client";

/**
 * Portfolio — Vantablack ink terminal card on ivory shell.
 *
 * Records-only UX: Add / Buy More / Sell / Edit write through to the
 * backend positions + trades endpoints via the existing modals.
 * Not investment advice. DisclaimerBanner at foot.
 */

import { useMemo, useState, useEffect } from "react";
import useSWR, { mutate } from "swr";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { TerminalSidebar } from "@/components/layout/terminal-sidebar";
import { AddPositionModal } from "@/components/portfolio/add-position-modal";
import { TradeModal } from "@/components/portfolio/trade-modal";
import { MOCK_POSITIONS, MOCK_TRADES } from "@/components/portfolio/mock-data";
import {
  PORTFOLIO_POSITIONS,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_TRADES,
} from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { fmtUsd, fmtPct } from "@/lib/format";
import type { Position, Trade, TradeAction } from "@/components/portfolio/types";

interface PositionsResponse { positions?: Position[]; }
interface TradesResponse { trades?: Trade[]; }
interface SummaryResponse {
  totalNav?: number;
  todayPnl?: number;
  todayPnlPct?: number;
  unrealized?: number;
  realizedYtd?: number;
}

const fetcher = async <T,>(url: string): Promise<T> => apiFetch<T>(url);

function handleApiError(err: unknown, context: string) {
  if (err instanceof ApiError && err.status === 401) {
    if (typeof window !== "undefined") window.location.href = "/login";
    return;
  }
  const message = err instanceof Error ? err.message : "Something went wrong";
  toast.error(`${context}: ${message}`);
}

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

export default function PortfolioPage() {
  const [addOpen, setAddOpen] = useState(false);
  const [tradeAction, setTradeAction] = useState<TradeAction | null>(null);
  const [targetPosition, setTargetPosition] = useState<Position | null>(null);
  const [showSkeleton, setShowSkeleton] = useState(true);

  const { data: posData, error: posErr, isLoading: posLoading } =
    useSWR<PositionsResponse>(PORTFOLIO_POSITIONS, fetcher, { revalidateOnFocus: false });
  const { data: sumData, error: sumErr } =
    useSWR<SummaryResponse>(PORTFOLIO_SUMMARY, fetcher, { revalidateOnFocus: false });
  const { data: tradesData, error: tradesErr } =
    useSWR<TradesResponse>(`${PORTFOLIO_TRADES}?limit=8`, fetcher, { revalidateOnFocus: false });

  useEffect(() => { if (posErr) handleApiError(posErr, "Positions"); }, [posErr]);
  useEffect(() => { if (sumErr) handleApiError(sumErr, "Summary"); }, [sumErr]);
  useEffect(() => { if (tradesErr) handleApiError(tradesErr, "Trades"); }, [tradesErr]);

  useEffect(() => {
    const t = setTimeout(() => setShowSkeleton(false), 1200);
    return () => clearTimeout(t);
  }, []);

  const positions: Position[] = useMemo(() => {
    if (posData?.positions && posData.positions.length > 0) return posData.positions;
    if (posErr) return MOCK_POSITIONS;
    return posData?.positions ?? [];
  }, [posData, posErr]);

  const trades: Trade[] = useMemo(() => {
    if (tradesData?.trades && tradesData.trades.length > 0) return tradesData.trades;
    if (tradesErr) return MOCK_TRADES;
    return tradesData?.trades ?? [];
  }, [tradesData, tradesErr]);

  const totals = useMemo(() => {
    let mv = 0;
    let cost = 0;
    for (const p of positions) {
      mv += p.shares * p.current;
      cost += p.shares * p.avgCost;
    }
    const unrealized = mv - cost;
    if (sumData && typeof sumData.totalNav === "number") {
      return {
        totalNav: sumData.totalNav,
        todayPnl: sumData.todayPnl ?? 0,
        todayPnlPct: sumData.todayPnlPct ?? 0,
        unrealized: sumData.unrealized ?? unrealized,
        realizedYtd: sumData.realizedYtd ?? 0,
      };
    }
    return { totalNav: mv, todayPnl: 0, todayPnlPct: 0, unrealized, realizedYtd: 0 };
  }, [sumData, positions]);

  // Sector allocation — computed inline.
  const sectorAlloc = useMemo(() => {
    const byS: Record<string, number> = {};
    let total = 0;
    for (const p of positions) {
      const mv = p.shares * p.current;
      byS[p.sector] = (byS[p.sector] ?? 0) + mv;
      total += mv;
    }
    return Object.entries(byS)
      .map(([sector, mv]) => ({ sector, mv, pct: total > 0 ? (mv / total) * 100 : 0 }))
      .sort((a, b) => b.mv - a.mv);
  }, [positions]);

  function openAction(action: TradeAction, position: Position) {
    setTargetPosition(position);
    setTradeAction(action);
  }
  function closeTrade() {
    setTradeAction(null);
    setTargetPosition(null);
  }
  function refreshAll() {
    mutate(PORTFOLIO_POSITIONS);
    mutate(PORTFOLIO_SUMMARY);
    mutate(`${PORTFOLIO_TRADES}?limit=8`);
  }

  if (posLoading && showSkeleton) {
    return (
      <div className="pq-ink-card animate-pulse">
        <div className="h-4 w-40 bg-white/10 rounded-sm" />
        <div className="mt-6 h-10 w-56 bg-white/10 rounded-sm" />
        <div className="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-white/5 rounded-sm" />
          ))}
        </div>
      </div>
    );
  }

  const toneClass = (v: number) =>
    v > 0 ? "text-[#7db487]" : v < 0 ? "text-[#d18888]" : "text-[rgba(245,240,232,0.55)]";

  return (
    <ErrorBoundary>
      <div className="pq-ink-card">
        {/* Terminal header row */}
        <header className="mb-8 flex items-center justify-between gap-4">
          <span className="pq-ink-kicker">PIVOXQUANT · PORTFOLIO</span>
          <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
            {weekTag()}
          </span>
        </header>

        <div className="flex gap-8 md:gap-10">
          <TerminalSidebar active="portfolio" />
          <div className="flex-1 min-w-0">
        {/* Title + CTA */}
        <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="pq-ink-h1">Portfolio</h1>
            <p className="mt-2 font-serif italic text-sm text-[rgba(245,240,232,0.55)]">
              Your self-reported book of record. Informational only.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="pq-ink-btn-bronze"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Position
          </button>
        </div>

        {/* 4-stat bento */}
        <section className="mb-10 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="pq-ink-stat">
            <div className="pq-ink-label">Total NAV</div>
            <div className="pq-ink-num mt-2">{fmtUsd(totals.totalNav)}</div>
          </div>
          <div className="pq-ink-stat">
            <div className="pq-ink-label">Today · P&amp;L</div>
            <div className={"pq-ink-num mt-2 " + toneClass(totals.todayPnl)}>
              {fmtUsd(totals.todayPnl)}
            </div>
            <div className={"mt-1 font-mono text-[11px] " + toneClass(totals.todayPnlPct)}>
              {fmtPct(totals.todayPnlPct)}
            </div>
          </div>
          <div className="pq-ink-stat">
            <div className="pq-ink-label">Unrealized</div>
            <div className={"pq-ink-num mt-2 " + toneClass(totals.unrealized)}>
              {fmtUsd(totals.unrealized)}
            </div>
          </div>
          <div className="pq-ink-stat">
            <div className="pq-ink-label">Realized YTD</div>
            <div className={"pq-ink-num mt-2 " + toneClass(totals.realizedYtd)}>
              {fmtUsd(totals.realizedYtd)}
            </div>
          </div>
        </section>

        {/* Positions table */}
        <section className="mb-12">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="pq-ink-h2">Positions</h2>
            <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.45)]">
              {positions.length} held
            </span>
          </div>
          {positions.length === 0 ? (
            <div className="pq-ink-empty">No positions yet. Use Add Position to begin.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="pq-ink-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Name</th>
                    <th>Side</th>
                    <th className="num">Shares</th>
                    <th className="num">Avg Cost</th>
                    <th className="num">Last</th>
                    <th className="num">Market Value</th>
                    <th className="num">Unrealized</th>
                    <th className="num">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p) => {
                    const mv = p.shares * p.current;
                    const unreal = (p.current - p.avgCost) * p.shares;
                    const unrealPct = p.avgCost > 0 ? ((p.current - p.avgCost) / p.avgCost) * 100 : 0;
                    return (
                      <tr key={p.id}>
                        <td className="font-mono text-[var(--pq-bronze)] tracking-wide">{p.symbol}</td>
                        <td className="text-[rgba(245,240,232,0.75)] truncate max-w-[220px]">{p.name}</td>
                        <td>
                          <span className="pq-ink-pill pq-ink-pill--neu">{p.side}</span>
                        </td>
                        <td className="num">{p.shares.toLocaleString("en-US")}</td>
                        <td className="num">{fmtUsd(p.avgCost)}</td>
                        <td className="num">{fmtUsd(p.current)}</td>
                        <td className="num">{fmtUsd(mv)}</td>
                        <td className={"num " + toneClass(unreal)}>
                          {fmtUsd(unreal)}
                          <div className="text-[10px] opacity-70">{fmtPct(unrealPct)}</div>
                        </td>
                        <td className="num">
                          <div className="flex justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => openAction("buy", p)}
                              className="text-[10px] uppercase tracking-[0.18em] text-[var(--pq-bronze)] hover:text-[var(--pq-bronze-light)]"
                            >
                              +
                            </button>
                            <button
                              type="button"
                              onClick={() => openAction("sell", p)}
                              className="text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.55)] hover:text-[var(--pq-ivory)]"
                            >
                              −
                            </button>
                            <button
                              type="button"
                              onClick={() => openAction("edit", p)}
                              className="text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.55)] hover:text-[var(--pq-ivory)]"
                            >
                              ✎
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Recent trades + sector allocation */}
        <section className="grid grid-cols-1 gap-10 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <h2 className="pq-ink-h2 mb-4">Recent Trades</h2>
            {trades.length === 0 ? (
              <div className="pq-ink-empty">No trades recorded.</div>
            ) : (
              <table className="pq-ink-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th className="num">Qty</th>
                    <th className="num">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.slice(0, 8).map((t) => (
                    <tr key={t.id}>
                      <td className="font-mono text-[11px] text-[rgba(245,240,232,0.7)]">
                        {t.date}
                      </td>
                      <td className="font-mono text-[var(--pq-bronze)]">{t.symbol}</td>
                      <td>
                        <span
                          className={
                            "pq-ink-pill " +
                            (t.side === "Bought" ? "pq-ink-pill--pos" : "pq-ink-pill--neg")
                          }
                        >
                          {t.side}
                        </span>
                      </td>
                      <td className="num">{t.qty.toLocaleString("en-US")}</td>
                      <td className="num">{fmtUsd(t.price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="lg:col-span-2">
            <h2 className="pq-ink-h2 mb-4">Sector Allocation</h2>
            {sectorAlloc.length === 0 ? (
              <div className="pq-ink-empty">—</div>
            ) : (
              <ul className="space-y-3">
                {sectorAlloc.map((s) => (
                  <li key={s.sector}>
                    <div className="flex items-baseline justify-between text-[12px]">
                      <span className="text-[rgba(245,240,232,0.85)]">{s.sector}</span>
                      <span className="font-mono tabular-nums text-[rgba(245,240,232,0.7)]">
                        {s.pct.toFixed(1)}%
                      </span>
                    </div>
                    <div className="mt-1.5 h-[3px] bg-[rgba(245,240,232,0.08)]">
                      <div
                        className="h-full bg-[var(--pq-bronze)]"
                        style={{ width: `${Math.min(100, s.pct)}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* Disclaimer inside card, muted */}
        <div className="mt-12 border-t border-[rgba(245,240,232,0.1)] pt-6">
          <div className="text-[rgba(245,240,232,0.7)]">
            <DisclaimerBanner type="signal" />
          </div>
          <p className="mt-3 text-[10px] italic text-[rgba(245,240,232,0.4)]">
            User-entered record only. Not investment advice.
          </p>
        </div>
          </div>
        </div>

        {/* Modals — overlaid, retain existing ivory styling */}
        <AddPositionModal
          open={addOpen}
          onClose={() => setAddOpen(false)}
          onSuccess={refreshAll}
        />
        <TradeModal
          key={targetPosition?.id ?? "none"}
          open={tradeAction !== null && targetPosition !== null}
          onClose={closeTrade}
          action={tradeAction ?? "buy"}
          position={targetPosition}
          onSuccess={refreshAll}
        />
      </div>
    </ErrorBoundary>
  );
}
