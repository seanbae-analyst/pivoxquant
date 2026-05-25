"use client";

/**
 * <PriceWithTimestamp /> — Neutral "price + last observed" display.
 *
 * Every current-price surface in the app should wrap its number in this
 * component so users see, at a glance, when the number was last observed.
 *
 * Visual contract:
 *   - Mono-tabular price (tabular-nums) — stays aligned under flashes.
 *   - Beside it: a small dot + "Xs ago" relative timestamp.
 *     * Green dot  → observed within the last 2 seconds (live).
 *     * Bronze dot → observed recently (< staleThresholdMs).
 *     * Yellow dot → stale (observation older than the threshold).
 *
 * Law / neutrality:
 *   - "observed" / "live" / "stale" only — no advice / guarantee language.
 *
 * Self-ticks every 1s so the relative label is always accurate without
 * requiring the parent to re-render.
 */

import { useEffect, useState } from "react";

interface Props {
  price: number | null | undefined;
  /** ISO 8601 timestamp of when the price was observed on the backend. */
  observedAt?: string | null;
  currency?: "USD" | "KRW";
  size?: "sm" | "md" | "lg";
  /** Whether to render the "Xs ago" chip beside the price. */
  showTimestamp?: boolean;
  /** Threshold (ms) beyond which the observation is considered stale. */
  staleThresholdMs?: number;
  className?: string;
}

function formatPrice(
  price: number | null | undefined,
  currency: "USD" | "KRW",
): string {
  if (price == null) return "—";
  // Backend occasionally serializes low-priced micro-caps (e.g. ABTC @ $1.30)
  // as strings when they come through a cached SignalCache hydration path.
  // Coerce defensively before the finiteness check so the price shows.
  const n = typeof price === "number" ? price : Number(price);
  if (!Number.isFinite(n)) return "—";
  if (currency === "KRW") {
    return "KRW " + Math.round(n).toLocaleString();
  }
  // Sub-dollar equities need more decimals so "0.0125" doesn't render as "USD 0.01".
  if (Math.abs(n) < 1) return "USD " + n.toFixed(4);
  return "USD " + n.toFixed(2);
}

function relativeTime(
  iso: string | null | undefined,
  now: number,
): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "—";
  const sec = Math.max(0, Math.floor((now - t) / 1000));
  if (sec < 2) return "live";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function PriceWithTimestamp({
  price,
  observedAt,
  currency = "USD",
  size = "md",
  showTimestamp = true,
  staleThresholdMs = 60_000,
  className = "",
}: Props) {
  // Tick every second so the relative label updates even if the parent
  // doesn't re-render. Cheap — one setInterval per instance.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const priceStr = formatPrice(price, currency);
  const rel = relativeTime(observedAt, now);
  const obsMs = observedAt ? new Date(observedAt).getTime() : 0;
  const hasObservation = !!observedAt && Number.isFinite(obsMs);
  const isStale = !observedAt || now - obsMs > staleThresholdMs;
  const isLive = rel === "live";

  const sizeCls = {
    sm: "text-pq-body-sm",
    md: "text-pq-h6",
    lg: "text-pq-callout",
  }[size];

  return (
    <span className={`inline-flex items-baseline gap-2 ${className}`}>
      <span
        className={`font-mono tabular-nums ${sizeCls}`}
        style={{ color: "var(--pq-ivory)" }}
      >
        {priceStr}
      </span>
      {/* FINDING-037: with no observedAt the chip used to render a pulsing
          dot + bare "—" ("· —") whose meaning was undefined to the user.
          Render an explicit "OBSERVATION PENDING" label instead — no dot. */}
      {showTimestamp && !hasObservation && (
        <span
          className="font-mono text-pq-mono-sm uppercase tracking-[0.16em]"
          style={{ color: "rgba(245,240,232,0.45)" }}
        >
          Observation pending
        </span>
      )}
      {showTimestamp && hasObservation && (
        <span className="inline-flex items-center gap-1 font-mono text-pq-caption uppercase tracking-[0.16em]">
          {isStale ? (
            <span
              className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--pq-stale)]"
              title="Stale — last observation is over 1 minute old"
            />
          ) : isLive ? (
            <span
              className="h-1.5 w-1.5 rounded-full bg-[var(--pq-live)]"
              title="Live — just observed"
            />
          ) : (
            <span
              className="h-1.5 w-1.5 rounded-full bg-[var(--pq-bronze)] opacity-70"
              title="Recently observed"
            />
          )}
          <span
            style={{
              color: isStale ? "rgba(234,179,8,0.8)" : "rgba(245,240,232,0.55)",
            }}
          >
            {rel}
          </span>
        </span>
      )}
    </span>
  );
}

/**
 * Shared `relativeTime()` helper so page-level "Live · Xs ago" banners can
 * render the same label format without duplicating logic.
 */
export { relativeTime };
