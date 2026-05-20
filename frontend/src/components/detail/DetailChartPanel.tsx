"use client";

/**
 * Zone1 TERMINAL — Price chart. The centre of gravity: tall (380px) and
 * connected to the hero on the same dark surface. Period tabs (1M~2Y),
 * signal observation markers + a legend keyed to KR convention colours
 * (carmine 긍정 ▲ / indigo 부정 ▼ / dim 중립 ·).
 *
 * P0 resilience: owns its own loading / failure boundary. A chart fetch
 * failure renders a retry, never an infinite skeleton.
 */

import { InteractiveLineChart, type ChartMarker } from "@/components/charts/interactive-line-chart";
import { cn } from "@/lib/utils";
import { fmtKrw, fmtUsd } from "@/lib/format";
import { EmptyNote, LoadFailure } from "./shared";
import {
  PERIODS,
  type Period,
  type ChartPoint,
} from "./types";

function ChartCanvas({
  data,
  currency,
  markers,
}: {
  data: ChartPoint[];
  currency: "USD" | "KRW";
  markers?: ChartMarker[];
}) {
  if (!data || data.length < 2) {
    return (
      <div className="h-[360px] flex items-center justify-center">
        <EmptyNote>Chart data unavailable for this window.</EmptyNote>
      </div>
    );
  }
  const series = data.map((d) => ({ date: d.date, value: d.close }));
  const priceFmt = currency === "KRW" ? fmtKrw : fmtUsd;
  return (
    <InteractiveLineChart
      points={series}
      height={380}
      markers={markers}
      valueFormatter={(v) => priceFmt(v)}
      dateFormatter={(d) => {
        const parsed = new Date(d);
        return isNaN(parsed.getTime())
          ? d
          : parsed.toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            });
      }}
      yLabel="Last observed"
      ariaLabel="Price observation chart"
    />
  );
}

export interface DetailChartPanelProps {
  period: Period;
  onPeriodChange: (p: Period) => void;
  data: ChartPoint[];
  currency: "USD" | "KRW";
  markers: ChartMarker[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  retrying: boolean;
}

export function DetailChartPanel({
  period,
  onPeriodChange,
  data,
  currency,
  markers,
  loading,
  error,
  onRetry,
  retrying,
}: DetailChartPanelProps) {
  return (
    <section>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <span className="font-mono text-pq-eyebrow-sm uppercase tracking-[0.12em] text-[var(--pq-bronze)]">
          Price history · observation
        </span>
        <div role="tablist" aria-label="Chart period" className="flex gap-1 items-center">
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              role="tab"
              aria-selected={period === p}
              onClick={() => onPeriodChange(p)}
              className={cn(
                "px-3 py-1 text-pq-eyebrow-sm tracking-[0.12em] uppercase transition-all",
                period === p
                  ? "text-[var(--pq-ivory)] border-b border-[var(--pq-bronze)]"
                  : "text-[var(--pq-ivory-faint)] hover:text-[var(--pq-bronze)]",
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 md:p-6 rounded-sm">
        {error ? (
          <LoadFailure
            label="차트 데이터를 불러오지 못했습니다."
            onRetry={onRetry}
            retrying={retrying}
          />
        ) : loading ? (
          <div className="h-[360px] pq-skeleton-dark rounded-sm" />
        ) : (
          <ChartCanvas data={data} currency={currency} markers={markers} />
        )}
      </div>

      {/* Marker legend — only when this ticker has observation history
          within the visible window. KR convention colours via tokens. */}
      {!loading && !error && markers.length > 0 && (
        <div className="mt-3 flex items-center gap-4 flex-wrap font-mono text-pq-eyebrow-sm uppercase tracking-[0.12em] text-[var(--pq-ivory-faint)]">
          <span>관측 기록 {markers.length}건</span>
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              style={{ width: 7, height: 7, borderRadius: 999, background: "var(--up)" }}
            />
            긍정 ▲
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              style={{ width: 7, height: 7, borderRadius: 999, background: "var(--down)" }}
            />
            부정 ▼
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              style={{
                width: 7,
                height: 7,
                borderRadius: 999,
                background: "rgba(245,240,232,0.5)",
              }}
            />
            중립 ·
          </span>
        </div>
      )}
    </section>
  );
}
