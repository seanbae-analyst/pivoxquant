"use client";

/**
 * <TickNumber /> — Numeric display that flashes bronze + slides up 3px
 * when its value changes (e.g. SSE price tick). Currency-aware with
 * configurable decimals so callers don't hand-format.
 *
 * - Respects prefers-reduced-motion — falls back to a plain span.
 * - Pure presentational: does NOT subscribe to SSE directly. The parent
 *   passes `value`; what matters is the value changing between renders.
 */

import { useEffect, useRef, useState } from "react";

interface Props {
  value: number | null | undefined;
  currency?: "USD" | "KRW";
  decimals?: number;
  className?: string;
  /** Duration of the pulse keyframe, ms. Default 220. */
  flashMs?: number;
}

function fmt(
  n: number | null | undefined,
  currency: "USD" | "KRW",
  decimals: number,
): string {
  if (typeof n !== "number" || !Number.isFinite(n))
    return currency === "KRW" ? "\u20A9—" : "$—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  const prefix = currency === "KRW" ? "\u20A9" : "$";
  return `${sign}${prefix}${body}`;
}

export function TickNumber({
  value,
  currency = "USD",
  decimals,
  className = "",
  flashMs = 220,
}: Props) {
  const dec = decimals ?? (currency === "KRW" ? 0 : 2);
  const [flash, setFlash] = useState(false);
  const prevRef = useRef<number | null | undefined>(value);

  useEffect(() => {
    const prev = prevRef.current;
    if (
      typeof prev === "number" &&
      typeof value === "number" &&
      Number.isFinite(prev) &&
      Number.isFinite(value) &&
      prev !== value
    ) {
      const prefersReduced =
        typeof window !== "undefined" &&
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      if (!prefersReduced) {
        setFlash(true);
        const id = setTimeout(() => setFlash(false), flashMs);
        prevRef.current = value;
        return () => clearTimeout(id);
      }
    }
    prevRef.current = value;
  }, [value, flashMs]);

  return (
    <span
      className={`${className} ${flash ? "pq-tick-flash" : ""}`.trim()}
      style={{ display: "inline-block", willChange: "transform, color" }}
    >
      {fmt(value, currency, dec)}
    </span>
  );
}
