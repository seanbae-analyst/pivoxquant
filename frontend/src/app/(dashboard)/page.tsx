"use client";

import { useState, useMemo } from "react";
import { useAuth } from "@/lib/auth";
import { usePortfolio, useAnalytics, useHistory } from "@/lib/hooks";
import { SummaryCards } from "@/components/dashboard/summary-cards";
import { AnalyticsBar } from "@/components/dashboard/analytics-bar";
import { PnlChart } from "@/components/dashboard/pnl-chart";
import { SectorPie } from "@/components/dashboard/sector-pie";
import { PositionCard } from "@/components/dashboard/position-card";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type Filter = "all" | "us" | "kr" | "buy" | "etf";

const filters: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "us", label: "🇺🇸 US" },
  { key: "kr", label: "🇰🇷 KR" },
  { key: "buy", label: "BUY" },
  { key: "etf", label: "📦 ETF" },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: portfolio, mutate: refreshPortfolio } = usePortfolio();
  const { data: analytics } = useAnalytics();
  const { data: history } = useHistory("5d");
  const [filter, setFilter] = useState<Filter>("all");
  const [refreshing, setRefreshing] = useState(false);

  const filteredPositions = useMemo(() => {
    if (!portfolio?.positions) return [];
    const p = portfolio.positions;
    switch (filter) {
      case "us":
        return p.filter((x) => !x.is_korean);
      case "kr":
        return p.filter((x) => x.is_korean);
      case "buy":
        return p.filter((x) => x.signal === "BUY");
      case "etf":
        return p.filter(
          (x) => x.sector === "ETF" || x.name.toLowerCase().includes("etf"),
        );
      default:
        return [...p].sort((a, b) => b.market_value - a.market_value);
    }
  }, [portfolio?.positions, filter]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await apiFetch("/api/signals/refresh", { method: "POST" });
      await refreshPortfolio();
    } finally {
      setRefreshing(false);
    }
  };

  if (!portfolio) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Greeting */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">
            Welcome back, {user?.name ?? "Trader"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {portfolio.positions.length} positions tracked
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-xs"
        >
          {refreshing ? "Refreshing..." : "↻ Refresh Signals"}
        </Button>
      </div>

      {/* Summary Cards */}
      <SummaryCards data={portfolio} />

      {/* Analytics Bar */}
      {analytics && <AnalyticsBar data={analytics} />}

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {history?.data && <PnlChart data={history.data} />}
        {analytics?.sector_allocation && (
          <SectorPie sectorAllocation={analytics.sector_allocation} />
        )}
      </div>

      {/* Positions */}
      <div>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-mono text-[10px] font-medium uppercase tracking-[1.2px] text-muted-foreground">
            Positions
          </h2>
          {filters.map((f) => (
            <Button
              key={f.key}
              variant={filter === f.key ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter(f.key)}
              className="h-7 text-[11px]"
            >
              {f.label}
            </Button>
          ))}
        </div>

        {filteredPositions.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No positions found
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredPositions.map((pos) => (
              <PositionCard key={pos.id} position={pos} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
