"use client";

/**
 * <SectorAllocationDonut /> — sector breakdown of current positions.
 *
 * Source: aggregates `usePortfolioPositions()` rows by `sector`, summed by
 * `current * shares`. No backend call — derived locally from the same
 * positions table the rest of /home already uses.
 *
 * Library: recharts 3.x. Single donut + legend, no animation, ink theme.
 *
 * Empty state: explicit "No positions yet" — no mock data.
 */

import { useMemo } from "react";
import Link from "next/link";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";

import type { Position } from "@/components/portfolio/types";

interface SectorAllocationDonutProps {
  positions: Position[];
  currency?: "USD" | "KRW";
  height?: number;
}

interface SectorRow {
  sector: string;
  value: number;
  count: number;
  pct: number;
  color: string;
}

/** Sector palette — distinct hues kept inside the muted Vantablack tone
 *  family. Each sector gets its own identity so the donut reads at a
 *  glance, but no color is bright/saturated enough to break the editorial
 *  ink mood. CEO directive 2026-04-27: previous bronze-only ramp was
 *  unreadable. Hues: bronze / sage / dusty-blue / muted-rose / mauve /
 *  warm-grey / olive / steel — calibrated lightness ~55-65 / chroma low. */
const SECTOR_PALETTE = [
  "#B8956A",  // bronze         — primary
  "#7DB487",  // sage green
  "#7AA0C8",  // dusty blue
  "#C28F8F",  // muted rose
  "#9B89B3",  // dusty mauve
  "#B5A98F",  // warm grey
  "#9AAB7E",  // olive
  "#88A6B8",  // steel blue
  "#C4A47C",  // sand
  "#A8908F",  // taupe-rose
];

/** Fallback for sectors beyond the palette length. */
const BRONZE_TAIL = "#6F5636";

function fmtMoney(n: number, currency: "USD" | "KRW"): string {
  if (!Number.isFinite(n)) return "—";
  if (currency === "KRW") {
    if (Math.abs(n) >= 1e8) return `₩${(n / 1e8).toFixed(2)}억`;
    if (Math.abs(n) >= 1e4) return `₩${(n / 1e4).toFixed(0)}만`;
    return `₩${Math.round(n).toLocaleString("ko-KR")}`;
  }
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

interface RechartsTooltipPayloadEntry {
  payload?: SectorRow;
}
interface DonutTooltipProps {
  active?: boolean;
  payload?: RechartsTooltipPayloadEntry[];
  currency: "USD" | "KRW";
}

function DonutTooltip({ active, payload, currency }: DonutTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div
      style={{
        background: "rgba(10, 10, 10, 0.92)",
        border: "1px solid rgba(184, 149, 106, 0.32)",
        padding: "8px 12px",
        fontSize: 11,
        lineHeight: 1.55,
        color: "var(--pq-ivory)",
      }}
    >
      {/* Sector name — serif (text identity, not a number/code). */}
      <div
        className="font-serif"
        style={{
          color: "var(--pq-bronze)",
          letterSpacing: "0.04em",
          marginBottom: 4,
          fontSize: 12,
        }}
      >
        {row.sector}
      </div>
      <div className="font-mono tabular-nums">
        {row.pct.toFixed(1)}%{" "}
        <span className="font-serif" style={{ fontSize: 10.5, color: "rgba(245,240,232,0.55)" }}>
          of book
        </span>
      </div>
      <div
        className="font-mono tabular-nums"
        style={{ color: "rgba(245, 240, 232, 0.7)" }}
      >
        {fmtMoney(row.value, currency)}
        <span
          className="font-serif"
          style={{ fontSize: 10.5, color: "rgba(245,240,232,0.55)", marginLeft: 6 }}
        >
          · {row.count} {row.count === 1 ? "position" : "positions"}
        </span>
      </div>
    </div>
  );
}

