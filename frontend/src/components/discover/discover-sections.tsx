"use client";

/**
 * Editorial sections for the Discover page.
 * Flat cards, tabular-nums, Bronze on positive / faint-red on negative.
 * Observation language only — POSITIVE / NEGATIVE / NEUTRAL.
 */

import { cn } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import type {
  IndexCard,
  MoverRow,
  SectorRow,
  ThematicItem,
} from "./mock-data";

function deltaTone(v: number): string {
  if (v > 0) return "text-[var(--pq-bronze,#8B6F47)]";
  if (v < 0) return "text-[#B04A3A]";
  return "text-slate-500";
}

export function SectionHeading({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <header className="mb-3 border-t border-slate-200 pt-4">
      {eyebrow && (
        <p className="text-[10px] uppercase tracking-widest text-[var(--pq-bronze,#8B6F47)]">
          {eyebrow}
        </p>
      )}
      <h2 className="mt-1 font-serif italic text-xl text-slate-900">{title}</h2>
      {subtitle && (
        <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
      )}
    </header>
  );
}

/* ── Market Overview row ── */

export function IndicesRow({ items }: { items: IndexCard[] }) {
  return (
    <ul className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-5">
      {items.map((it) => (
        <li key={it.name} className="border-t border-slate-100 pt-2">
          <p className="text-[10px] uppercase tracking-widest text-slate-400">
            {it.name}
          </p>
          <p className="mt-1 text-sm font-semibold tabular-nums text-slate-900">
            {it.level}
          </p>
          <p
            className={cn(
              "text-xs font-semibold tabular-nums",
              deltaTone(it.changePct),
            )}
          >
            {fmtPct(it.changePct)}
          </p>
        </li>
      ))}
    </ul>
  );
}

/* ── Movers table ── */

export function MoversTable({
  title,
  rows,
}: {
  title: string;
  rows: MoverRow[];
}) {
  return (
    <div>
      <h3 className="font-serif italic text-sm font-bold text-slate-900 mb-2">
        {title}
      </h3>
      <table
        className="w-full text-xs"
        style={{ tableLayout: "fixed" as const }}
      >
        <thead>
          <tr className="border-b border-slate-200 text-[10px] uppercase tracking-widest text-slate-400">
            <th className="py-1.5 text-left w-[28%]">Ticker</th>
            <th className="py-1.5 text-left">Name</th>
            <th className="py-1.5 text-right w-[22%]">Price</th>
            <th className="py-1.5 text-right w-[18%]">1D</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={r.ticker}>
              <td className="py-2 font-mono text-[11px] text-slate-700 truncate">
                {r.ticker}
              </td>
              <td className="py-2 text-slate-600 truncate pr-2">{r.name}</td>
              <td className="py-2 text-right tabular-nums text-slate-900">
                {r.price}
              </td>
              <td
                className={cn(
                  "py-2 text-right font-semibold tabular-nums",
                  deltaTone(r.changePct),
                )}
              >
                {fmtPct(r.changePct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Sector rotation table ── */

export function SectorRotationTable({ rows }: { rows: SectorRow[] }) {
  return (
    <table
      className="w-full text-xs"
      style={{ tableLayout: "fixed" as const }}
    >
      <thead>
        <tr className="border-b border-slate-200 text-[10px] uppercase tracking-widest text-slate-400">
          <th className="py-1.5 text-left">Sector</th>
          <th className="py-1.5 text-right w-[16%]">1D</th>
          <th className="py-1.5 text-right w-[16%]">5D</th>
          <th className="py-1.5 text-right w-[16%]">1M</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((r) => (
          <tr key={r.sector}>
            <td className="py-2 text-slate-700 truncate pr-2">{r.sector}</td>
            <td
              className={cn(
                "py-2 text-right font-semibold tabular-nums",
                deltaTone(r.d1),
              )}
            >
              {fmtPct(r.d1)}
            </td>
            <td
              className={cn(
                "py-2 text-right font-semibold tabular-nums",
                deltaTone(r.d5),
              )}
            >
              {fmtPct(r.d5)}
            </td>
            <td
              className={cn(
                "py-2 text-right font-semibold tabular-nums",
                deltaTone(r.m1),
              )}
            >
              {fmtPct(r.m1)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ── Thematic screener block ── */

export function ThematicBlock({
  title,
  items,
}: {
  title: string;
  items: ThematicItem[];
}) {
  return (
    <div>
      <h3 className="font-serif italic text-sm font-bold text-slate-900 mb-2">
        {title}
      </h3>
      <ul className="divide-y divide-slate-100">
        {items.map((it) => (
          <li
            key={it.ticker}
            className="grid grid-cols-[auto_1fr_auto] items-center gap-3 py-2"
          >
            <span className="font-mono text-[11px] text-slate-700 w-16 truncate">
              {it.ticker}
            </span>
            <span className="text-xs text-slate-600 truncate">{it.name}</span>
            <span className="text-xs tabular-nums text-[var(--pq-bronze,#8B6F47)] font-semibold">
              {it.metricValue}
              <span className="ml-1 text-[10px] text-slate-400 font-normal">
                {it.metric}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
