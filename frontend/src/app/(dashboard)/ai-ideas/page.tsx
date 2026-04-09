"use client";

import { useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Sparkles,
  TrendingUp,
  Target,
  RefreshCw,
  ShieldCheck,
  ArrowUpRight,
  Layers,
  DollarSign,
  Hash,
  CheckCircle2,
} from "lucide-react";
import { useDiscover } from "@/lib/hooks";
import type { DiscoverResult } from "@/lib/types";
import { fmtUsd, fmtPct, signalColor, scoreColor } from "@/lib/format";

/* ── helpers ── */

function priorityLabel(p: number) {
  if (p === 1) return "Top Pick";
  if (p === 2) return "2nd";
  if (p === 3) return "3rd";
  return `${p}th`;
}

function priorityBadgeColor(p: number) {
  if (p === 1) return "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";
  if (p <= 3) return "bg-violet-500/15 text-violet-300 border-violet-500/25";
  return "bg-zinc-700/40 text-zinc-400 border-zinc-600/30";
}

/* ── page ── */

export default function AIIdeasPage() {
  const { data, error, isLoading, mutate } = useDiscover();

  const grouped = useMemo(() => {
    if (!data?.results) return { buy: [], hold: [] };
    const sorted = [...data.results]
      .sort((a, b) => a.priority - b.priority)
      .slice(0, 6);
    return {
      buy: sorted.filter((r) => r.signal === "BUY"),
      hold: sorted.filter((r) => r.signal !== "BUY"),
    };
  }, [data]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-10"
    >
      {/* ── Header ── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            AI Weekly Trade Ideas
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            Curated by StockPilot AI based on your profile, portfolio, and
            market conditions
          </p>
        </div>

        <button
          onClick={() => mutate()}
          disabled={isLoading}
          className="flex items-center gap-2 self-start rounded-xl glass-surface px-4 py-2 text-sm font-medium text-zinc-300 transition hover:text-white disabled:opacity-50"
        >
          <RefreshCw
            size={14}
            className={isLoading ? "animate-spin" : ""}
          />
          Refresh
        </button>
      </div>

      {/* ── Hero ── */}
      <div className="relative overflow-hidden rounded-2xl glass-surface bg-gradient-to-br from-cyan-950/40 p-8">
        <div className="absolute -right-12 -top-12 h-56 w-56 rounded-full bg-cyan-500/5 blur-3xl" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:gap-12">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-cyan-500/10 border border-cyan-500/20">
            <Sparkles size={28} className="text-cyan-400" />
          </div>
          <div className="space-y-3 max-w-2xl">
            <h2 className="text-lg font-semibold text-white">
              How AI Discovery Works
            </h2>
            <div className="grid gap-2 text-sm text-zinc-400 sm:grid-cols-3">
              <div className="flex items-start gap-2">
                <Target size={14} className="mt-0.5 shrink-0 text-cyan-400" />
                <span>
                  Scans 500+ stocks for technical and fundamental signals daily
                </span>
              </div>
              <div className="flex items-start gap-2">
                <Layers size={14} className="mt-0.5 shrink-0 text-cyan-400" />
                <span>
                  Ranks by composite score combining momentum, value, and
                  volatility
                </span>
              </div>
              <div className="flex items-start gap-2">
                <ShieldCheck
                  size={14}
                  className="mt-0.5 shrink-0 text-cyan-400"
                />
                <span>
                  Adapts position sizing to your risk profile and capital
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Loading ── */}
      {isLoading && (
        <div className="flex items-center justify-center gap-0 py-20">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
          <span className="text-zinc-600 text-[12px]">Loading...</span>
        </div>
      )}

      {/* ── Error ── */}
      {error && !isLoading && (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-6 text-center text-sm text-red-400">
          Failed to load trade ideas. Please try refreshing.
        </div>
      )}

      {/* ── Cards ── */}
      {!isLoading && !error && data && (
        <>
          {grouped.buy.length > 0 && (
            <Section label="Buy Signals" icon={TrendingUp} items={grouped.buy} />
          )}
          {grouped.hold.length > 0 && (
            <Section label="Hold / Watch" icon={ShieldCheck} items={grouped.hold} />
          )}
          {grouped.buy.length === 0 && grouped.hold.length === 0 && (
            <div className="py-16 text-center text-sm text-zinc-500">
              No trade ideas at this time. Check back later.
            </div>
          )}
        </>
      )}
    </motion.div>
  );
}

/* ── Section ── */

