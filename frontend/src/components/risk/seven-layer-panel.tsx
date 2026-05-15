"use client";

/**
 * Seven-Layer Risk Defense Panel — editorial ladder.
 * Each layer renders as a hairline-separated row with a status dot,
 * serif italic name, metric (tabular-nums), and a neutral 1-line observation.
 *
 * Neutral observation language only. Uses POSITIVE / NEUTRAL / NEGATIVE
 * signal semantics under the hood.
 */

import { cn } from "@/lib/utils";

export type LayerStatus = "green" | "yellow" | "red";

export interface RiskLayer {
  no: number;
  name: string;            // serif italic
  metricLabel: string;     // short label before value
  metricValue: string;     // formatted value, tabular-nums
  status: LayerStatus;
  observation: string;     // neutral one-liner
}

/** Seven canonical layers with mock values (pre-wire; backend hook later). */
export const SEVEN_LAYER_MOCK: RiskLayer[] = [
  {
    no: 1,
    name: "VaR Layer",
    metricLabel: "Daily 1-day 95% VaR",
    metricValue: "-2.14%",
    status: "green",
    observation: "Within historical band.",
  },
  {
    no: 2,
    name: "Correlation Layer",
    metricLabel: "Avg pairwise correlation",
    metricValue: "0.62",
    status: "yellow",
    observation: "Elevated — diversification benefit reduced.",
  },
  {
    no: 3,
    name: "VIX Regime",
    metricLabel: "VIX",
    metricValue: "15.8",
    status: "green",
    observation: "Low-volatility regime noted.",
  },
  {
    no: 4,
    name: "Tail Risk",
    metricLabel: "Tail ratio",
    metricValue: "1.18",
    status: "green",
    observation: "Balanced right/left tail.",
  },
  {
    no: 5,
    name: "Daily Loss Guard",
    metricLabel: "Today's P&L",
    metricValue: "-0.4%",
    status: "green",
    observation: "Well within the -3% threshold.",
  },
  {
    no: 6,
    name: "Sector Exposure",
    metricLabel: "Max sector weight",
    metricValue: "34% Tech",
    status: "yellow",
    observation: "Above the 30% soft-limit band.",
  },
  {
    no: 7,
    name: "Cash Buffer",
    metricLabel: "Cash weight",
    metricValue: "12%",
    status: "green",
    observation: "Above the 8% floor.",
  },
];

function StatusDot({ status }: { status: LayerStatus }) {
  const cls =
    status === "green"
      ? "bg-[var(--pq-bronze-light,#A3845C)]"
      : status === "yellow"
        ? "bg-[var(--pq-bronze,#B8956A)]"
        : "bg-[#B04A3A]"; // faint-red editorial accent
  return (
    <span
      aria-label={`status ${status}`}
      className={cn("inline-block h-2 w-2 rounded-full shrink-0", cls)}
    />
  );
}

function StatusLabel({ status }: { status: LayerStatus }) {
  const label =
    status === "green" ? "OK" : status === "yellow" ? "NOTED" : "ELEVATED";
  const cls =
    status === "green"
      ? "signal-positive"
      : status === "yellow"
        ? "signal-neutral"
        : "signal-negative";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-pq-eyebrow font-semibold tracking-wide",
        cls,
      )}
    >
      {label}
    </span>
  );
}

export function SevenLayerPanel({
  layers = SEVEN_LAYER_MOCK,
}: {
  layers?: RiskLayer[];
}) {
  return (
    <section aria-labelledby="seven-layer-heading">
      <header className="mb-3 border-t border-slate-200 pt-4">
        <h2
          id="seven-layer-heading"
          className="font-serif text-xl text-slate-900"
        >
          Seven-Layer Risk Defense
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Observation ladder — informational signal only.
        </p>
      </header>

      <ol className="divide-y divide-slate-100">
        {layers.map((layer) => (
          <li
            key={layer.no}
            className="grid grid-cols-[auto_1fr_auto] items-start gap-x-4 gap-y-1 py-4 sm:grid-cols-[auto_1fr_auto_auto]"
            style={{ tableLayout: "fixed" } as React.CSSProperties}
          >
            {/* layer number */}
            <span className="font-serif text-sm text-slate-400 tabular-nums w-8">
              {String(layer.no).padStart(2, "0")}
            </span>

            {/* name + observation */}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <StatusDot status={layer.status} />
                <h3 className="font-serif font-bold text-pq-lead text-slate-900">
                  {layer.name}
                </h3>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                {layer.observation}
              </p>
            </div>

            {/* metric */}
            <div className="text-right shrink-0">
              <p className="text-pq-eyebrow uppercase tracking-wider text-slate-400">
                {layer.metricLabel}
              </p>
              <p className="mt-0.5 text-sm font-semibold tabular-nums text-slate-900">
                {layer.metricValue}
              </p>
            </div>

            {/* status badge (desktop only) */}
            <div className="hidden sm:flex items-start pt-0.5">
              <StatusLabel status={layer.status} />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
