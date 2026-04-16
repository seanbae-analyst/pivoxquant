"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { usePortfolio, useAnalytics, useHistory } from "@/lib/hooks";
import { useRealtimeContext } from "@/lib/realtime";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { MetricCards } from "@/components/dashboard/metric-cards";
import { MorningBriefCard } from "@/components/dashboard/morning-brief-card";
import { EquityChart, type PeriodValue } from "@/components/dashboard/equity-chart";
import { SignalsWidget } from "@/components/dashboard/signals-widget";
import { RiskWidget } from "@/components/dashboard/risk-widget";
import { PositionsList } from "@/components/dashboard/positions-list";
import { useT, useLocale } from "@/lib/locale";

/* ── Greeting helper ── */

function getGreeting(t: (key: string) => string): string {
  const h = new Date().getHours();
  if (h < 12) return t("dashboard.greeting.morning");
  if (h < 18) return t("dashboard.greeting.afternoon");
  return t("dashboard.greeting.evening");
}

function formatDate(locale: string): string {
  const localeCode = locale === "ko" ? "ko-KR" : "en-US";
  return new Date().toLocaleDateString(localeCode, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/* ── Dashboard Page ── */

export default function HomePage() {
  const { user } = useAuth();
  const { locale } = useLocale();
  const t = useT();
  const [period, setPeriod] = useState<PeriodValue>("1mo");

  const {
    data: portfolio,
    isLoading: portfolioLoading,
  } = usePortfolio();

  const {
    data: analytics,
    isLoading: analyticsLoading,
  } = useAnalytics();

  const {
    data: history,
    isLoading: historyLoading,
  } = useHistory(period);

  const realtimeCtx = useRealtimeContext();

  const firstName = user?.name?.split(" ")[0] ?? "there";

  return (
    <ErrorBoundary>
      <div className="space-y-6 pb-8">
        {/* Greeting header */}
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-2xl font-bold text-slate-900">
            {getGreeting(t)}, {firstName}
          </h1>
          <p className="text-sm text-slate-500">{formatDate(locale)}</p>
        </div>

        {/* Metric cards */}
        <MetricCards
          portfolio={portfolio}
          analytics={analytics}
          isLoading={portfolioLoading || analyticsLoading}
        />

        {/* Morning Brief — inserted right after metric cards */}
        <MorningBriefCard />

        {/* Disclaimer */}
        <DisclaimerBanner type="signal" />

        {/* Equity chart */}
        <EquityChart
          data={history?.data}
          isLoading={historyLoading}
          activePeriod={period}
          onPeriodChange={setPeriod}
        />

        {/* Signals + Risk row */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SignalsWidget
            positions={portfolio?.positions}
            isLoading={portfolioLoading}
          />
          <RiskWidget
            analytics={analytics}
            isLoading={analyticsLoading}
            hasPositions={(portfolio?.positions?.length ?? 0) > 0}
          />
        </div>

        {/* Positions list */}
        <PositionsList
          positions={portfolio?.positions}
          updatedTickers={realtimeCtx.updatedTickers}
          isLoading={portfolioLoading}
        />
      </div>
    </ErrorBoundary>
  );
}