export function SectorAllocationDonut({
  positions,
  currency = "USD",
  height = 240,
}: SectorAllocationDonutProps) {
  const rows: SectorRow[] = useMemo(() => {
    if (positions.length === 0) return [];

    const buckets = new Map<string, { value: number; count: number }>();
    for (const p of positions) {
      const cur = p.current ?? 0;
      const mv = cur * (p.shares ?? 0);
      if (!Number.isFinite(mv) || mv <= 0) continue;
      const sector = (p.sector || "Unclassified").trim() || "Unclassified";
      const acc = buckets.get(sector) ?? { value: 0, count: 0 };
      acc.value += mv;
      acc.count += 1;
      buckets.set(sector, acc);
    }
    if (buckets.size === 0) return [];

    const total = Array.from(buckets.values()).reduce(
      (s, b) => s + b.value,
      0,
    );
    if (total <= 0) return [];

    const sorted = Array.from(buckets.entries())
      .sort((a, b) => b[1].value - a[1].value)
      .map(([sector, b], i) => ({
        sector,
        value: b.value,
        count: b.count,
        pct: (b.value / total) * 100,
        color: SECTOR_PALETTE[i] ?? BRONZE_TAIL,
      }));

    return sorted;
  }, [positions]);

  const totalValue = useMemo(
    () => rows.reduce((s, r) => s + r.value, 0),
    [rows],
  );

  /* ── Empty state ── */

  if (rows.length === 0) {
    return (
      <div
        style={{
          background: "var(--pq-card-bg-ink)",
          border: "1px solid var(--pq-hairline-ink)",
          height,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: 20,
          textAlign: "center",
          gap: 10,
        }}
      >
        <div
          className="font-mono uppercase"
          style={{
            fontSize: 9,
            letterSpacing: "0.24em",
            color: "rgba(245, 240, 232, 0.4)",
          }}
        >
          No data
        </div>
        <div
          className="font-serif"
          style={{
            fontSize: 12,
            lineHeight: 1.6,
            color: "rgba(245, 240, 232, 0.6)",
            maxWidth: 240,
          }}
        >
          No positions yet. Add to see sector breakdown.
        </div>
        <Link
          href="/portfolio"
          className="pq-ink-btn-ghost"
          style={{ height: 30, padding: "0 12px", fontSize: 10, marginTop: 4 }}
        >
          Open Portfolio
        </Link>
      </div>
    );
  }

  /* ── Donut + legend ── */

  const topSectors = rows
    .slice(0, 3)
    .map((r) => `${r.sector} ${r.pct.toFixed(1)}%`)
    .join(", ");
  const ariaLabel = `Sector allocation donut chart, ${rows.length} sectors, total ${fmtMoney(totalValue, currency)}. Top: ${topSectors}.`;

  return (
    <div
      style={{
        background: "var(--pq-card-bg-ink)",
        border: "1px solid var(--pq-hairline-ink)",
        padding: 12,
        height,
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.1fr)",
        gap: 12,
      }}
      role="img"
      aria-label={ariaLabel}
    >
      {/* ── Donut ── */}
      <div style={{ position: "relative", minWidth: 0 }} aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="sector"
              cx="50%"
              cy="50%"
              innerRadius="62%"
              outerRadius="92%"
              stroke="rgba(10, 10, 10, 0.6)"
              strokeWidth={1}
              isAnimationActive={false}
              startAngle={90}
              endAngle={-270}
            >
              {rows.map((r) => (
                <Cell key={r.sector} fill={r.color} />
              ))}
            </Pie>
            <Tooltip
              content={(props: unknown) => {
                const p = props as {
                  active?: boolean;
                  payload?: RechartsTooltipPayloadEntry[];
                };
                return (
                  <DonutTooltip
                    active={p.active}
                    payload={p.payload}
                    currency={currency}
                  />
                );
              }}
            />
          </PieChart>
        </ResponsiveContainer>

        {/* Centre label */}
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            textAlign: "center",
          }}
        >
          <div
            className="font-mono uppercase"
            style={{
              fontSize: 9,
              letterSpacing: "0.22em",
              color: "rgba(245, 240, 232, 0.5)",
              marginBottom: 2,
            }}
          >
            {rows.length} {rows.length === 1 ? "sector" : "sectors"}
          </div>
          <div
            className="font-serif"
            style={{
              fontSize: 16,
              color: "var(--pq-ivory)",
              lineHeight: 1.1,
            }}
          >
            {fmtMoney(totalValue, currency)}
          </div>
        </div>
      </div>

      {/* ── Legend ── */}
      <ul
        style={{
          listStyle: "none",
          margin: 0,
          padding: "4px 4px 4px 0",
          display: "flex",
          flexDirection: "column",
          gap: 4,
          minWidth: 0,
          overflowY: "auto",
          fontSize: 11,
        }}
      >
        {rows.map((r) => (
          <li
            key={r.sector}
            style={{
              display: "grid",
              gridTemplateColumns: "10px minmax(0, 1fr) auto",
              alignItems: "center",
              gap: 8,
              padding: "3px 0",
              borderBottom: "0.5px solid rgba(245, 240, 232, 0.05)",
              minWidth: 0,
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 10,
                height: 10,
                background: r.color,
                borderRadius: 1,
                display: "inline-block",
              }}
            />
            <span
              className="font-serif"
              style={{
                color: "rgba(245, 240, 232, 0.78)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                fontSize: 12,
              }}
              title={`${r.sector} · ${r.count} ${r.count === 1 ? "position" : "positions"}`}
            >
              {r.sector}
            </span>
            <span
              className="font-mono"
              style={{
                color: "var(--pq-bronze)",
                fontVariantNumeric: "tabular-nums",
                fontSize: 11,
              }}
            >
              {r.pct.toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default SectorAllocationDonut;
