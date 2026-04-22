"use client";

import type { Position } from "./types";

interface SectorAllocationProps {
  positions: Position[];
  totalMarketValue: number;
}

/* Flat, editorial stacked bar — no gradients, no soft shadows. */
const SECTOR_PALETTE: Record<string, string> = {
  Technology: "#0A0A0A",
  Communication: "#8B6F47",
  Financials: "#6B6B6B",
  Energy: "#A3845C",
  Healthcare: "#404040",
  Other: "#D4CEC4",
};

export function SectorAllocation({
  positions,
  totalMarketValue,
}: SectorAllocationProps) {
  const buckets = new Map<string, number>();
  for (const p of positions) {
    const mv = p.shares * p.current;
    buckets.set(p.sector, (buckets.get(p.sector) ?? 0) + mv);
  }

  const rows = Array.from(buckets.entries())
    .map(([sector, mv]) => ({
      sector,
      mv,
      pct: totalMarketValue > 0 ? (mv / totalMarketValue) * 100 : 0,
    }))
    .sort((a, b) => b.pct - a.pct);

  return (
    <section className="bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 pb-3">
        <h2 className="font-serif text-[18px] italic text-slate-900">
          Sector Allocation
        </h2>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          {rows.length} sectors
        </span>
      </header>

      <div className="pt-4">
        <div className="flex h-3 w-full overflow-hidden rounded-sm">
          {rows.map((r) => (
            <div
              key={r.sector}
              style={{
                width: `${r.pct}%`,
                backgroundColor:
                  SECTOR_PALETTE[r.sector] ?? SECTOR_PALETTE.Other,
              }}
              aria-label={`${r.sector} ${r.pct.toFixed(1)}%`}
            />
          ))}
        </div>

        <ul className="mt-4 space-y-2">
          {rows.map((r) => (
            <li
              key={r.sector}
              className="flex items-center justify-between text-[13px]"
            >
              <div className="flex items-center gap-2.5">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{
                    backgroundColor:
                      SECTOR_PALETTE[r.sector] ?? SECTOR_PALETTE.Other,
                  }}
                />
                <span className="text-slate-800">{r.sector}</span>
              </div>
              <span className="font-mono tabular-nums text-slate-700">
                {r.pct.toFixed(1)}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
