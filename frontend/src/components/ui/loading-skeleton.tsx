import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("pq-skeleton-dark", className)} />;
}

/**
 * ChartSkeleton — fixed-height placeholder for lazy-loaded recharts charts.
 *
 * Used by equity-curve-chart-dynamic.tsx and sector-allocation-donut-dynamic.tsx
 * as the `loading` prop in next/dynamic. The explicit height matches the
 * default `height` prop of each chart (240px) so CLS is 0 while the chunk
 * is in-flight.
 */
export function ChartSkeleton({ height = 240 }: { height?: number }) {
  return (
    <div
      style={{
        height,
        background: "rgba(255,255,255,0.02)",
        border: "1px solid var(--pq-ivory-line)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      aria-hidden="true"
    >
      <Skeleton className="h-4 w-32" />
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 space-y-4">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-2 w-full" />
    </div>
  );
}

export function TableRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3">
      <Skeleton className="h-8 w-8 rounded-lg" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-16" />
      </div>
      <Skeleton className="h-5 w-16" />
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Top row: 4 metric cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
      {/* Chart area */}
      <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6">
        <Skeleton className="h-4 w-32 mb-4" />
        <Skeleton className="h-64 w-full" />
      </div>
      {/* Table */}
      <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)]">
        {Array.from({ length: 5 }).map((_, i) => (
          <TableRowSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}
