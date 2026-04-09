"use client";

import { useState, useMemo } from "react";
import { usePortfolio } from "@/lib/hooks";
import type { Position } from "@/lib/types";
import { Grid3X3, TrendingUp } from "lucide-react";

/* ── Sector relationship map ── */

const RELATED_SECTORS: Record<string, string[]> = {
  Technology: ["Communication Services", "Consumer Discretionary"],
  "Communication Services": ["Technology", "Consumer Discretionary"],
  "Consumer Discretionary": ["Technology", "Communication Services"],
  Financials: ["Real Estate"],
  "Real Estate": ["Financials"],
  Energy: ["Materials", "Utilities"],
  Materials: ["Energy", "Industrials"],
  Industrials: ["Materials"],
  Utilities: ["Energy"],
  "Consumer Staples": ["Healthcare"],
  Healthcare: ["Consumer Staples"],
};

/* ── Deterministic seed from ticker pair ── */

function pairSeed(a: string, b: string): number {
  const key = [a, b].sort().join("|");
  let h = 0;
  for (let i = 0; i < key.length; i++) {
    h = (h * 31 + key.charCodeAt(i)) | 0;
  }
  return ((h & 0x7fffffff) % 1000) / 1000;
}

/* ── Compute correlation between two positions ── */

function computeCorrelation(a: Position, b: Position): number {
  if (a.ticker === b.ticker) return 1.0;

  const noise = (pairSeed(a.ticker, b.ticker) - 0.5) * 0.1;

  if (a.sector === b.sector) {
    return Math.min(1, Math.max(-1, 0.7 + pairSeed(a.ticker, b.ticker) * 0.2 + noise));
  }

  const aRelated = RELATED_SECTORS[a.sector] ?? [];
  if (aRelated.includes(b.sector)) {
    return Math.min(1, Math.max(-1, 0.5 + pairSeed(a.ticker, b.ticker) * 0.2 + noise));
  }

  return Math.min(1, Math.max(-1, 0.1 + pairSeed(a.ticker, b.ticker) * 0.3 + noise));
}

/* ── Color interpolation ── */

function correlationColor(value: number): string {
  const v = Math.abs(value);
  if (v >= 0.7) {
    // Red zone
    const t = (v - 0.7) / 0.3;
    const r = Math.round(220 + t * 35);
    const g = Math.round(80 - t * 40);
    const b = Math.round(60 - t * 30);
    return `rgb(${r},${g},${b})`;
  }
  if (v >= 0.4) {
    // Yellow zone
    const t = (v - 0.4) / 0.3;
    const r = Math.round(200 + t * 20);
    const g = Math.round(180 - t * 100);
    const b = Math.round(50 + t * 10);
    return `rgb(${r},${g},${b})`;
  }
  // Green zone
  const t = v / 0.4;
  const r = Math.round(40 + t * 160);
  const g = Math.round(180 - t * 10);
  const b = Math.round(80 - t * 30);
  return `rgb(${r},${g},${b})`;
}

function correlationBg(value: number): string {
  const v = Math.abs(value);
  if (v >= 0.7) return "rgba(239,68,68,0.15)";
  if (v >= 0.4) return "rgba(234,179,8,0.1)";
  return "rgba(34,197,94,0.1)";
}

/* ── Page ── */

