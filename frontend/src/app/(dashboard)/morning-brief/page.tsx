"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Sunrise,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Archive,
  ArrowRight,
} from "lucide-react";
import { useMorningBriefArchive, useMorningBrief } from "@/lib/hooks";
import { useLocale, useT } from "@/lib/locale";
import { cn } from "@/lib/utils";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import { MorningBriefCard } from "@/components/dashboard/morning-brief-card";
import type {
  MorningBriefArchiveItem,
  MorningBriefIndex,
} from "@/lib/types";

/* ── Filter options ── */

type FilterKey = "all" | "week" | "month";

const FILTERS: { key: FilterKey; labelKey: string }[] = [
  { key: "all", labelKey: "morningBrief.filterAll" },
  { key: "week", labelKey: "morningBrief.filterWeek" },
  { key: "month", labelKey: "morningBrief.filterMonth" },
];

/* ── Helpers ── */

function formatArchiveDate(dateStr: string, locale: "ko" | "en"): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  if (locale === "ko") {
    return d.toLocaleDateString("ko-KR", {
      month: "long",
      day: "numeric",
      weekday: "short",
    });
  }
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    weekday: "short",
  });
}

function fmtPctSigned(pct: number): string {
  const s = pct >= 0 ? "+" : "";
  return `${s}${pct.toFixed(1)}%`;
}

function pctColor(pct: number): string {
  if (pct > 0) return "text-emerald-600";
  if (pct < 0) return "text-red-600";
  return "text-slate-500";
}

function filterItems(
  items: MorningBriefArchiveItem[],
  filter: FilterKey,
): MorningBriefArchiveItem[] {
  if (filter === "all") return items;
  const now = Date.now();
  const cutoff =
    filter === "week" ? 7 * 86400 * 1000 : 30 * 86400 * 1000;
  return items.filter((item) => {
    const t = new Date(item.date).getTime();
    return Number.isFinite(t) && now - t <= cutoff;
  });
}

/* ── Compact index row ── */

function IndexMini({
  label,
  data,
}: {
  label: string;
  data?: MorningBriefIndex;
}) {
  return (
    <div className="flex items-baseline gap-1">
      <span className="text-[11px] text-slate-400">{label}</span>
      <span
        className={cn(
          "text-xs font-semibold tabular-nums",
          data ? pctColor(data.change_pct) : "text-slate-300",
        )}
      >
        {data ? fmtPctSigned(data.change_pct) : "—"}
      </span>
    </div>
  );
}

/* ── Archive card ── */

