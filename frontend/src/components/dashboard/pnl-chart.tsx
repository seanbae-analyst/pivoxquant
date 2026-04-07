"use client";

import { Card } from "@/components/ui/card";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { fmtUsd } from "@/lib/format";
import type { HistoryPoint } from "@/lib/types";

interface Props {
  data: HistoryPoint[];
}

export function PnlChart({ data }: Props) {
  if (!data.length) return null;

  const isUp = data[data.length - 1].value >= data[0].value;
  const color = isUp ? "#00d68f" : "#ff4757";

  return (
    <Card className="border-border bg-card p-5">
      <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
        Portfolio Value
      </p>
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => d.slice(5)}
              tick={{ fontSize: 10, fill: "#6b7d95" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v: number) => fmtUsd(v)}
              tick={{ fontSize: 10, fill: "#6b7d95" }}
              axisLine={false}
              tickLine={false}
              width={70}
            />
            <Tooltip
              contentStyle={{
                background: "#111822",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(v) => [fmtUsd(Number(v)), "Value"]}
              labelFormatter={(d) => String(d)}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              fill="url(#pnlGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
