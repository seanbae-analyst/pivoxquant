"use client";

import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";

const COLORS = ["#22d3ee", "#34d399", "#fbbf24", "#f472b6", "#818cf8", "#f87171", "#06b6d4", "#f97316", "#6366f1", "#14b8a6"];

interface Props {
  sectorAllocation: Record<string, number>;
}

export function SectorPie({ sectorAllocation }: Props) {
  const chartData = Object.entries(sectorAllocation)
    .map(([name, value]) => ({ name, value: +value.toFixed(1) }))
    .sort((a, b) => b.value - a.value);

  if (!chartData.length) return null;

  return (
    <div className="rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-6">
      <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">Sector Allocation</p>
      <div className="mt-4 h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={chartData} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={3} dataKey="value" strokeWidth={0}>
              {chartData.map((_, i) => (<Cell key={i} fill={COLORS[i % COLORS.length]} />))}
            </Pie>
            <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 12, fontSize: 12, color: "#fafafa" }} formatter={(v) => [`${v}%`, "Weight"]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2">
        {chartData.map((item, i) => (
          <div key={item.name} className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
            <span className="text-[11px] text-zinc-500">{item.name}</span>
            <span className="text-[11px] font-semibold text-zinc-300">{item.value}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
