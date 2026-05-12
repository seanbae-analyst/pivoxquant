"use client";

/**
 * What-If Simulator — Growth Chart
 *
 * Recharts-based area + line overlay.
 * - Main line: portfolio value over time
 * - Dotted line: cumulative invested principal (for DCA scenarios)
 * - Buy-point markers on DCA mode
 *
 * Mobile-first: 240px height on small screens, 360px on desktop.
 */

import { useMemo } from "react";
import { useT } from "@/lib/locale";
import {
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  ReferenceDot,
} from "recharts";
import type { WhatIfChartPoint } from "@/lib/types";

interface WhatIfChartProps {
  data: WhatIfChartPoint[];
  currency?: "USD" | "KRW";
  showInvestedLine?: boolean;
}

/* ── Formatters (scoped to avoid locale-dep) ── */

function fmtShort(v: number, currency: "USD" | "KRW"): string {
  const symbol = currency === "KRW" ? "₩" : "$";
  const abs = Math.abs(v);
  if (currency === "KRW") {
    if (abs >= 100_000_000) return `${symbol}${(v / 100_000_000).toFixed(1)}억`;
    if (abs >= 10_000) return `${symbol}${(v / 10_000).toFixed(0)}만`;
    return `${symbol}${Math.round(v).toLocaleString()}`;
  }
  if (abs >= 1_000_000) return `${symbol}${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${symbol}${(v / 1_000).toFixed(0)}k`;
  return `${symbol}${v.toFixed(0)}`;
}

