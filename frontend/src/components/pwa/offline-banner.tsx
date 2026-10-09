"use client";

/**
 * <OfflineBanner> — one line above the screen while the device is offline
 * (2026-10-09). Before this, tapping a tab offline replaced the whole app
 * with /offline.html. The service worker now serves the cached app shell for
 * the dashboard screens (public/sw.js), so the app stays on screen and this
 * line says why the records are not loading. It disappears on its own when
 * the connection returns; SWR revalidates on reconnect by itself.
 *
 * Observational copy only. Server render and first paint assume online, so
 * the banner never flashes on a normal load.
 */

import { useSyncExternalStore } from "react";
import { WifiOff } from "lucide-react";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

const readOnline = () => navigator.onLine !== false;
const serverOnline = () => true;

export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, readOnline, serverOnline);
}

export function OfflineBanner() {
  const online = useOnline();
  if (online) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-4 flex items-center gap-2 rounded-[2px] border border-[var(--pq-ivory-line)] bg-[var(--pq-card-veil)] px-3 py-2 text-[13px] leading-snug text-[var(--pq-ivory-mid)]"
      data-testid="offline-banner"
    >
      <WifiOff className="h-4 w-4 shrink-0 text-[var(--pq-bronze)]" strokeWidth={1.5} aria-hidden />
      <span>오프라인입니다. 연결되면 기록을 다시 불러옵니다.</span>
    </div>
  );
}
