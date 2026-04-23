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

export function CountUp({
  value,
  currency = "USD",
  decimals,
  durationMs = 1500,
  animate = true,
  className,
}: Props) {
  const dec = decimals ?? (currency === "KRW" ? 0 : 2);
  const target =
    typeof value === "number" && Number.isFinite(value) ? value : 0;

  const [current, setCurrent] = useState<number>(() => (animate ? 0 : target));
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
    ranRef.current = true;

    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const eased = easeOutExpo(t);
      setCurrent(target * eased);
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

  // Snap to new target after the initial animation completes.
  useEffect(() => {
    if (ranRef.current) setCurrent(target);
  }, [target]);

  return <span className={className}>{fmt(current, currency, dec)}</span>;
}
