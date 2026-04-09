"use client";

import { useMemo } from "react";
import { usePortfolio } from "@/lib/hooks";
import { fmtUsd, fmtKrw } from "@/lib/format";
import { DollarSign, Calendar, TrendingUp, Wallet } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import type { Position } from "@/lib/types";

/* ── Sector yield estimates (%) ── */

const US_SECTOR_YIELDS: Record<string, number> = {
  Technology: 0.5,
  "Financial Services": 2.5,
  Healthcare: 1.5,
  Energy: 3.5,
  "Consumer Cyclical": 1.0,
  "Consumer Defensive": 2.2,
  Industrials: 1.8,
  Utilities: 3.0,
  "Real Estate": 3.5,
  "Communication Services": 1.0,
  "Basic Materials": 2.0,
};

const KR_TICKER_YIELDS: Record<string, number> = {
  "005930.KS": 2.0, // Samsung
  "000660.KS": 1.0, // SK Hynix
  "035420.KS": 0.3, // NAVER
  "035720.KS": 0.3, // Kakao
  "051910.KS": 1.5, // LG Chem
  "006400.KS": 1.2, // Samsung SDI
  "068270.KS": 0.5, // Celltrion
  "105560.KS": 2.5, // KB Financial
  "055550.KS": 3.0, // Shinhan
  "096770.KS": 4.0, // SK Innovation
};

const DEFAULT_KR_YIELD = 1.5;
const DEFAULT_US_YIELD = 1.5;

function estimateYield(pos: Position): number {
  if (pos.is_korean) {
    return KR_TICKER_YIELDS[pos.ticker] ?? DEFAULT_KR_YIELD;
  }
  return US_SECTOR_YIELDS[pos.sector] ?? DEFAULT_US_YIELD;
}

/* ── Derived dividend data ── */

interface DividendRow {
  ticker: string;
  name: string;
  shares: number;
  marketValue: number;
  currency: "USD" | "KRW";
  estYield: number;
  annualDividend: number;
  annualDividendUsd: number;
}

function buildRows(
  positions: Position[],
  fxRate: number,
): DividendRow[] {
  return positions
    .map((p) => {
      const yld = estimateYield(p);
      const annual = p.market_value * (yld / 100);
      const annualUsd = p.is_korean ? annual / fxRate : annual;
      return {
        ticker: p.ticker,
        name: p.name,
        shares: p.shares,
        marketValue: p.market_value,
        currency: p.currency,
        estYield: yld,
        annualDividend: annual,
        annualDividendUsd: annualUsd,
      };
    })
    .sort((a, b) => b.annualDividendUsd - a.annualDividendUsd);
}

/* ── Monthly projection ── */

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

function buildMonthly(totalAnnualUsd: number) {
  // Simple even distribution with slight quarterly bumps (Q2, Q4)
  const base = totalAnnualUsd / 12;
  return MONTHS.map((month, i) => {
    const qBoost = i % 3 === 2 ? 1.25 : 0.92;
    return { month, dividend: Math.round(base * qBoost * 100) / 100 };
  });
}

/* ── Custom tooltip ── */

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "#18181b",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: 12,
        fontSize: 12,
        color: "#fafafa",
      }}
      className="px-4 py-3 shadow-xl"
    >
      <p className="text-xs text-zinc-400">{label}</p>
      <p className="text-sm font-semibold font-mono text-emerald-400">
        {fmtUsd(payload[0].value)}
      </p>
    </div>
  );
}

/* ── Summary card ── */

function SummaryCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <div className="mb-3 flex items-center gap-2 text-zinc-600">
        <Icon className="h-4 w-4" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">
          {label}
        </span>
      </div>
      <p className="text-2xl font-bold font-mono text-white">{value}</p>
      {sub && <p className="mt-1 text-[13px] text-zinc-400">{sub}</p>}
    </div>
  );
}

/* ── Page ── */

