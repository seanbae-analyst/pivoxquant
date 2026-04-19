"use client";

import Link from "next/link";
import {
  Sunrise,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  CalendarDays,
  Sparkles,
  Moon,
} from "lucide-react";
import { useMorningBrief } from "@/lib/hooks";
import { usePortfolio } from "@/lib/hooks";
import { useLocale, useT } from "@/lib/locale";
import { cn } from "@/lib/utils";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import type {
  MorningBriefContent,
  MorningBriefIndex,
} from "@/lib/types";

/* ── Helpers ── */

function formatToday(locale: "ko" | "en"): string {
  const d = new Date();
  if (locale === "ko") {
    return d.toLocaleDateString("ko-KR", {
      month: "long",
      day: "numeric",
    });
  }
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric" });
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

/* ── Index Cell ── */

function IndexCell({
  label,
  data,
}: {
  label: string;
  data?: MorningBriefIndex;
}) {
  if (!data) {
    return (
      <div className="min-w-0">
        <p className="text-[11px] font-medium text-slate-400">{label}</p>
        <p className="text-sm font-semibold text-slate-300">—</p>
      </div>
    );
  }
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-medium text-slate-400">{label}</p>
      <p
        className={cn(
          "text-sm font-bold tabular-nums",
          pctColor(data.change_pct),
        )}
      >
        {fmtPctSigned(data.change_pct)}
      </p>
    </div>
  );
}

/* ── Brief body ── */

function BriefBody({ brief }: { brief: MorningBriefContent }) {
  const t = useT();
  const { market_summary, portfolio_changes, events, insight } = brief;

  const topPortfolio = portfolio_changes.slice(0, 4);

  return (
    <div className="space-y-4">
      {/* Market summary */}
      <section>
        <p className="mb-2 text-xs font-semibold text-slate-600">
          📊 {t("morningBrief.yesterdayClose")}
        </p>
        <div className="grid grid-cols-3 gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <IndexCell label="S&P 500" data={market_summary.sp500} />
          <IndexCell label="NASDAQ" data={market_summary.nasdaq} />
          <IndexCell label="KOSPI" data={market_summary.kospi} />
        </div>
      </section>

      {/* Portfolio changes */}
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
                    "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
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
      {events.length > 0 && (
        <section>
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-slate-600">
            <CalendarDays className="h-3.5 w-3.5" />
            {t("morningBrief.events")}
          </p>
          <ul className="space-y-1.5">
            {events.slice(0, 3).map((event, i) => (
              <li
                key={`${event.ticker}-${i}`}
                className="flex items-start gap-2 text-xs text-slate-700"
              >
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-accent" />
                <span className="font-medium">
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

      {/* AI Insight */}
      {insight && (
        <section className="rounded-xl bg-muted border-l-2 border-accent px-4 py-3">
          <p className="flex items-start gap-2 text-xs text-slate-700">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
            <span className="leading-relaxed">{insight}</span>
          </p>
        </section>
      )}
    </div>
  );
}

/* ── States ── */

function NotAvailableState() {
  const t = useT();
  return (
    <div className="flex flex-col items-center justify-center rounded-xl bg-slate-50 px-4 py-6 text-center">
      <Moon className="mb-2 h-6 w-6 text-slate-400" />
      <p className="text-sm font-semibold text-slate-700">
        {t("morningBrief.notAvailable")}
      </p>
      <p className="mt-1 text-xs text-slate-500">
        {t("morningBrief.notAvailableDesc")}
      </p>
    </div>
  );
}

function NoPositionsState() {
  const t = useT();
  return (
    <div className="flex flex-col items-center justify-center rounded-xl bg-slate-50 px-4 py-6 text-center">
      <p className="text-sm font-semibold text-slate-700">
        {t("morningBrief.noPositionsTitle")}
      </p>
      <p className="mt-1 mb-3 text-xs text-slate-500">
        {t("morningBrief.noPositionsDesc")}
      </p>
      <Link
        href="/portfolio"
        className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]"
      >
        {t("morningBrief.addPosition")}
        <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

/* ── Main card ── */

export function MorningBriefCard() {
  const { data, isLoading } = useMorningBrief();
  const { data: portfolio } = usePortfolio();
  const t = useT();
  const { locale } = useLocale();

  const hasPositions = (portfolio?.positions?.length ?? 0) > 0;

  return (
    <section
      className="sp-card overflow-hidden p-5 sm:p-6"
      aria-labelledby="morning-brief-heading"
    >
      {/* Header */}
      <header className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500">
            <Sunrise className="h-[18px] w-[18px] text-white" aria-hidden />
          </div>
          <div className="min-w-0">
            <h2
              id="morning-brief-heading"
              className="text-base font-bold text-slate-900 truncate"
            >
              🌅 {t("morningBrief.title")}
            </h2>
            <p className="text-xs text-slate-500">{formatToday(locale)}</p>
          </div>
        </div>
        <Link
          href="/morning-brief"
          className="hidden sm:inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-accent/10 transition-colors"
        >
          {t("morningBrief.viewAll")}
          <ArrowRight className="h-3 w-3" />
        </Link>
      </header>

      {/* Body */}
      {isLoading ? (
        <CardSkeleton />
      ) : !hasPositions ? (
        <NoPositionsState />
      ) : !data?.available || !data.brief ? (
        <NotAvailableState />
      ) : (
        <BriefBody brief={data.brief} />
      )}

      {/* Mobile "view all" link */}
      <div className="mt-4 sm:hidden">
        <Link
          href="/morning-brief"
          className="flex items-center justify-center gap-1.5 rounded-full bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
        >
          {t("morningBrief.viewAll")}
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </section>
  );
}
