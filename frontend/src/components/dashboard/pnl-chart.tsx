"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { fmtUsd } from "@/lib/format";
import type { HistoryPoint } from "@/lib/types";

interface Props {
  data: HistoryPoint[];
}

export function PnlChart({ data }: Props) {
  if (!data.length) return null;

  const isUp = data[data.length - 1].value >= data[0].value;
  const color = isUp ? "#34d399" : "#f87171";
  const change = data.length > 1
    ? ((data[data.length - 1].value - data[0].value) / data[0].value * 100).toFixed(2)
    : "0.00";

  return (
    <div className="rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">Portfolio Performance</p>
          <p className="mt-1 text-2xl font-bold text-white">{fmtUsd(data[data.length - 1].value)}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-bold ${
          isUp ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"
        }`}>
          {isUp ? "+" : ""}{change}%
        </span>
      </div>
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.15} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={{ fontSize: 10, fill: "#52525b" }} axisLine={false} tickLine={false} />
            <YAxis domain={["dataMin", "dataMax"]} tickFormatter={(v: number) => fmtUsd(v)} tick={{ fontSize: 10, fill: "#52525b" }} axisLine={false} tickLine={false} width={70} />
            <Tooltip
              contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 12, fontSize: 12, color: "#fafafa", boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}
              formatter={(v) => [fmtUsd(Number(v)), "Value"]}
              labelFormatter={(d) => String(d)}
            />
            <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} fill="url(#pnlGrad)" animationDuration={1200} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
