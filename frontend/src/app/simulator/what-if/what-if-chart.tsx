"use client";

/**
 * What-If Simulator — Growth Chart
 *
 * Recharts-based area + line overlay.
 * - Main line: portfolio value over time
 * - Dotted line: cumulative invested principal (for DCA scenarios)
 * - Buy-point markers on DCA mode
 *
 * Mobile-first: 240px height on small screens, 360px on desktop.
 */

import { useMemo } from "react";
import {
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  ReferenceDot,
} from "recharts";
import type { WhatIfChartPoint } from "@/lib/types";

interface WhatIfChartProps {
  data: WhatIfChartPoint[];
  currency?: "USD" | "KRW";
  showInvestedLine?: boolean;
}

/* ── Formatters (scoped to avoid locale-dep) ── */

function fmtShort(v: number, currency: "USD" | "KRW"): string {
  const symbol = currency === "KRW" ? "₩" : "$";
  const abs = Math.abs(v);
  if (currency === "KRW") {
    if (abs >= 100_000_000) return `${symbol}${(v / 100_000_000).toFixed(1)}억`;
    if (abs >= 10_000) return `${symbol}${(v / 10_000).toFixed(0)}만`;
    return `${symbol}${Math.round(v).toLocaleString()}`;
  }
  if (abs >= 1_000_000) return `${symbol}${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${symbol}${(v / 1_000).toFixed(0)}k`;
  return `${symbol}${v.toFixed(0)}`;
}

function fmtFull(v: number, currency: "USD" | "KRW"): string {
  const symbol = currency === "KRW" ? "₩" : "$";
  if (currency === "KRW") {
    return `${symbol}${Math.round(v).toLocaleString("ko-KR")}`;
  }
  return `${symbol}${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

/* ── Tooltip ── */

interface TooltipPayloadItem {
  value: number;
  dataKey: string;
  payload: WhatIfChartPoint;
  color?: string;
}

function ChartTooltip({
  active,
  payload,
  currency = "USD",
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  currency?: "USD" | "KRW";
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;

  const valueItem = payload.find((p) => p.dataKey === "value");
  const investedItem = payload.find((p) => p.dataKey === "invested");

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-lg">
      <p className="text-[11px] text-slate-500">
        {new Date(point.date).toLocaleDateString(
          currency === "KRW" ? "ko-KR" : "en-US",
          { year: "numeric", month: "short", day: "numeric" },
        )}
      </p>
      {valueItem ? (
        <p className="text-sm font-bold text-slate-900 tabular-nums">
          {fmtFull(valueItem.value, currency)}
        </p>
      ) : null}
      {investedItem && investedItem.value !== valueItem?.value ? (
        <p className="text-[11px] text-slate-500 tabular-nums">
          Invested: {fmtFull(investedItem.value, currency)}
        </p>
      ) : null}
    </div>
  );
}

/* ── Component ── */

export function WhatIfChart({
  data,
  currency = "USD",
  showInvestedLine = false,
}: WhatIfChartProps) {
  const prepared = useMemo(() => {
    if (!data?.length) return [];
    return data
      .filter((d) => d?.value != null && isFinite(d.value))
      .map((d) => ({
        ...d,
        label: new Date(d.date).toLocaleDateString("en-US", {
          month: "short",
          year: "2-digit",
        }),
      }));
  }, [data]);

  const yDomain = useMemo<[number, number]>(() => {
    if (!prepared.length) return [0, 100];
    const values = prepared.flatMap((d) => [d.value, d.invested ?? d.value]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.08 || 100;
    return [Math.max(0, Math.floor(min - pad)), Math.ceil(max + pad)];
  }, [prepared]);

  const buyPoints = useMemo(
    () => prepared.filter((d) => d.buy_point),
    [prepared],
  );

  if (!prepared.length) {
    return (
      <div className="flex h-60 w-full items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-500">
        No chart data
      </div>
    );
  }

  const ChartEl = showInvestedLine ? ComposedChart : AreaChart;
  const isSparse = buyPoints.length > 0 && buyPoints.length < 40;

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={320}>
        <ChartEl
          data={prepared}
          margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="whatIfFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0f172a" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#0f172a" stopOpacity={0} />
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
            minTickGap={40}
          />
          <YAxis
            domain={yDomain}
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v: number) => fmtShort(v, currency)}
            width={64}
          />
          <Tooltip content={<ChartTooltip currency={currency} />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#0f172a"
            strokeWidth={2.5}
            fill="url(#whatIfFill)"
            animationDuration={900}
            animationEasing="ease-out"
            dot={false}
            activeDot={{ r: 4, fill: "#0f172a" }}
          />
          {showInvestedLine ? (
            <Line
              type="stepAfter"
              dataKey="invested"
              stroke="#94a3b8"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              animationDuration={900}
            />
          ) : null}
          {showInvestedLine && isSparse
            ? buyPoints.map((pt) => (
                <ReferenceDot
                  key={pt.date}
                  x={pt.label}
                  y={pt.value}
                  r={3}
                  fill="#64748b"
                  stroke="#ffffff"
                  strokeWidth={1.5}
                />
              ))
            : null}
        </ChartEl>
      </ResponsiveContainer>
    </div>
  );
}
