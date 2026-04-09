"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Trophy, Users, Star, TrendingUp, Shield } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Mock Data                                                          */
/* ------------------------------------------------------------------ */

interface Trader {
  id: number;
  name: string;
  avatar: string;
  returnPct: number;
  winRate: number;
  sharpe: number;
  followers: number;
  risk: "Low" | "Medium" | "High";
  bio: string;
}

const TRADERS: Trader[] = [
  { id: 1, name: "하윤서", avatar: "하", returnPct: 187.4, winRate: 78, sharpe: 2.41, followers: 12840, risk: "Medium", bio: "Momentum + AI alpha blend strategy" },
  { id: 2, name: "박도현", avatar: "박", returnPct: 142.8, winRate: 72, sharpe: 2.18, followers: 9320, risk: "High", bio: "High-conviction concentrated bets" },
  { id: 3, name: "이서진", avatar: "이", returnPct: 118.6, winRate: 81, sharpe: 2.65, followers: 15200, risk: "Low", bio: "Systematic factor rotation" },
  { id: 4, name: "김민준", avatar: "김", returnPct: 96.3, winRate: 69, sharpe: 1.87, followers: 7650, risk: "High", bio: "Earnings catalyst plays" },
  { id: 5, name: "정수빈", avatar: "정", returnPct: 89.1, winRate: 74, sharpe: 2.03, followers: 11400, risk: "Medium", bio: "Quant mean-reversion specialist" },
  { id: 6, name: "최예린", avatar: "최", returnPct: 76.5, winRate: 83, sharpe: 2.72, followers: 18900, risk: "Low", bio: "Defensive dividend compounder" },
  { id: 7, name: "강태현", avatar: "강", returnPct: 64.2, winRate: 67, sharpe: 1.54, followers: 5280, risk: "High", bio: "Options gamma scalping" },
  { id: 8, name: "윤하은", avatar: "윤", returnPct: 52.9, winRate: 76, sharpe: 1.92, followers: 8730, risk: "Low", bio: "Long-term quality growth" },
];

type Filter = "all" | "high-return" | "low-risk" | "most-followed";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "high-return", label: "High Return" },
  { key: "low-risk", label: "Low Risk" },
  { key: "most-followed", label: "Most Followed" },
];

const riskColor: Record<Trader["risk"], string> = {
  Low: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  Medium: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  High: "text-rose-400 bg-rose-400/10 border-rose-400/20",
};

