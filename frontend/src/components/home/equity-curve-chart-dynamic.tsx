"use client";

/**
 * equity-curve-chart-dynamic.tsx — next/dynamic wrapper for EquityCurveChart.
 *
 * Purpose: recharts pulls ~391KB (raw) / ~112KB (gzip) into the initial
 * bundle when imported statically. This wrapper lazy-loads the chart chunk
 * only when the component is actually mounted, keeping it out of the home
 * initial bundle (LCP gain estimated +0.5~1s on home).
 *
 * P0-1 perf wave — 2026-05-10.
 *
 * Usage: drop-in replacement for the static import.
 *   - import { EquityCurveChart } from "@/components/home/equity-curve-chart-dynamic";
 *
 * Props: identical to the underlying EquityCurveChart component.
 *
 * SSR: disabled (ssr: false) — recharts uses browser-only SVG APIs and the
 * home page is already fully client-rendered ("use client" + SWR fetchers).
 * No hydration mismatch risk.
 *
 * CLS: ChartSkeleton reserves height={240} (matching the component default)
 * while the chunk is in-flight → layout shift = 0.
 */

import dynamic from "next/dynamic";
import { ChartSkeleton } from "@/components/ui/loading-skeleton";

export const EquityCurveChart = dynamic(
  () =>
    import("./equity-curve-chart").then((mod) => ({
      default: mod.EquityCurveChart,
    })),
  {
    ssr: false,
    loading: () => <ChartSkeleton height={240} />,
  },
);

export default EquityCurveChart;
