"use client";

import { Card } from "@/components/ui/card";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";

const COLORS = [
  "#6366f1", "#22c55e", "#f59e0b", "#a855f7", "#06b6d4",
  "#ef4444", "#ec4899", "#14b8a6", "#f97316", "#818cf8",
];

interface Props {
  sectorAllocation: Record<string, number>;
}

export function SectorPie({ sectorAllocation }: Props) {
  const chartData = Object.entries(sectorAllocation)
    .map(([name, value]) => ({ name, value: +value.toFixed(1) }))
    .sort((a, b) => b.value - a.value);

  if (!chartData.length) return null;

  return (
    <Card className="border-border bg-card p-5">
      <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
        Sector Allocation
      </p>
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={75}
              paddingAngle={2}
              dataKey="value"
            >
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "#111111",
                border: "1px solid #1f1f1f",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(v) => [`${v}%`, "Weight"]}
            />
            <Legend
              iconSize={8}
              wrapperStyle={{ fontSize: 11, color: "#666666" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
