"use client";

/**
 * CandlestickChart — lightweight-charts v5 wrapper for PivoxQuant Terminal.
 *
 * Renders price + volume + MA overlays for a ticker against the backend
 * /api/chart/{ticker}?period=... endpoint.
 *
 * Data note: the existing backend endpoint returns `{ data: [{ date,
 * close, volume }] }` — no OHLC. We therefore plot close as a line series
 * (MA20 / MA50 overlays on top) and volume as a histogram pane. When the
 * backend gains OHLC we can promote the price series to CandlestickSeries
 * without touching consumers.
 *
 * Props:
 *   - ticker: "NVDA", "005930.KS", etc.
 *   - timeframe: "1D" | "5D" | "1M" | "3M" | "6M" | "1Y" | "2Y"
 *   - indicators: subset of "ma20" | "ma50" | "rsi" | "volume"
 *
 * Visual: dark terminal theme; bronze (#B8956A) for MA20, bronze-deep
 * (#6F5636) dashed for MA50. Green/red volume bars.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import type {
  IChartApi,
  ISeriesApi,
  LineData,
  HistogramData,
  UTCTimestamp,
} from "lightweight-charts";
import { apiFetch } from "@/lib/api";
import { pctColor } from "@/lib/format";

export type Timeframe = "1D" | "5D" | "1M" | "3M" | "6M" | "1Y" | "2Y";
export type Indicator = "ma20" | "ma50" | "rsi" | "volume";

const TIMEFRAME_TO_PERIOD: Record<Timeframe, string> = {
  "1D": "1d",
  "5D": "5d",
  "1M": "1mo",
  "3M": "3mo",
  "6M": "6mo",
  "1Y": "1y",
  "2Y": "2y",
};

interface BackendPoint {
  date: string;
  close: number;
  volume?: number;
}
interface BackendResponse {
  ticker: string;
  period: string;
  data: BackendPoint[];
  source?: string;
  observed_at?: string;
}

export interface CandlestickChartProps {
  ticker: string;
  timeframe?: Timeframe;
  indicators?: Indicator[];
  /** Height of the primary price pane, px. Volume adds 80 more. Default 320. */
  height?: number;
  className?: string;
  /** If true, render the Today % KPI chip above the chart. CEO directive
   *  2026-04-27: with the chart on a `1d` SWR fetch, only the 1-day return
   *  has reliable lookback; 5-Day / 1-Month chips would render "—" most of
   *  the time. Better to surface a single trustworthy chip than three with
   *  two perpetual blanks. Multi-period view lives on /detail/[ticker]. */
  showKpiChips?: boolean;
}

function toTs(s: string): UTCTimestamp {
  const iso = s.length <= 10 ? `${s}T00:00:00Z` : `${s.replace(" ", "T")}:00Z`;
  return Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp;
}

function sma(values: number[], window: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= window) sum -= values[i - window];
    out.push(i >= window - 1 ? sum / window : null);
  }
  return out;
}

