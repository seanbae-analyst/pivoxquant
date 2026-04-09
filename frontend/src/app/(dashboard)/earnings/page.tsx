"use client";

import { useMemo } from "react";
import { useEarnings } from "@/lib/hooks";
import { signalColor, scoreColor } from "@/lib/format";
import { Calendar, Clock, TrendingUp } from "lucide-react";
import type { EarningsItem } from "@/lib/types";

/* ── Helpers ── */

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function startOfWeek(d: Date): Date {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const start = new Date(d);
  start.setDate(diff);
  start.setHours(0, 0, 0, 0);
  return start;
}

function getWeekLabel(dateStr: string, now: Date): string {
  const d = new Date(dateStr);
  const thisWeekStart = startOfWeek(now);
  const nextWeekStart = new Date(thisWeekStart);
  nextWeekStart.setDate(nextWeekStart.getDate() + 7);
  const weekAfterNext = new Date(nextWeekStart);
  weekAfterNext.setDate(weekAfterNext.getDate() + 7);

  if (d >= thisWeekStart && d < nextWeekStart) return "This Week";
  if (d >= nextWeekStart && d < weekAfterNext) return "Next Week";
  if (d < thisWeekStart) return "Past";
  return "Upcoming";
}

function groupByWeek(
  items: EarningsItem[],
  now: Date,
): { label: string; items: EarningsItem[] }[] {
  const order = ["This Week", "Next Week", "Upcoming", "Past"];
  const map = new Map<string, EarningsItem[]>();

  for (const item of items) {
    const label = getWeekLabel(item.date, now);
    const arr = map.get(label) ?? [];
    arr.push(item);
    map.set(label, arr);
  }

  return order
    .filter((label) => map.has(label))
    .map((label) => ({
      label,
      items: map.get(label)!.sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
      ),
    }));
}

/* ── Summary card ── */

function SummaryCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <div className="mb-3 flex items-center gap-2 text-zinc-600">
        <Icon className="h-4 w-4" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">
          {label}
        </span>
      </div>
      <p className="text-2xl font-bold font-mono text-white">{value}</p>
      {sub && <p className="mt-1 text-[13px] text-zinc-400">{sub}</p>}
    </div>
  );
}

/* ── Earnings row ── */

function EarningsRow({ item }: { item: EarningsItem }) {
  return (
    <div className="flex items-center gap-4 border-b border-white/[0.06] px-5 py-4 last:border-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:bg-white/[0.02]">
      {/* Date badge */}
      <div className="flex h-11 w-11 flex-shrink-0 flex-col items-center justify-center rounded-xl bg-white/5 text-center">
        <span className="text-[10px] font-semibold uppercase text-zinc-600 tracking-[0.1em]">
          {new Date(item.date).toLocaleDateString("en-US", { month: "short" })}
        </span>
        <span className="text-sm font-bold font-mono text-white">
          {new Date(item.date).getDate()}
        </span>
      </div>

      {/* Ticker + name */}
      <div className="min-w-0 flex-1">
        <p className="font-medium text-white">{item.ticker}</p>
        <p className="truncate text-[13px] text-zinc-600">{item.name}</p>
      </div>

      {/* Score bar */}
      <div className="hidden items-center gap-2 sm:flex">
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/10">
          <div
            className={`h-full rounded-full ${scoreColor(item.score)}`}
            style={{ width: `${Math.min(item.score, 100)}%` }}
          />
        </div>
        <span className="text-xs font-medium font-mono text-zinc-300 tabular-nums">
          {item.score}
        </span>
      </div>

      {/* Signal badge */}
      <span
        className={`rounded-md px-2.5 py-1 text-[9px] font-bold ${signalColor(item.signal)}`}
      >
        {item.signal}
      </span>
    </div>
  );
}

/* ── Page ── */

export default function EarningsPage() {
  const { data, isLoading } = useEarnings();
  const items = data?.earnings ?? [];
  const now = useMemo(() => new Date(), []);

  const groups = useMemo(() => groupByWeek(items, now), [items, now]);

  const upcomingItems = useMemo(
    () => items.filter((i) => new Date(i.date) >= now),
    [items, now],
  );

  const nextDate = useMemo(() => {
    if (!upcomingItems.length) return null;
    const sorted = [...upcomingItems].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    );
    return sorted[0].date;
  }, [upcomingItems]);

  const buyCount = useMemo(
    () => upcomingItems.filter((i) => i.signal === "BUY").length,
    [upcomingItems],
  );

  /* Loading */
  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  /* Empty */
  if (!items.length) {
    return (
      <div className="glass-surface rounded-2xl py-12 text-center">
        <Calendar className="mx-auto h-10 w-10 text-zinc-600" />
        <p className="mt-3 text-[13px] text-zinc-600">
          No upcoming earnings data available.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-4 py-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Earnings Calendar
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Upcoming earnings reports for stocks in your universe
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard
          icon={Calendar}
          label="Upcoming Earnings"
          value={`${upcomingItems.length}`}
          sub="Reports scheduled"
        />
        <SummaryCard
          icon={Clock}
          label="Next Report"
          value={nextDate ? formatDate(nextDate) : "--"}
          sub={nextDate ? `${upcomingItems.length} stocks reporting soon` : undefined}
        />
        <SummaryCard
          icon={TrendingUp}
          label="BUY-Rated Reporting"
          value={`${buyCount}`}
          sub={
            upcomingItems.length
              ? `${Math.round((buyCount / upcomingItems.length) * 100)}% of upcoming`
              : undefined
          }
        />
      </div>

      {/* Timeline */}
      {groups.map((group) => (
        <div key={group.label}>
          <h2 className="mb-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-600">
            {group.label}
          </h2>
          <div className="glass-surface rounded-xl overflow-hidden">
            {group.items.map((item) => (
              <EarningsRow key={`${item.ticker}-${item.date}`} item={item} />
            ))}
          </div>
        </div>
      ))}

      {/* Disclaimer */}
      <p className="text-center text-[13px] text-zinc-600">
        Earnings dates are sourced from public filings and may change.
        Signals and scores reflect the latest quantitative analysis.
      </p>
    </div>
  );
}