function ArchiveCard({ item }: { item: MorningBriefArchiveItem }) {
  const [expanded, setExpanded] = useState(false);
  const t = useT();
  const { locale } = useLocale();

  const brief = item.content;
  const topPortfolio = brief.portfolio_changes.slice(0, 3);

  return (
    <article className="sp-card overflow-hidden">
      {/* Header — always visible */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-3 px-4 py-4 text-left transition-colors hover:bg-slate-50/50"
      >
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex items-center gap-2">
            <CalendarDays className="h-3.5 w-3.5 text-slate-400" aria-hidden />
            <time className="text-sm font-bold text-slate-900">
              {formatArchiveDate(item.date, locale)}
            </time>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <IndexMini label="S&P" data={brief.market_summary.sp500} />
            <IndexMini label="NASDAQ" data={brief.market_summary.nasdaq} />
            <IndexMini label="KOSPI" data={brief.market_summary.kospi} />
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
        ) : (
          <ChevronDown
            className="h-4 w-4 shrink-0 text-slate-400"
            aria-hidden
          />
        )}
      </button>

      {/* Expanded body */}
      {expanded && (
        <div className="space-y-4 border-t border-slate-100 px-4 py-4">
          {/* Portfolio */}
          {topPortfolio.length > 0 && (
            <section>
              <p className="mb-2 text-xs font-semibold text-slate-600">
                💼 {t("morningBrief.portfolio")}
              </p>
              <div className="flex flex-wrap gap-2">
                {topPortfolio.map((change) => {
                  const isUp = change.direction === "up";
                  const Icon = isUp ? TrendingUp : TrendingDown;
                  return (
                    <div
                      key={change.ticker}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold",
                        isUp
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-red-50 text-red-700",
                      )}
                    >
                      <span className="font-mono">{change.ticker}</span>
                      <Icon className="h-3 w-3" />
                      <span className="tabular-nums">
                        {fmtPctSigned(change.change_pct)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Events */}
          {brief.events.length > 0 && (
            <section>
              <p className="mb-2 text-xs font-semibold text-slate-600">
                📅 {t("morningBrief.events")}
              </p>
              <ul className="space-y-1.5">
                {brief.events.slice(0, 3).map((event, i) => (
                  <li
                    key={`${event.ticker}-${i}`}
                    className="flex items-start gap-2 text-xs text-slate-700"
                  >
                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-purple-400" />
                    <span>
                      <span className="font-mono text-slate-900">
                        {event.ticker}
                      </span>{" "}
                      {event.description}
                      {event.event_time && (
                        <span className="ml-1 text-slate-400">
                          ({event.event_time})
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Insight */}
          {brief.insight && (
            <section className="rounded-xl bg-gradient-to-br from-purple-50 to-pink-50 px-3 py-2.5">
              <p className="flex items-start gap-2 text-xs text-slate-700">
                <Sparkles
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-purple-500"
                  aria-hidden
                />
                <span className="leading-relaxed">{brief.insight}</span>
              </p>
            </section>
          )}
        </div>
      )}
    </article>
  );
}

/* ── Empty state ── */

function EmptyArchiveState() {
  const t = useT();
  return (
    <div className="sp-card flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
        <Archive className="h-5 w-5 text-slate-400" aria-hidden />
      </div>
      <h3 className="text-base font-semibold text-slate-900">
        {t("morningBrief.noArchive")}
      </h3>
      <p className="mt-1 max-w-sm text-sm text-slate-500">
        {t("morningBrief.noArchiveDesc")}
      </p>
    </div>
  );
}

/* ── Page ── */

export default function MorningBriefPage() {
  const [filter, setFilter] = useState<FilterKey>("all");
  const t = useT();

  // Prefetch today's brief so the top card renders consistently
  useMorningBrief();

  const { data: archive, isLoading } = useMorningBriefArchive();

  const items = useMemo<MorningBriefArchiveItem[]>(() => {
    const list = archive?.briefs ?? [];
    return filterItems(list, filter);
  }, [archive, filter]);

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-3xl space-y-6 pb-8">
        {/* Header */}
        <header className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500"
            aria-hidden
          >
            <Sunrise className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-slate-900">
              {t("morningBrief.title")}
            </h1>
            <p className="text-sm text-slate-500">
              {t("morningBrief.archiveSubtitle")}
            </p>
          </div>
        </header>

        {/* Disclaimer */}
        <DisclaimerBanner type="signal" />

        {/* Today's brief (reuse card) */}
        <div>
          <h2 className="mb-3 text-sm font-bold text-slate-900">
            {t("morningBrief.today")}
          </h2>
          <MorningBriefCard />
        </div>

        {/* Archive list */}
        <section aria-labelledby="archive-heading">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2
              id="archive-heading"
              className="text-sm font-bold text-slate-900"
            >
              {t("morningBrief.archive")}
            </h2>

            {/* Filter pills */}
            <div
              className="flex gap-1.5 overflow-x-auto scrollbar-hide"
              role="tablist"
              aria-label="Date filter"
            >
              {FILTERS.map((f) => {
                const active = filter === f.key;
                return (
                  <button
                    key={f.key}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setFilter(f.key)}
                    className={cn(
                      "whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
                      active
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200",
                    )}
                  >
                    {t(f.labelKey)}
                  </button>
                );
              })}
            </div>
          </div>

          {isLoading ? (
            <div className="space-y-3">
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
            </div>
          ) : items.length === 0 ? (
            <EmptyArchiveState />
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <ArchiveCard key={item.date} item={item} />
              ))}
            </div>
          )}
        </section>

        {/* Footer CTA */}
        <div className="pt-2 text-center">
          <Link
            href="/settings"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-purple-700 hover:text-purple-800"
          >
            <span>알림 설정 관리</span>
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
    </ErrorBoundary>
  );
}
