"use client";

import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { cn } from "@/lib/utils";
import { fmtUsd } from "@/lib/format";
import { Skeleton } from "@/components/ui/loading-skeleton";
import type { HistoryPoint } from "@/lib/types";

/* ── Period selector ── */

const PERIODS = [
  { label: "1W", value: "5d" },
  { label: "1M", value: "1mo" },
  { label: "3M", value: "3mo" },
  { label: "6M", value: "6mo" },
  { label: "1Y", value: "1y" },
  { label: "All", value: "max" },
] as const;

type PeriodValue = (typeof PERIODS)[number]["value"];

/* ── Custom tooltip ── */

interface TooltipPayloadItem {
  value: number;
  payload: HistoryPoint;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  if (!point?.payload) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
      <p className="text-xs text-slate-500">{point.payload?.date ?? ""}</p>
      <p className="text-sm font-bold text-slate-900 tabular-nums">
        {fmtUsd(point.value ?? 0)}
      </p>
    </div>
  );
}

/* ── Chart component ── */

interface EquityChartProps {
  data: HistoryPoint[] | undefined;
  isLoading: boolean;
  onPeriodChange: (period: PeriodValue) => void;
  activePeriod: string;
}

export function EquityChart({
  data,
  isLoading,
  onPeriodChange,
  activePeriod,
}: EquityChartProps) {
  const chartData = useMemo(() => {
    if (!data?.length) return [];
    return data
      .filter((d) => d?.value != null && isFinite(d.value))
      .map((d) => ({
        ...d,
        // Shorten date labels for X axis
        label: new Date(d.date).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
        }),
      }));
  }, [data]);

  const yDomain = useMemo(() => {
    if (!chartData.length) return [0, 100];
    const values = chartData.map((d) => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.05 || 100;
    return [Math.floor(min - pad), Math.ceil(max + pad)];
  }, [chartData]);

  return (
    <div className="sp-card p-6 overflow-hidden">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6">
        <h3 className="text-base font-bold text-slate-900">
          Portfolio Performance
        </h3>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => onPeriodChange(p.value)}
              className={cn(
                "filter-pill text-xs",
                activePeriod === p.value ? "active" : "",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : chartData.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-slate-400 text-sm">
          No performance data yet. Add positions to see your equity curve.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280} minHeight={200} maxHeight={400}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#f1f5f9"
              vertical={false}
            />
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={yDomain}
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              tickFormatter={(v: number) =>
                v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`
              }
              width={56}
            />
            <Tooltip content={<ChartTooltip />} />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#8b5cf6"
              strokeWidth={2}
              fill="url(#equityFill)"
              animationDuration={600}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

/* Re-export period type for parent usage */
export type { PeriodValue };
export { PERIODS };