export function CandlestickChart({
  ticker,
  timeframe = "1D",
  indicators = ["ma20", "ma50", "volume"],
  height = 320,
  className = "",
  showKpiChips = false,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lineRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ma50Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const wantVolume = indicators.includes("volume");
  const wantMa20 = indicators.includes("ma20");
  const wantMa50 = indicators.includes("ma50");

  // BUG-8 FIX 1: chart data now flows through SWR instead of a raw
  // `fetch()` inside a useEffect. The old code had TWO useEffects — a
  // chart-init effect keyed on [height, wantVolume, wantMa20, wantMa50,
  // timeframe] and a fetch effect keyed on [ticker, timeframe]. Under
  // React StrictMode in dev, and on any timeframe-only change, both
  // effects re-ran and the fetch fired twice for the same URL. With SWR
  // + the global dedupingInterval (6 s), parallel calls to the same
  // `/api/chart/NVDA?period=1d` URL return a single in-flight response.
  const period = TIMEFRAME_TO_PERIOD[timeframe] ?? "6mo";
  const chartKey = `/api/chart/${encodeURIComponent(ticker)}?period=${period}`;
  const {
    data: chartBody,
    error: chartErr,
    isLoading: chartLoading,
  } = useSWR<BackendResponse>(
    chartKey,
    (url) => apiFetch<BackendResponse>(url),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 60_000,
      keepPreviousData: true,
    },
  );

  const loading = chartLoading && !chartBody;
  const err = chartErr ? String((chartErr as Error).message || chartErr) : null;
  const source = chartBody?.source ?? null;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let cancelled = false;
    let chart: IChartApi | null = null;
    let ro: ResizeObserver | null = null;

    (async () => {
      const lc = await import("lightweight-charts");
      if (cancelled || !container) return;

      chart = lc.createChart(container, {
        width: container.clientWidth,
        height: height + (wantVolume ? 80 : 0),
        layout: {
          background: { type: lc.ColorType.Solid, color: "#0B0E14" },
          textColor: "rgba(245,240,232,0.65)",
          fontFamily:
            "var(--font-mono), ui-monospace, Menlo, monospace",
          fontSize: 10,
        },
        grid: {
          vertLines: { color: "rgba(26,31,46,0.55)" },
          horzLines: { color: "rgba(26,31,46,0.55)" },
        },
        rightPriceScale: {
          borderColor: "#1A1F2E",
        },
        timeScale: {
          borderColor: "#1A1F2E",
          timeVisible: timeframe === "1D" || timeframe === "5D",
          secondsVisible: false,
        },
        crosshair: {
          horzLine: {
            color: "#B8956A",
            labelBackgroundColor: "#1A1F2E",
          },
          vertLine: {
            color: "#B8956A",
            labelBackgroundColor: "#1A1F2E",
          },
        },
      });
      chartRef.current = chart;

      const line = chart.addSeries(lc.LineSeries, {
        color: "rgba(245,240,232,0.92)",
        lineWidth: 2,
        priceLineColor: "#B8956A",
        priceLineWidth: 1,
        lastValueVisible: true,
      });
      lineRef.current = line;

      if (wantMa20) {
        ma20Ref.current = chart.addSeries(lc.LineSeries, {
          color: "#B8956A",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "MA20",
        });
      }
      if (wantMa50) {
        ma50Ref.current = chart.addSeries(lc.LineSeries, {
          color: "#6F5636",
          lineWidth: 1,
          lineStyle: lc.LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "MA50",
        });
      }
      if (wantVolume) {
        volRef.current = chart.addSeries(lc.HistogramSeries, {
          priceFormat: { type: "volume" },
          priceScaleId: "volume",
          color: "rgba(125,180,135,0.55)",
        });
        chart.priceScale("volume").applyOptions({
          scaleMargins: { top: 0.78, bottom: 0 },
          borderColor: "#1A1F2E",
        });
      }

      ro = new ResizeObserver(() => {
        if (!chart || !container) return;
        chart.applyOptions({
          width: container.clientWidth,
          height: height + (wantVolume ? 80 : 0),
        });
      });
      ro.observe(container);
      // Signal the data-feed effect that freshly-created series refs are
      // ready to accept data. Without this, changing timeframe recreated
      // the chart but the cached SWR response would not re-populate the
      // new series until the next revalidation tick.
      if (!cancelled) setChartRev((r) => r + 1);
    })().catch(() => {
      // Chart init errors are rare; data errors are surfaced via the
      // SWR chartErr branch below. Silently swallow to avoid clobbering
      // the useful error message.
    });

    return () => {
      cancelled = true;
      ro?.disconnect();
      if (chart) chart.remove();
      chartRef.current = null;
      lineRef.current = null;
      ma20Ref.current = null;
      ma50Ref.current = null;
      volRef.current = null;
    };
  }, [height, wantVolume, wantMa20, wantMa50, timeframe]);

  // Push SWR data into the lightweight-charts series. Runs whenever
  // chartBody updates OR when the series are rebuilt (timeframe/indicator
  // change triggers the init effect above). `chartRev` tracks init-effect
  // completions so we re-feed data into freshly-created series refs.
  const [chartRev, setChartRev] = useState(0);
  useEffect(() => {
    if (!chartBody) return;
    const data = chartBody.data || [];
    if (!lineRef.current) return;

    const priceData: LineData[] = data.map((p) => ({
      time: toTs(p.date),
      value: p.close,
    }));
    lineRef.current.setData(priceData);

    const closes = data.map((p) => p.close);
    if (ma20Ref.current) {
      const ma20 = sma(closes, 20);
      const ma20Data: LineData[] = [];
      ma20.forEach((v, i) => {
        if (v != null) ma20Data.push({ time: toTs(data[i].date), value: v });
      });
      ma20Ref.current.setData(ma20Data);
    }
    if (ma50Ref.current) {
      const ma50 = sma(closes, 50);
      const ma50Data: LineData[] = [];
      ma50.forEach((v, i) => {
        if (v != null) ma50Data.push({ time: toTs(data[i].date), value: v });
      });
      ma50Ref.current.setData(ma50Data);
    }
    if (volRef.current) {
      const volData: HistogramData[] = data.map((p, i) => {
        const prev = i > 0 ? data[i - 1].close : p.close;
        const up = p.close >= prev;
        return {
          time: toTs(p.date),
          value: p.volume ?? 0,
          color: up ? "rgba(125,180,135,0.55)" : "rgba(209,136,136,0.55)",
        };
      });
      volRef.current.setData(volData);
    }
    chartRef.current?.timeScale().fitContent();
  }, [chartBody, chartRev]);

  // KPI chip (single, "Today") — computed client-side from the SWR chart
  // data. With the chart on a `1d` fetch we only have the last vs second-
  // to-last close to compare; multi-day chips would be "—" most of the time
  // (CEO call: avoid blank chips, surface one trustworthy number). Detail
  // page is the place for 5-Day / 1-Month context.
  const kpiChips = useMemo(() => {
    if (!showKpiChips) return null;
    const data = chartBody?.data ?? [];
    if (data.length < 2) return null;
    const last = data[data.length - 1]?.close;
    const prev = data[data.length - 2]?.close;
    if (!Number.isFinite(last) || !Number.isFinite(prev) || prev === 0) {
      return null;
    }
    const todayPct = ((last - prev) / prev) * 100;
    return [{ label: "Today", pct: todayPct }];
  }, [chartBody, showKpiChips]);

  return (
    <div
      className={`pq-terminal-chart ${className}`.trim()}
      style={{
        background: "#0B0E14",
        border: "1px solid #1A1F2E",
        position: "relative",
      }}
    >
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: "1px solid #1A1F2E" }}
      >
        <div className="flex items-center gap-3">
          <span
            className="font-mono"
            style={{
              fontSize: 11.5,
              letterSpacing: "0.12em",
              color: "rgba(245,240,232,0.98)",
              fontWeight: 500,
            }}
          >
            {ticker}
          </span>
          <span
            className="font-mono uppercase"
            style={{
              fontSize: 9.5,
              letterSpacing: "0.22em",
              color: "#B8956A",
              borderLeft: "1px solid #1A1F2E",
              paddingLeft: 12,
            }}
          >
            {timeframe}
          </span>
        </div>
        <div
          className="font-mono uppercase"
          style={{
            fontSize: 9,
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.45)",
          }}
        >
          {loading
            ? "Loading…"
            : err
              ? "Unavailable"
              : source
                ? `src · ${source}`
                : "observed"}
        </div>
      </div>

      {kpiChips && (
        <div
          className="flex gap-2 px-3 py-2"
          style={{
            borderBottom: "1px solid #1A1F2E",
            background: "rgba(184,149,106,0.02)",
          }}
        >
          {kpiChips.map((chip) => (
            <div
              key={chip.label}
              style={{
                padding: "5px 10px",
                border: "1px solid rgba(245,240,232,0.08)",
                borderRadius: 2,
                background: "rgba(10,10,10,0.4)",
                minWidth: 76,
              }}
            >
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: 9,
                  letterSpacing: "0.2em",
                  color: "rgba(245,240,232,0.45)",
                }}
              >
                {chip.label}
              </div>
              <div
                className="font-mono tabular-nums"
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  marginTop: 2,
                  color:
                    chip.pct == null
                      ? "rgba(245,240,232,0.45)"
                      : pctColor(chip.pct),
                }}
              >
                {chip.pct == null
                  ? "—"
                  : `${chip.pct >= 0 ? "+" : ""}${chip.pct.toFixed(2)}%`}
              </div>
            </div>
          ))}
        </div>
      )}

      <div ref={containerRef} style={{ width: "100%" }} />

      {err && !loading && (
        <div
          className="font-serif"
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            color: "rgba(245,240,232,0.45)",
            fontSize: 12,
          }}
        >
          chart data unavailable
        </div>
      )}
    </div>
  );
}

export default CandlestickChart;