const rankBadge = (rank: number) => {
  if (rank === 1) return "bg-amber-400/15 text-amber-300 border-amber-400/30";
  if (rank === 2) return "bg-zinc-300/10 text-zinc-300 border-zinc-400/20";
  if (rank === 3) return "bg-orange-400/10 text-orange-300 border-orange-400/20";
  return "bg-zinc-700/40 text-zinc-400 border-zinc-600/30";
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function applyFilter(traders: Trader[], filter: Filter): Trader[] {
  switch (filter) {
    case "high-return":
      return [...traders].sort((a, b) => b.returnPct - a.returnPct);
    case "low-risk":
      return traders.filter((t) => t.risk === "Low");
    case "most-followed":
      return [...traders].sort((a, b) => b.followers - a.followers);
    default:
      return [...traders].sort((a, b) => b.returnPct - a.returnPct);
  }
}

function formatNumber(n: number): string {
  if (n >= 10000) return `${(n / 1000).toFixed(1)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toString();
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function CopyTradingPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [followed, setFollowed] = useState<Set<number>>(new Set());

  const toggleFollow = (id: number) => {
    setFollowed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filtered = applyFilter(TRADERS, filter);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-4"
    >
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Copy Trading</h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Follow top-performing traders and mirror their strategies
        </p>
      </div>

      {/* Coming Soon Banner */}
      <div className="relative overflow-hidden glass-surface rounded-xl border-cyan-500/20 bg-gradient-to-r from-cyan-500/10 via-blue-500/10 to-purple-500/10 p-5">
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-cyan-500/5 blur-2xl" />
        <div className="relative flex items-center gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-500/15 text-cyan-400">
            <Star size={22} />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">
              Coming Soon &mdash; Premium Feature
            </p>
            <p className="mt-0.5 text-[13px] text-zinc-400">
              Copy Trading will be available with StockPilot Pro. Join the waitlist to get early access.
            </p>
          </div>
        </div>
      </div>

      {/* Filter Pills */}
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-md px-2.5 py-1 text-[9px] font-bold spring-transition transition-all duration-300 ${
              filter === f.key
                ? "bg-white/10 text-white border border-white/15 shadow-sm"
                : "glass-surface text-zinc-600 hover:text-zinc-300"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Leaderboard */}
      <div className="glass-surface rounded-xl overflow-hidden">
        {/* Table Header */}
        <div className="grid grid-cols-[3rem_1fr_5.5rem_5rem_5rem_5.5rem_5rem_6rem] items-center gap-2 border-b border-white/[0.06] px-5 py-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-600">
          <span>Rank</span>
          <span>Trader</span>
          <span className="text-right">Return</span>
          <span className="text-right">Win Rate</span>
          <span className="text-right">Sharpe</span>
          <span className="text-right">Followers</span>
          <span className="text-center">Risk</span>
          <span className="text-center">Action</span>
        </div>

        {/* Table Rows */}
        {filtered.map((trader, idx) => {
          const rank = idx + 1;
          const isFollowed = followed.has(trader.id);
          return (
            <motion.div
              key={trader.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04, duration: 0.3 }}
              className="grid grid-cols-[3rem_1fr_5.5rem_5rem_5rem_5.5rem_5rem_6rem] items-center gap-2 border-b border-white/[0.06] px-5 py-3.5 last:border-b-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:bg-white/[0.02]"
            >
              {/* Rank */}
              <span
                className={`inline-flex h-7 w-7 items-center justify-center rounded-lg border text-xs font-bold ${rankBadge(rank)}`}
              >
                {rank}
              </span>

              {/* Trader Info */}
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-zinc-700 to-zinc-800 text-sm font-bold text-white">
                  {trader.avatar}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{trader.name}</p>
                  <p className="truncate text-[13px] text-zinc-600">{trader.bio}</p>
                </div>
              </div>

              {/* Return */}
              <div className="text-right">
                <span className="text-sm font-semibold font-mono text-emerald-400">
                  +{trader.returnPct}%
                </span>
              </div>

              {/* Win Rate */}
              <div className="text-right">
                <span className="text-sm font-mono text-zinc-300">{trader.winRate}%</span>
              </div>

              {/* Sharpe */}
              <div className="text-right">
                <span className="text-sm font-mono text-zinc-300">{trader.sharpe.toFixed(2)}</span>
              </div>

              {/* Followers */}
              <div className="flex items-center justify-end gap-1 text-sm text-zinc-400">
                <Users size={12} />
                <span className="font-mono">{formatNumber(trader.followers)}</span>
              </div>

              {/* Risk Badge */}
              <div className="flex justify-center">
                <span
                  className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[9px] font-bold ${riskColor[trader.risk]}`}
                >
                  <Shield size={10} />
                  {trader.risk}
                </span>
              </div>

              {/* Follow Button */}
              <div className="flex justify-center">
                <button
                  onClick={() => toggleFollow(trader.id)}
                  className={`rounded-xl px-3.5 py-1.5 text-xs font-medium spring-transition transition-all duration-300 ${
                    isFollowed
                      ? "bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 text-cyan-400 border border-cyan-500/20"
                      : "bg-white/5 text-zinc-400 border border-white/[0.06] hover:bg-white/10 hover:text-white"
                  }`}
                >
                  {isFollowed ? "Following" : "Follow"}
                </button>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Trophy size={18} className="text-amber-400" />}
          label="Top Return"
          value={`+${TRADERS[0].returnPct}%`}
          sub={TRADERS[0].name}
          color="text-emerald-400"
        />
        <StatCard
          icon={<TrendingUp size={18} className="text-cyan-400" />}
          label="Highest Win Rate"
          value={`${Math.max(...TRADERS.map((t) => t.winRate))}%`}
          sub={TRADERS.find((t) => t.winRate === Math.max(...TRADERS.map((x) => x.winRate)))?.name ?? ""}
          color="text-white"
        />
        <StatCard
          icon={<Star size={18} className="text-purple-400" />}
          label="Best Sharpe"
          value={Math.max(...TRADERS.map((t) => t.sharpe)).toFixed(2)}
          sub={TRADERS.find((t) => t.sharpe === Math.max(...TRADERS.map((x) => x.sharpe)))?.name ?? ""}
          color="text-white"
        />
        <StatCard
          icon={<Users size={18} className="text-emerald-400" />}
          label="Most Followed"
          value={formatNumber(Math.max(...TRADERS.map((t) => t.followers)))}
          sub={TRADERS.find((t) => t.followers === Math.max(...TRADERS.map((x) => x.followers)))?.name ?? ""}
          color="text-white"
        />
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Stat Card                                                          */
/* ------------------------------------------------------------------ */

function StatCard({
  icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  return (
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <div className="flex items-center gap-2.5 text-zinc-600">
        {icon}
        <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">{label}</span>
      </div>
      <p className={`mt-3 text-2xl font-bold font-mono ${color}`}>{value}</p>
      <p className="mt-1 text-[13px] text-zinc-600">{sub}</p>
    </div>
  );
}
