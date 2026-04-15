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

/* ── Greeting helper ── */

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "좋은 아침이에요";
  if (h < 18) return "좋은 오후예요";
  return "좋은 저녁이에요";
}

function formatDate(): string {
  return new Date().toLocaleDateString("ko-KR", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/* ── Dashboard Page ── */

export default function HomePage() {
  const { user } = useAuth();
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
            {getGreeting()}, {firstName}
          </h1>
          <p className="text-sm text-slate-500">{formatDate()}</p>
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