export default function DividendsPage() {
  const { data: portfolio, isLoading } = usePortfolio();

  const positions = portfolio?.positions ?? [];
  const fxRate = portfolio?.fx_rate ?? 1350;

  const rows = useMemo(() => buildRows(positions, fxRate), [positions, fxRate]);

  const totalAnnualUsd = useMemo(
    () => rows.reduce((s, r) => s + r.annualDividendUsd, 0),
    [rows],
  );

  const totalValueUsd = portfolio?.total_value_usd ?? 0;
  const portfolioYield =
    totalValueUsd > 0 ? (totalAnnualUsd / totalValueUsd) * 100 : 0;
  const monthlyIncome = totalAnnualUsd / 12;

  const monthlyData = useMemo(
    () => buildMonthly(totalAnnualUsd),
    [totalAnnualUsd],
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  if (!positions.length) {
    return (
      <div className="glass-surface rounded-2xl py-12 text-center">
        <Wallet className="mx-auto h-10 w-10 text-zinc-600" />
        <p className="mt-3 text-[13px] text-zinc-600">
          No positions found. Add stocks to see dividend estimates.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-4 py-8">
      {/* ── Header ── */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Dividend Tracker
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Estimated dividend income based on sector-average yields
        </p>
      </div>

      {/* ── Summary Cards ── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          icon={DollarSign}
          label="Annual Dividends (USD)"
          value={fmtUsd(totalAnnualUsd)}
          sub={fmtKrw(totalAnnualUsd * fxRate)}
        />
        <SummaryCard
          icon={TrendingUp}
          label="Portfolio Yield"
          value={`${portfolioYield.toFixed(2)}%`}
          sub="Weighted average"
        />
        <SummaryCard
          icon={Calendar}
          label="Monthly Income"
          value={fmtUsd(monthlyIncome)}
          sub={fmtKrw(monthlyIncome * fxRate)}
        />
        <SummaryCard
          icon={Wallet}
          label="Positions Paying"
          value={`${rows.length}`}
          sub="Estimated dividend payers"
        />
      </div>

      {/* ── Monthly Projection Chart ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Monthly Dividend Projection
        </h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthlyData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.06)"
                vertical={false}
              />
              <XAxis
                dataKey="month"
                tick={{ fill: "#71717a", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `$${v}`}
              />
              <Tooltip content={<ChartTooltip />} />
              <Bar
                dataKey="dividend"
                fill="#34d399"
                radius={[6, 6, 0, 0]}
                maxBarSize={40}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Position Dividend Table ── */}
      <div className="glass-surface rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-white/[0.06]">
          <h2 className="text-lg font-semibold text-white">
            Dividend by Position
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] text-left">
                <th className="px-6 py-3 text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Ticker</th>
                <th className="px-6 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Shares</th>
                <th className="px-6 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Market Value</th>
                <th className="px-6 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Est. Yield</th>
                <th className="px-6 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Annual Dividend</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.ticker}
                  className="border-b border-white/[0.06] last:border-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3">
                    <div>
                      <span className="font-medium text-white">
                        {row.ticker}
                      </span>
                      <p className="text-[13px] text-zinc-600 truncate max-w-[180px]">
                        {row.name}
                      </p>
                    </div>
                  </td>
                  <td className="px-6 py-3 text-right font-mono text-zinc-300">
                    {row.shares}
                  </td>
                  <td className="px-6 py-3 text-right font-mono text-zinc-300">
                    {row.currency === "KRW"
                      ? fmtKrw(row.marketValue)
                      : fmtUsd(row.marketValue)}
                  </td>
                  <td className="px-6 py-3 text-right font-mono text-cyan-400">
                    {row.estYield.toFixed(1)}%
                  </td>
                  <td className="px-6 py-3 text-right font-mono font-medium text-emerald-400">
                    {row.currency === "KRW"
                      ? fmtKrw(row.annualDividend)
                      : fmtUsd(row.annualDividend)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Disclaimer ── */}
      <p className="text-center text-[13px] text-zinc-600">
        Dividend estimates are based on sector-average yields and may differ from
        actual payouts. Past dividends do not guarantee future distributions.
      </p>
    </div>
  );
}
