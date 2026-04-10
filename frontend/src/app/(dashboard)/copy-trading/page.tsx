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
  Low: "text-emerald-600 bg-emerald-50 border-emerald-200",
  Medium: "text-amber-600 bg-amber-50 border-amber-200",
  High: "text-red-600 bg-red-50 border-red-200",
};

const rankBadge = (rank: number) => {
  if (rank === 1) return "bg-amber-50 text-amber-600 border-amber-200";
  if (rank === 2) return "bg-slate-100 text-slate-500 border-slate-200";
  if (rank === 3) return "bg-orange-50 text-orange-500 border-orange-200";
  return "bg-slate-50 text-slate-400 border-slate-200";
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
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Copy Trading</h1>
        <p className="mt-1 text-[13px] text-slate-400">
          Follow top-performing traders and mirror their strategies
        </p>
      </div>

      {/* Coming Soon Banner */}
      <div className="relative overflow-hidden glass-surface rounded-xl border-sky-200 bg-gradient-to-r from-sky-50 via-blue-50 to-violet-50 p-5">
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-sky-100 blur-2xl" />
        <div className="relative flex items-center gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-sky-100 text-sky-600">
            <Star size={22} />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">
              Coming Soon &mdash; Premium Feature
            </p>
            <p className="mt-0.5 text-[13px] text-slate-500">
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
                ? "bg-slate-100 text-slate-900 border border-slate-200 shadow-sm"
                : "glass-surface text-slate-400 hover:text-slate-700"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Leaderboard */}
      <div className="glass-surface rounded-xl overflow-hidden">
        {/* Table Header */}
        <div className="grid grid-cols-[3rem_1fr_5.5rem_5rem_5rem_5.5rem_5rem_6rem] items-center gap-2 border-b border-slate-200 px-5 py-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">
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
              className="grid grid-cols-[3rem_1fr_5.5rem_5rem_5rem_5.5rem_5rem_6rem] items-center gap-2 border-b border-slate-100 px-5 py-3.5 last:border-b-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)] hover:bg-slate-50"
            >
              {/* Rank */}
              <span
                className={`inline-flex h-7 w-7 items-center justify-center rounded-lg border text-xs font-bold ${rankBadge(rank)}`}
              >
                {rank}
              </span>

              {/* Trader Info */}
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-slate-200 to-slate-300 text-sm font-bold text-slate-700">
                  {trader.avatar}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{trader.name}</p>
                  <p className="truncate text-[13px] text-slate-400">{trader.bio}</p>
                </div>
              </div>

              {/* Return */}
              <div className="text-right">
                <span className="text-sm font-semibold font-mono text-emerald-600">
                  +{trader.returnPct}%
                </span>
              </div>

              {/* Win Rate */}
              <div className="text-right">
                <span className="text-sm font-mono text-slate-700">{trader.winRate}%</span>
              </div>

              {/* Sharpe */}
              <div className="text-right">
                <span className="text-sm font-mono text-slate-700">{trader.sharpe.toFixed(2)}</span>
              </div>

              {/* Followers */}
              <div className="flex items-center justify-end gap-1 text-sm text-slate-500">
                <Users size={12} />
                <span className="font-mono">{formatNumber(trader.followers)}</span>
              </div>

              {/* Risk Badge */}
              <div className="flex justify-center">
                <span
                  className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[9px] font-bold border ${riskColor[trader.risk]}`}
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
                      ? "bg-gradient-to-r from-sky-50 to-emerald-50 text-sky-600 border border-sky-200"
                      : "bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100 hover:text-slate-900"
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
          icon={<Trophy size={18} className="text-amber-500" />}
          label="Top Return"
          value={`+${TRADERS[0].returnPct}%`}
          sub={TRADERS[0].name}
          color="text-emerald-600"
        />
        <StatCard
          icon={<TrendingUp size={18} className="text-sky-600" />}
          label="Highest Win Rate"
          value={`${Math.max(...TRADERS.map((t) => t.winRate))}%`}
          sub={TRADERS.find((t) => t.winRate === Math.max(...TRADERS.map((x) => x.winRate)))?.name ?? ""}
          color="text-slate-900"
        />
        <StatCard
          icon={<Star size={18} className="text-violet-500" />}
          label="Best Sharpe"
          value={Math.max(...TRADERS.map((t) => t.sharpe)).toFixed(2)}
          sub={TRADERS.find((t) => t.sharpe === Math.max(...TRADERS.map((x) => x.sharpe)))?.name ?? ""}
          color="text-slate-900"
        />
        <StatCard
          icon={<Users size={18} className="text-emerald-600" />}
          label="Most Followed"
          value={formatNumber(Math.max(...TRADERS.map((t) => t.followers)))}
          sub={TRADERS.find((t) => t.followers === Math.max(...TRADERS.map((x) => x.followers)))?.name ?? ""}
          color="text-slate-900"
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
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)]">
      <div className="flex items-center gap-2.5 text-slate-400">
        {icon}
        <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">{label}</span>
      </div>
      <p className={`mt-3 text-2xl font-bold font-mono ${color}`}>{value}</p>
      <p className="mt-1 text-[13px] text-slate-400">{sub}</p>
    </div>
  );
}
