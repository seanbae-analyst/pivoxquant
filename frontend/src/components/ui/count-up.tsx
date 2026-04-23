"use client";

/**
 * <CountUp /> — Cinematic count-up for a hero NAV or currency figure.
 *
 * - Animates 0 → target over `durationMs` using ease-out-expo.
 * - Runs once on mount; subsequent value changes snap without re-running.
 * - Respects `prefers-reduced-motion` — renders the final value immediately.
 * - Currency-aware rendering (USD "$" / KRW "₩") with configurable decimals,
 *   so callers don't need to pass a format callback.
 * - Purely presentational — no SWR, no data fetching, no side effects.
 */

import { useEffect, useRef, useState } from "react";

interface Props {
  /** Target numeric value to count up to. */
  value: number | null | undefined;
  /** Currency symbol to prefix. Defaults to USD. */
  currency?: "USD" | "KRW";
  /** Decimal digits. Defaults: USD=2, KRW=0. */
  decimals?: number;
  /** Animation duration in ms. Default 1500. */
  durationMs?: number;
  /** Whether to animate. Default true. When false, final value renders instantly. */
  animate?: boolean;
  /**
   * Optional storage key — when set, the most recent final value is cached in
   * sessionStorage under this key so subsequent mounts (navigating home →
   * detail → home) animate from last-seen value rather than `$0`. Without a
   * key, we still avoid the $0 flash by skipping the intro animation when the
   * first-observed value is already numeric (e.g. SWR cache hit).
   */
  storageKey?: string;
  className?: string;
}

function easeOutExpo(t: number): number {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

function fmt(
  n: number,
  currency: "USD" | "KRW",
  decimals: number,
): string {
  if (!Number.isFinite(n)) return currency === "KRW" ? "\u20A9—" : "$—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  const prefix = currency === "KRW" ? "\u20A9" : "$";
  return `${sign}${prefix}${body}`;
}

/** Read the last-seen value for a storage key. Returns null on any failure. */
function readLastSeen(key: string | undefined): number | null {
  if (!key || typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(`pq-count-up:${key}`);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

function writeLastSeen(key: string | undefined, value: number): void {
  if (!key || typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(`pq-count-up:${key}`, String(value));
  } catch {
    // sessionStorage disabled — safe to ignore.
  }
}

export function CountUp({
  value,
  currency = "USD",
  decimals,
  durationMs = 1500,
  animate = true,
  storageKey,
  className,
}: Props) {
  const dec = decimals ?? (currency === "KRW" ? 0 : 2);
  // If value is absent (undefined/null/NaN) treat as "not yet loaded" and
  // hold previous/cached number. Only coerce to 0 when an explicit 0 arrives.
  const hasValue = typeof value === "number" && Number.isFinite(value);
  const target = hasValue ? (value as number) : 0;

  // Initial paint: prefer sessionStorage cache → target (if we have one) → 0.
  // This avoids the TOTAL BOOK "$0.00 → animate" flash on every navigation
  // when the caller hasn't yet handed us a number (SWR still loading).
  const [current, setCurrent] = useState<number>(() => {
    if (!animate) return target;
    const cached = readLastSeen(storageKey);
    if (cached != null) return cached;
    // If the first value is already known on mount, skip intro animation —
    // the $0 flash is the user-visible regression we're fixing.
    if (hasValue) return target;
    return 0;
  });
  const frameRef = useRef<number | null>(null);
  const ranRef = useRef(false);

  useEffect(() => {
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    if (!animate || prefersReduced) {
      setCurrent(target);
      ranRef.current = true;
      return;
    }
    if (ranRef.current) {
      setCurrent(target);
      return;
    }

    // If we already have a cached or first-paint value that equals target,
    // nothing to animate — mark as ran so future updates snap.
    const cached = readLastSeen(storageKey);
    const startValue = cached != null ? cached : hasValue ? target : 0;
    if (startValue === target) {
      ranRef.current = true;
      setCurrent(target);
      return;
    }
    ranRef.current = true;

    const start = performance.now();
    const delta = target - startValue;
    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const eased = easeOutExpo(t);
      setCurrent(startValue + delta * eased);
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        setCurrent(target);
      }
    };
    frameRef.current = requestAnimationFrame(tick);

    return () => {
      if (frameRef.current != null) cancelAnimationFrame(frameRef.current);
    };
    // Only animate once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Snap to new target after the initial animation completes, and persist
  // the latest observed value so the next mount starts from a sane place.
  useEffect(() => {
    if (ranRef.current && hasValue) setCurrent(target);
    if (hasValue) writeLastSeen(storageKey, target);
  }, [target, hasValue, storageKey]);

  return <span className={className}>{fmt(current, currency, dec)}</span>;
}
