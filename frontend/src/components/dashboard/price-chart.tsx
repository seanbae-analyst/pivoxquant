"use client";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/loading-skeleton";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { RefreshCw } from "lucide-react";

const PERIODS = ["1W", "1M", "3M", "6M", "1Y"] as const;

interface ChartPoint {
  date: string;
  close: number;
}

interface PriceChartProps {
  data: ChartPoint[] | undefined;
  isLoading: boolean;
  error?: Error | null;
  onRetry?: () => void;
  period: string;
  onPeriodChange: (p: string) => void;
  className?: string;
  currency?: "USD" | "KRW";
}

function CustomTooltip({
  active,
  payload,
  label,
  currency,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
  currency?: "USD" | "KRW";
}) {
  if (!active || !payload?.length) return null;
  const val = payload[0]?.value;
  if (val == null) return null;
  const isKrw = currency === "KRW";
  const display = isKrw
    ? `₩${Math.round(val).toLocaleString("ko-KR")}`
    : `$${val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
      <p className="text-xs text-slate-500">{label ?? ""}</p>
      <p className="text-sm font-bold tabular-nums text-slate-900">
        {display}
      </p>
    </div>
  );
}

export function PriceChart({
  data,
  isLoading,
  error,
  onRetry,
  period,
  onPeriodChange,
  className,
  currency = "USD",
}: PriceChartProps) {
  const isKrw = currency === "KRW";
  if (isLoading) {
    return (
      <div className={cn("sp-card p-5", className)}>
        <div className="flex items-center justify-between mb-4">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-8 w-48" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const chartData = (data ?? []).filter(
    (d) => d?.close != null && isFinite(d.close),
  );
  const minPrice = chartData.length
    ? Math.min(...chartData.map((d) => d.close)) * 0.995
    : 0;
  const maxPrice = chartData.length
    ? Math.max(...chartData.map((d) => d.close)) * 1.005
    : 100;

  return (
    <div className={cn("sp-card p-5 overflow-hidden", className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-bold text-slate-900">Price</h3>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => onPeriodChange(p)}
              className={cn(
                "filter-pill",
                period === p ? "active" : "",
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          <p className="text-sm text-slate-400">
            Unable to load chart data
          </p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </button>
          )}
        </div>
      ) : chartData.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-sm text-slate-400">
          No chart data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280} minHeight={200} maxHeight={400}>
          <AreaChart
            data={chartData}
            margin={{ top: 4, right: 4, bottom: 0, left: 4 }}
          >
            <defs>
              <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              tickMargin={8}
              minTickGap={40}
            />
            <YAxis
              domain={[minPrice, maxPrice]}
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              tickFormatter={(v: number) =>
                isKrw
                  ? (v >= 10000 ? `₩${(v / 10000).toFixed(0)}만` : `₩${Math.round(v).toLocaleString("ko-KR")}`)
                  : (v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`)
              }
              width={60}
            />
            <Tooltip
              content={<CustomTooltip currency={currency} />}
              cursor={{ stroke: "#e2e8f0", strokeDasharray: "4 4" }}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke="#8b5cf6"
              strokeWidth={2}
              fill="url(#priceGradient)"
              animationDuration={600}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
