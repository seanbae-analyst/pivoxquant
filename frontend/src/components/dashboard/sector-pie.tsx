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
  "#3b8bff", "#00d68f", "#ffb84d", "#9c6cff", "#00d4ff",
  "#ff4757", "#ff6b9d", "#2ed573", "#ffa502", "#70a1ff",
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
                background: "#111822",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(v) => [`${v}%`, "Weight"]}
            />
            <Legend
              iconSize={8}
              wrapperStyle={{ fontSize: 11, color: "#6b7d95" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