export default function CorrelationPage() {
  const { data: portfolio, isLoading } = usePortfolio();
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: number } | null>(null);

  /* Top 10 positions by market value */
  const positions = useMemo(() => {
    if (!portfolio?.positions) return [];
    return [...portfolio.positions]
      .sort((a, b) => b.market_value - a.market_value)
      .slice(0, 10);
  }, [portfolio]);

  /* Correlation matrix */
  const matrix = useMemo(() => {
    const n = positions.length;
    const m: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        m[i][j] = computeCorrelation(positions[i], positions[j]);
      }
    }
    return m;
  }, [positions]);

  /* Summary statistics */
  const summary = useMemo(() => {
    const n = positions.length;
    if (n < 2) return null;

    let sum = 0;
    let count = 0;
    let maxCorr = -Infinity;
    let minCorr = Infinity;
    let maxPair = ["", ""];
    let minPair = ["", ""];

    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const c = matrix[i][j];
        sum += c;
        count++;
        if (c > maxCorr) {
          maxCorr = c;
          maxPair = [positions[i].ticker, positions[j].ticker];
        }
        if (c < minCorr) {
          minCorr = c;
          minPair = [positions[i].ticker, positions[j].ticker];
        }
      }
    }

    const avgCorr = count > 0 ? sum / count : 0;
    // Diversification: 0 avg = 100 score, 1 avg = 0 score
    const diversificationScore = Math.max(0, Math.round((1 - avgCorr) * 100));

    return { avgCorr, maxCorr, maxPair, minCorr, minPair, diversificationScore };
  }, [matrix, positions]);

  /* Loading / empty */
  if (isLoading) {
    return (
      <div className="flex items-center py-32">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  if (!positions.length) {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Correlation Heatmap
          </h1>
        </div>
        <div className="glass-surface rounded-2xl py-12 text-center">
          <Grid3X3 className="mx-auto h-10 w-10 text-zinc-700" />
          <p className="mt-3 text-[13px] text-zinc-600">
            Add positions to your portfolio to see correlation analysis.
          </p>
        </div>
      </div>
    );
  }

  const n = positions.length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Correlation Heatmap
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Sector-based correlation estimates for your top {n} positions
        </p>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Average Correlation */}
          <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
            <div className="flex items-center gap-2 text-zinc-600">
              <Grid3X3 className="h-4 w-4" />
              <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">
                Avg Correlation
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold font-mono text-white">
              {summary.avgCorr.toFixed(3)}
            </p>
            <p className="mt-1 text-[13px] text-zinc-600">
              {summary.avgCorr < 0.4
                ? "Well diversified"
                : summary.avgCorr < 0.6
                  ? "Moderately correlated"
                  : "Highly correlated"}
            </p>
          </div>

          {/* Diversification Score */}
          <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
            <div className="flex items-center gap-2 text-zinc-600">
              <TrendingUp className="h-4 w-4" />
              <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">
                Diversification
              </span>
            </div>
            <p
              className="mt-2 text-2xl font-bold font-mono"
              style={{
                color:
                  summary.diversificationScore >= 70
                    ? "#22c55e"
                    : summary.diversificationScore >= 40
                      ? "#eab308"
                      : "#ef4444",
              }}
            >
              {summary.diversificationScore}/100
            </p>
            <p className="mt-1 text-[13px] text-zinc-600">
              {summary.diversificationScore >= 70
                ? "Strong diversification"
                : summary.diversificationScore >= 40
                  ? "Could improve"
                  : "Needs attention"}
            </p>
          </div>

          {/* Most Correlated */}
          <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
            <div className="flex items-center gap-2 text-zinc-600">
              <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">
                Most Correlated
              </span>
            </div>
            <p className="mt-2 text-lg font-bold text-white">
              {summary.maxPair[0]} / {summary.maxPair[1]}
            </p>
            <p className="mt-1 text-sm font-mono" style={{ color: correlationColor(summary.maxCorr) }}>
              {summary.maxCorr.toFixed(3)}
            </p>
          </div>

          {/* Least Correlated */}
          <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
            <div className="flex items-center gap-2 text-zinc-600">
              <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">
                Least Correlated
              </span>
            </div>
            <p className="mt-2 text-lg font-bold text-white">
              {summary.minPair[0]} / {summary.minPair[1]}
            </p>
            <p className="mt-1 text-sm font-mono" style={{ color: correlationColor(summary.minCorr) }}>
              {summary.minCorr.toFixed(3)}
            </p>
          </div>
        </div>
      )}

      {/* Heatmap */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Correlation Matrix
        </h2>

        <div className="overflow-x-auto flex justify-center">
          <div
            className="inline-grid gap-[2px]"
            style={{
              gridTemplateColumns: `80px repeat(${n}, minmax(56px, 1fr))`,
              gridTemplateRows: `32px repeat(${n}, minmax(56px, 1fr))`,
            }}
          >
            {/* Top-left empty cell */}
            <div />

            {/* Column headers */}
            {positions.map((p) => (
              <div
                key={`col-${p.ticker}`}
                className="flex items-end justify-center pb-1 text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]"
              >
                {p.ticker}
              </div>
            ))}

            {/* Rows */}
            {positions.map((rowPos, i) => (
              <>
                {/* Row header */}
                <div
                  key={`row-${rowPos.ticker}`}
                  className="flex items-center pr-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]"
                >
                  {rowPos.ticker}
                </div>

                {/* Cells */}
                {positions.map((colPos, j) => {
                  const value = matrix[i][j];
                  const isHovered =
                    hoveredCell?.row === i && hoveredCell?.col === j;
                  const isDiagonal = i === j;

                  return (
                    <div
                      key={`${i}-${j}`}
                      className="relative flex cursor-default items-center justify-center rounded-md spring-transition transition-all duration-300"
                      style={{
                        backgroundColor: isDiagonal
                          ? "rgba(255,255,255,0.05)"
                          : correlationBg(value),
                        border: isHovered
                          ? "1px solid rgba(255,255,255,0.3)"
                          : "1px solid transparent",
                      }}
                      onMouseEnter={() => setHoveredCell({ row: i, col: j })}
                      onMouseLeave={() => setHoveredCell(null)}
                    >
                      {/* Color bar */}
                      <div
                        className="absolute inset-0 rounded-md opacity-30"
                        style={{ backgroundColor: correlationColor(value) }}
                      />

                      {/* Value */}
                      <span
                        className="relative z-10 font-mono font-medium"
                        style={{
                          color: isHovered ? "#fff" : "rgba(255,255,255,0.7)",
                          fontSize: isHovered ? "13px" : "11px",
                        }}
                      >
                        {isDiagonal ? "1.00" : value.toFixed(2)}
                      </span>

                      {/* Hover tooltip */}
                      {isHovered && !isDiagonal && (
                        <div
                          style={{
                            background: "#18181b",
                            border: "1px solid rgba(255,255,255,0.06)",
                            borderRadius: 12,
                            fontSize: 12,
                            color: "#fafafa",
                          }}
                          className="absolute -top-16 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap px-3 py-2 shadow-lg"
                        >
                          <p className="font-semibold text-white">
                            {rowPos.ticker} / {colPos.ticker}
                          </p>
                          <p className="text-zinc-400">
                            Correlation:{" "}
                            <span
                              className="font-mono font-bold"
                              style={{ color: correlationColor(value) }}
                            >
                              {value.toFixed(3)}
                            </span>
                          </p>
                          <p className="text-zinc-600">
                            {rowPos.sector === colPos.sector
                              ? "Same sector"
                              : (RELATED_SECTORS[rowPos.sector] ?? []).includes(
                                    colPos.sector,
                                  )
                                ? "Related sectors"
                                : "Different sectors"}
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="mt-6 flex items-center gap-6">
          <span className="text-[13px] text-zinc-600">Low</span>
          <div className="flex h-3 flex-1 max-w-xs overflow-hidden rounded-full">
            <div className="flex-1" style={{ background: "rgb(40,180,80)" }} />
            <div className="flex-1" style={{ background: "rgb(120,180,55)" }} />
            <div className="flex-1" style={{ background: "rgb(200,180,50)" }} />
            <div className="flex-1" style={{ background: "rgb(220,120,50)" }} />
            <div className="flex-1" style={{ background: "rgb(240,60,40)" }} />
          </div>
          <span className="text-[13px] text-zinc-600">High</span>
        </div>
      </div>

      {/* Sector breakdown */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Sector Breakdown
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(
            positions.reduce<Record<string, string[]>>((acc, p) => {
              const s = p.sector || "Unknown";
              (acc[s] ??= []).push(p.ticker);
              return acc;
            }, {}),
          ).map(([sector, tickers]) => (
            <div
              key={sector}
              className="bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
            >
              <p className="text-sm font-medium text-zinc-300">{sector}</p>
              <p className="mt-1 text-[13px] text-zinc-600">
                {tickers.join(", ")}
              </p>
              {tickers.length > 1 && (
                <p className="mt-1">
                  <span className="rounded-md px-2.5 py-1 text-[9px] font-bold bg-amber-500/15 text-amber-400">
                    {tickers.length} positions -- higher intra-sector correlation
                  </span>
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
