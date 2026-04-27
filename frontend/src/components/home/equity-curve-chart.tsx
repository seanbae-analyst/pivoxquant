"use client";

/**
 * <EquityCurveChart /> — 90d portfolio NAV time-series on /home.
 *
 * Backend: GET /api/portfolio/history?period=3mo → { data: [{date, value}] }
 * (3mo ≈ 90 trading days). No mock fallback: empty / loading / error each
 * render their own state with explicit copy.
 *
 * Library: recharts 3.x (already installed). SVG-only render keeps the
 * Apple HIG / Bloomberg ink tone intact.
 *
 * Legal: this is a value time-series — no signal labels, no advice copy.
 */

import { useMemo } from "react";
import useSWR from "swr";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { pctColor } from "@/lib/format";

interface EquityPoint {
  date: string;   // YYYY-MM-DD
  value: number;
}
interface EquityHistoryResponse {
  data?: EquityPoint[];
}

interface ChartRow extends EquityPoint {
  ts: number;        // ms epoch (for x-axis ordering)
  changePct: number; // vs first point in window
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

interface EquityCurveChartProps {
  /** Display currency for axis labels and tooltip. */
  currency?: "USD" | "KRW";
  /** Pixel height of the chart. */
  height?: number;
}

function fmtAxisMoney(n: number, currency: "USD" | "KRW"): string {
  if (!Number.isFinite(n)) return "—";
  if (currency === "KRW") {
    if (Math.abs(n) >= 1e8) return `₩${(n / 1e8).toFixed(1)}억`;
    if (Math.abs(n) >= 1e4) return `₩${(n / 1e4).toFixed(0)}만`;
    return `₩${Math.round(n).toLocaleString("ko-KR")}`;
  }
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtTooltipMoney(n: number, currency: "USD" | "KRW"): string {
  if (!Number.isFinite(n)) return "—";
  const dec = currency === "KRW" ? 0 : 2;
  const body = n.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${currency === "KRW" ? "₩" : "$"}${body}`;
}

function fmtAxisDate(ts: number): string {
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

interface RechartsTooltipPayloadEntry {
  payload?: ChartRow;
}
interface CustomTooltipProps {
  active?: boolean;
  payload?: RechartsTooltipPayloadEntry[];
  currency: "USD" | "KRW";
}

function ChartTooltip({ active, payload, currency }: CustomTooltipProps) {
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
        lineHeight: 1.5,
        color: "var(--pq-ivory)",
        fontFamily:
          "var(--font-mono), 'JetBrains Mono', ui-monospace, monospace",
      }}
    >
      <div
        style={{
          color: "var(--pq-bronze)",
          letterSpacing: "0.08em",
          marginBottom: 4,
        }}
      >
        {row.date}
      </div>
      <div>{fmtTooltipMoney(row.value, currency)}</div>
      <div style={{ color: pctColor(row.changePct) }}>
        {row.changePct >= 0 ? "+" : ""}
        {row.changePct.toFixed(2)}% vs window start
      </div>
    </div>
  );
}

export function EquityCurveChart({
  currency = "USD",
  height = 240,
}: EquityCurveChartProps) {
  const { data, error, isLoading } = useSWR<EquityHistoryResponse>(
    API.portfolio.history("3mo"),
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      errorRetryCount: 2,
      errorRetryInterval: 10_000,
    },
  );

  const rows: ChartRow[] = useMemo(() => {
    const raw = data?.data ?? [];
    if (raw.length === 0) return [];
    const base = raw[0]?.value || 1;
    return raw.map((p) => ({
      date: p.date,
      value: p.value,
      ts: new Date(p.date).getTime(),
      changePct: base > 0 ? ((p.value - base) / base) * 100 : 0,
    }));
  }, [data]);

  const yDomain = useMemo<[number, number] | undefined>(() => {
    if (rows.length === 0) return undefined;
    const vs = rows.map((r) => r.value);
    const min = Math.min(...vs);
    const max = Math.max(...vs);
    const pad = (max - min) * 0.08 || max * 0.02 || 1;
    return [min - pad, max + pad];
  }, [rows]);

  const totalChangePct = rows.length >= 2 ? rows[rows.length - 1].changePct : 0;
  const lineColor = totalChangePct >= 0 ? "#B8956A" : "#A3845C";

  /* ── Empty / loading / error states ── */

  const Frame = ({
    children,
    label,
  }: {
    children: React.ReactNode;
    label?: string;
  }) => (
    <div
      style={{
        background: "var(--pq-card-bg-ink)",
        border: "1px solid var(--pq-hairline-ink)",
        height,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        textAlign: "center",
        color: "rgba(245, 240, 232, 0.55)",
        fontSize: 12,
        lineHeight: 1.6,
      }}
    >
      <div style={{ maxWidth: 320 }}>
        {label && (
          <div
            className="font-mono uppercase"
            style={{
              fontSize: 9,
              letterSpacing: "0.24em",
              color: "rgba(245, 240, 232, 0.4)",
              marginBottom: 6,
            }}
          >
            {label}
          </div>
        )}
        {children}
      </div>
    </div>
  );

  if (isLoading) {
    return <Frame label="Loading">90-day equity curve resolving…</Frame>;
  }
  if (error) {
    return (
      <Frame label="Unavailable">
        Equity history failed to load. The page will retry automatically.
      </Frame>
    );
  }
  if (rows.length === 0) {
    return (
      <Frame label="No data">
        No portfolio history yet. Add a position to see your 90-day equity
        curve.
      </Frame>
    );
  }

  /* ── Chart ── */

  return (
    <div
      style={{
        background: "var(--pq-card-bg-ink)",
        border: "1px solid var(--pq-hairline-ink)",
        padding: "8px 4px 4px 4px",
      }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart
          data={rows}
          margin={{ top: 8, right: 16, bottom: 4, left: 8 }}
        >
          <defs>
            <linearGradient id="pq-equity-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity={0.18} />
              <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="rgba(245, 240, 232, 0.06)"
            strokeDasharray="2 4"
            vertical={false}
          />
          <XAxis
            dataKey="ts"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tickFormatter={fmtAxisDate}
            stroke="rgba(245, 240, 232, 0.18)"
            tick={{
              fontSize: 10,
              fill: "rgba(245, 240, 232, 0.55)",
              fontFamily:
                "var(--font-mono), 'JetBrains Mono', ui-monospace, monospace",
            }}
            tickLine={false}
            axisLine={{ stroke: "rgba(245, 240, 232, 0.10)" }}
            minTickGap={32}
          />
          <YAxis
            domain={yDomain}
            tickFormatter={(v: number) => fmtAxisMoney(v, currency)}
            stroke="rgba(245, 240, 232, 0.18)"
            tick={{
              fontSize: 10,
              fill: "rgba(245, 240, 232, 0.55)",
              fontFamily:
                "var(--font-mono), 'JetBrains Mono', ui-monospace, monospace",
            }}
            tickLine={false}
            axisLine={false}
            width={64}
          />
          <Tooltip
            content={(props: unknown) => {
              const p = props as {
                active?: boolean;
                payload?: RechartsTooltipPayloadEntry[];
              };
              return (
                <ChartTooltip
                  active={p.active}
                  payload={p.payload}
                  currency={currency}
                />
              );
            }}
            cursor={{
              stroke: "rgba(184, 149, 106, 0.45)",
              strokeDasharray: "2 4",
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={lineColor}
            strokeWidth={1.5}
            fill="url(#pq-equity-fill)"
            dot={false}
            activeDot={{
              r: 3,
              fill: lineColor,
              stroke: "var(--pq-ivory)",
              strokeWidth: 1,
            }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default EquityCurveChart;