function Section({
  label,
  icon: Icon,
  items,
}: {
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  items: DiscoverResult[];
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Icon size={16} className="text-cyan-400" />
        <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
          {label}
        </h3>
        <span className="ml-1 text-xs text-zinc-600">{items.length}</span>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <IdeaCard key={item.ticker} item={item} />
        ))}
      </div>
    </div>
  );
}

/* ── Card ── */

function IdeaCard({ item }: { item: DiscoverResult }) {
  const {
    ticker,
    name,
    signal,
    score,
    price,
    sector,
    priority,
    already_owned,
    rec_shares,
    rec_investment,
    is_korean,
    currency,
  } = item;
  const snapshot = (item as unknown as Record<string, unknown>).snapshot as Record<string, unknown> | undefined;
  const tp_pct = (snapshot?.tp_pct as number) ?? (item as unknown as Record<string, unknown>).tp_pct as number | undefined;
  const sl_pct = (snapshot?.sl_pct as number) ?? (item as unknown as Record<string, unknown>).sl_pct as number | undefined;

  const displayPrice = is_korean
    ? `₩${Math.round(price).toLocaleString("ko-KR")}`
    : fmtUsd(price);

  const displayInvestment = is_korean
    ? `₩${Math.round(rec_investment).toLocaleString("ko-KR")}`
    : fmtUsd(rec_investment);

  return (
    <Link href={`/detail/${ticker}`}>
      <motion.div
        whileHover={{ y: -2 }}
        transition={{ type: "spring", stiffness: 400, damping: 25 }}
        className="group relative flex flex-col gap-4 rounded-2xl glass-surface p-5 transition-colors"
      >
        {/* top row */}
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-white">{ticker}</span>
              {already_owned && (
                <span className="flex items-center gap-0.5 text-[10px] text-emerald-400">
                  <CheckCircle2 size={10} />
                  Owned
                </span>
              )}
            </div>
            <p className="mt-0.5 truncate text-xs text-zinc-500">{name}</p>
          </div>

          <div className="flex items-center gap-1.5">
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${signalColor(signal)}`}
            >
              {signal}
            </span>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${priorityBadgeColor(priority)}`}
            >
              #{priority} {priorityLabel(priority)}
            </span>
          </div>
        </div>

        {/* price + score row */}
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xl font-semibold text-white">{displayPrice}</p>
            <p
              className={`text-xs font-medium ${
                ((item as unknown as Record<string, unknown>).change_pct as number ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {fmtPct(((item as unknown as Record<string, unknown>).change_pct as number ?? 0))}
            </p>
          </div>

          <div className="text-right">
            <p className="text-[10px] uppercase tracking-wider text-zinc-600">
              Score
            </p>
            <div className="mt-0.5 flex items-center gap-1.5">
              <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className={`h-full rounded-full ${scoreColor(score)}`}
                  style={{ width: `${Math.min(score, 100)}%` }}
                />
              </div>
              <span className="text-sm font-bold text-white">{score}</span>
            </div>
          </div>
        </div>

        {/* sector */}
        <div className="flex items-center gap-1.5 text-[11px] text-zinc-500">
          <Layers size={11} />
          {sector}
        </div>

        {/* recommendation */}
        <div className="rounded-xl border border-white/[0.06] bg-zinc-900/50 p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            Recommended Action
          </p>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="flex items-center gap-1.5">
              <Hash size={11} className="text-cyan-400" />
              <span className="text-zinc-400">Shares</span>
              <span className="ml-auto font-semibold text-white">
                {rec_shares}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <DollarSign size={11} className="text-cyan-400" />
              <span className="text-zinc-400">Invest</span>
              <span className="ml-auto font-semibold text-white">
                {displayInvestment}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <ArrowUpRight size={11} className="text-emerald-400" />
              <span className="text-zinc-400">TP</span>
              <span className="ml-auto font-medium text-emerald-400">
                {fmtPct(tp_pct ?? 0)}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <ArrowUpRight
                size={11}
                className="rotate-90 text-red-400"
              />
              <span className="text-zinc-400">SL</span>
              <span className="ml-auto font-medium text-red-400">
                {fmtPct(sl_pct ? -Math.abs(sl_pct) : 0)}
              </span>
            </div>
          </div>
        </div>

        {/* hover arrow */}
        <div className="absolute right-4 top-1/2 -translate-y-1/2 opacity-0 transition-opacity group-hover:opacity-100">
          <ArrowUpRight size={16} className="text-cyan-400" />
        </div>
      </motion.div>
    </Link>
  );
}
