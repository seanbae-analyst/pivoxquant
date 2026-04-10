"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { useHistory } from "@/lib/hooks";
import { fmtUsd } from "@/lib/format";

const periods = [
  { key: "5d", label: "1W" },
  { key: "1mo", label: "1M" },
  { key: "3mo", label: "3M" },
  { key: "6mo", label: "6M" },
  { key: "1y", label: "1Y" },
];

export function TerminalChart() {
  const [period, setPeriod] = useState("1mo");
  const { data } = useHistory(period);
  const points = (data?.data ?? []).filter(p => p.value != null && !isNaN(p.value));

  const isUp = points.length > 1 && points[points.length - 1].value >= points[0].value;
  const color = isUp ? "#10b981" : "#ef4444";
  const glowColor = isUp ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.06)";
  const change = points.length > 1
    ? ((points[points.length - 1].value - points[0].value) / points[0].value * 100)
    : 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 shrink-0 border-b border-slate-200">
        <div className="flex items-center gap-4">
          <span className="text-[10px] text-slate-400 uppercase tracking-[0.15em] font-semibold">Portfolio P&L</span>
          {points.length > 0 && (
            <>
              <span className="text-[20px] font-bold text-slate-900 font-mono tracking-tight"
                style={{ fontFamily: "var(--font-geist-heading), monospace" }}>
                {fmtUsd(points[points.length - 1].value)}
              </span>
              <span
                className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full ${
                  isUp
                    ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
                    : "bg-red-50 text-red-600 border border-red-200"
                }`}
              >
                {change >= 0 ? "+" : ""}{change.toFixed(2)}%
              </span>
            </>
          )}
        </div>
        {/* Period toggles */}
        <div className="flex items-center gap-0.5 rounded-full px-1 py-0.5 border border-slate-200 bg-slate-50">
          {periods.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`text-[10px] font-semibold px-3 py-1 rounded-full spring-transition transition-all duration-300 ${
                period === p.key
                  ? "bg-emerald-50 text-emerald-600 shadow-sm"
                  : "text-slate-400 hover:text-slate-700"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 min-h-0 px-3 pb-2 relative">
        <div
          className="absolute inset-x-0 top-1/3 h-1/3 blur-3xl pointer-events-none opacity-60"
          style={{ background: glowColor }}
        />
        {points.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points}>
              <defs>
                <linearGradient id="termGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.12} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" />
              <XAxis
                dataKey="date"
                tickFormatter={(d: string) => d.slice(5)}
                tick={{ fontSize: 9, fill: "#94a3b8" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={["dataMin", "dataMax"]}
                tickFormatter={(v: number) => fmtUsd(v)}
                tick={{ fontSize: 9, fill: "#94a3b8" }}
                axisLine={false}
                tickLine={false}
                width={70}
              />
              <Tooltip
                contentStyle={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: 14,
                  fontSize: 11,
                  color: "#0f172a",
                  boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
                  padding: "10px 14px",
                }}
                formatter={(v) => [fmtUsd(Number(v)), "Value"]}
                labelFormatter={(d) => String(d)}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                fill="url(#termGrad)"
                animationDuration={800}
                animationEasing="ease-out"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-slate-400 text-[12px]">Loading chart...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
