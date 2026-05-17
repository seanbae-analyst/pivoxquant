"use client";

/**
 * what-if-chart-dynamic.tsx — next/dynamic wrapper for WhatIfChart.
 *
 * Purpose: recharts pulls ~391KB (raw) / ~112KB (gzip) into the bundle
 * when imported statically. The /simulator/what-if route's main client
 * component (what-if-client.tsx) imports what-if-result.tsx, which in
 * turn statically imports WhatIfChart — recharts ends up on first
 * paint before the user has even submitted the form.
 *
 * Mirror of the same pattern at:
 *   - components/home/equity-curve-chart-dynamic.tsx
 *   - components/home/sector-allocation-donut-dynamic.tsx
 *
 * 2026-05-17 wave 12 frontend P2 (PR #431).
 *
 * SSR: disabled (ssr: false) — recharts uses browser-only SVG APIs and
 * the simulator route is already fully client-rendered.
 *
 * CLS: ChartSkeleton reserves height={320} (matching what-if-chart.tsx
 * default ResponsiveContainer height) while the chunk is in-flight.
 */

import dynamic from "next/dynamic";
import { ChartSkeleton } from "@/components/ui/loading-skeleton";

export const WhatIfChart = dynamic(
  () =>
    import("./what-if-chart").then((mod) => ({
      default: mod.WhatIfChart,
    })),
  {
    ssr: false,
    loading: () => <ChartSkeleton height={320} />,
  },
);

export default WhatIfChart;
