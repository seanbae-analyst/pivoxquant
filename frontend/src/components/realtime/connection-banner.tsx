"use client";

/**
 * ConnectionBanner — Shows a warning strip when the SSE realtime
 * connection is lost. Automatically hides when reconnected.
 */

import { useRealtimeContext } from "@/lib/realtime";

export function ConnectionBanner() {
  const { connected, lastUpdate } = useRealtimeContext();

  // Don't show anything if connected or if we've never connected
  // (avoid flash on initial mount before first SSE message)
  if (connected || lastUpdate === null) return null;

  const ago = lastUpdate
    ? Math.round((Date.now() - lastUpdate) / 1000)
    : null;

  return (
    <div className="flex items-center justify-center gap-2 bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-amber-700 shrink-0">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
      <span className="text-[11px] font-semibold">
        Reconnecting...
        {ago !== null && ago > 5 && (
          <span className="font-normal text-amber-600 ml-1">
            Last update {ago}s ago
          </span>
        )}
      </span>
    </div>
  );
}
