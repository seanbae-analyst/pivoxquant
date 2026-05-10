"use client";

/**
 * sector-allocation-donut-dynamic.tsx — next/dynamic wrapper for SectorAllocationDonut.
 *
 * Purpose: same as equity-curve-chart-dynamic.tsx — removes the recharts
 * chunk from the home initial bundle. Both components share the recharts
 * package so the split happens once; either dynamic call is the trigger.
 *
 * P0-1 perf wave — 2026-05-10.
 *
 * Usage: drop-in replacement for the static import.
 *   - import { SectorAllocationDonut } from "@/components/home/sector-allocation-donut-dynamic";
 *
 * Props: identical to the underlying SectorAllocationDonut component.
 *
 * SSR: disabled (ssr: false) — same reasoning as equity-curve-chart-dynamic.
 *
 * CLS: ChartSkeleton reserves height={240} while the chunk loads → CLS = 0.
 */

import dynamic from "next/dynamic";
import { ChartSkeleton } from "@/components/ui/loading-skeleton";

export const SectorAllocationDonut = dynamic(
  () =>
    import("./sector-allocation-donut").then((mod) => ({
      default: mod.SectorAllocationDonut,
    })),
  {
    ssr: false,
    loading: () => <ChartSkeleton height={240} />,
  },
);

export default SectorAllocationDonut;