function fmtFull(v: number, currency: "USD" | "KRW"): string {
  const symbol = currency === "KRW" ? "₩" : "$";
  if (currency === "KRW") {
    return `${symbol}${Math.round(v).toLocaleString("ko-KR")}`;
  }
  return `${symbol}${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

/* ── Tooltip ── */

interface TooltipPayloadItem {
  value: number;
  dataKey: string;
  payload: WhatIfChartPoint;
  color?: string;
}

function ChartTooltip({
  active,
  payload,
  currency = "USD",
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  currency?: "USD" | "KRW";
}) {
  const t = useT();
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;

  const valueItem = payload.find((p) => p.dataKey === "value");
  const investedItem = payload.find((p) => p.dataKey === "invested");

  // v3 Vantablack tooltip: ink card on ivory hairline. No white shadow — uses
  // a subtle inset border instead so the tooltip reads as part of the dark
  // chart surface, not a Nexora-era light callout.
  return (
    <div
      className="rounded-sm border px-3 py-2"
      style={{
        borderColor: "var(--pq-ivory-line)",
        backgroundColor: "rgba(5, 5, 5, 0.92)",
        backdropFilter: "blur(6px)",
      }}
    >
      <p
        className="text-[11px]"
        style={{ color: "rgba(245, 240, 232, 0.55)" }}
      >
        {new Date(point.date).toLocaleDateString(
          currency === "KRW" ? "ko-KR" : "en-US",
          { year: "numeric", month: "short", day: "numeric" },
        )}
      </p>
      {valueItem ? (
        <p
          className="font-mono text-sm font-bold tabular-nums"
          style={{ color: "var(--pq-ivory)" }}
        >
          {fmtFull(valueItem.value, currency)}
        </p>
      ) : null}
      {investedItem && investedItem.value !== valueItem?.value ? (
        <p
          className="font-mono text-[11px] tabular-nums"
          style={{ color: "rgba(245, 240, 232, 0.55)" }}
        >
          {t("whatIf.result.invested")}: {fmtFull(investedItem.value, currency)}
        </p>
      ) : null}
    </div>
  );
}

/* ── Component ── */

export function WhatIfChart({
  data,
  currency = "USD",
  showInvestedLine = false,
}: WhatIfChartProps) {
  const prepared = useMemo(() => {
    if (!data?.length) return [];
    return data
      .filter((d) => d?.value != null && isFinite(d.value))
      .map((d) => ({
        ...d,
        label: new Date(d.date).toLocaleDateString("en-US", {
          month: "short",
          year: "2-digit",
        }),
      }));
  }, [data]);

  const yDomain = useMemo<[number, number]>(() => {
    if (!prepared.length) return [0, 100];
    const values = prepared.flatMap((d) => [d.value, d.invested ?? d.value]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.08 || 100;
    return [Math.max(0, Math.floor(min - pad)), Math.ceil(max + pad)];
  }, [prepared]);

  const buyPoints = useMemo(
    () => prepared.filter((d) => d.buy_point),
    [prepared],
  );

  if (!prepared.length) {
    // v3 ink empty state — hairline border, ghost surface, muted ivory text.
    return (
      <div
        className="flex h-60 w-full items-center justify-center rounded-sm border text-sm"
        style={{
          borderColor: "var(--pq-ivory-line)",
          backgroundColor: "rgba(255, 255, 255, 0.015)",
          color: "rgba(245, 240, 232, 0.55)",
        }}
      >
        No chart data
      </div>
    );
  }

  const ChartEl = showInvestedLine ? ComposedChart : AreaChart;
  const isSparse = buyPoints.length > 0 && buyPoints.length < 40;

  const firstPt = prepared[0];
  const lastPt = prepared[prepared.length - 1];
  const netDelta = lastPt.value - firstPt.value;
  const netPct =
    firstPt.value > 0 ? (netDelta / firstPt.value) * 100 : 0;
  const directionLabel = netDelta >= 0 ? "상승 ▲ up" : "하락 ▼ down";
  const ariaLabel = `What-if simulator growth chart, ${prepared.length} data points from ${firstPt.label} to ${lastPt.label}, ${fmtFull(firstPt.value, currency)} to ${fmtFull(lastPt.value, currency)} (${netPct >= 0 ? "+" : ""}${netPct.toFixed(1)}% ${directionLabel})${showInvestedLine ? `, with cumulative invested principal overlay${buyPoints.length > 0 ? ` and ${buyPoints.length} entry markers` : ""}` : ""}.`;

  return (
    <div
      className="w-full overflow-hidden"
      role="img"
      aria-label={ariaLabel}
    >
      <span className="sr-only">
        Simulated portfolio value from {firstPt.label} (
        {fmtFull(firstPt.value, currency)}) to {lastPt.label} (
        {fmtFull(lastPt.value, currency)}). Net {netPct >= 0 ? "+" : ""}
        {netPct.toFixed(1)} percent ({directionLabel}).
      </span>
      <ResponsiveContainer width="100%" height={320} maxHeight={400}>
        <ChartEl
          data={prepared}
          margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="whatIfFill" x1="0" y1="0" x2="0" y2="1">
              {/* v3: bronze area gradient over Vantablack ink. */}
              <stop offset="0%" stopColor="#B8956A" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#B8956A" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(245, 240, 232, 0.06)"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            axisLine={false}
            tickLine={false}
            tick={{ fill: "rgba(245, 240, 232, 0.45)", fontSize: "var(--pq-text-eyebrow)" }}
            interval="preserveStartEnd"
            minTickGap={40}
          />
          <YAxis
            domain={yDomain}
            axisLine={false}
            tickLine={false}
            tick={{ fill: "rgba(245, 240, 232, 0.45)", fontSize: "var(--pq-text-eyebrow)" }}
            tickFormatter={(v: number) => fmtShort(v, currency)}
            width={64}
          />
          <Tooltip content={<ChartTooltip currency={currency} />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#B8956A"
            strokeWidth={2.5}
            fill="url(#whatIfFill)"
            animationDuration={900}
            animationEasing="ease-out"
            dot={false}
            activeDot={{ r: 4, fill: "#B8956A" }}
          />
          {showInvestedLine ? (
            <Line
              type="stepAfter"
              dataKey="invested"
              stroke="rgba(245, 240, 232, 0.45)"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              animationDuration={900}
            />
          ) : null}
          {showInvestedLine && isSparse
            ? buyPoints.map((pt) => (
                <ReferenceDot
                  key={pt.date}
                  x={pt.label}
                  y={pt.value}
                  r={3}
                  fill="#B8956A"
                  stroke="#050505"
                  strokeWidth={1.5}
                />
              ))
            : null}
        </ChartEl>
      </ResponsiveContainer>
    </div>
  );
}
