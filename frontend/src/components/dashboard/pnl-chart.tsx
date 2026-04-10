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
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Portfolio Performance</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">{fmtUsd(data[data.length - 1].value)}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-bold ${
          isUp ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-600"
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
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={{ fontSize: 10, fill: "#52525b" }} axisLine={false} tickLine={false} />
            <YAxis domain={["dataMin", "dataMax"]} tickFormatter={(v: number) => fmtUsd(v)} tick={{ fontSize: 10, fill: "#52525b" }} axisLine={false} tickLine={false} width={70} />
            <Tooltip
              contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 12, fontSize: 12, color: "#0f172a", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
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
