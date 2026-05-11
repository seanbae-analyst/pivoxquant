"use client";

/**
 * KpiCard — dense terminal KPI block.
 *
 * A compact, dark-tone card used across the terminal dashboard. No white
 * background, no rounded paper; just a tight hairline rectangle with a
 * monospaced value and an optional delta + sparkline.
 *
 * Props:
 *   - label: the metric name (uppercase, tracked, 10.5px).
 *   - value: the primary number (TickNumber-style flash on change).
 *   - delta: optional % or absolute change with sign. Color-coded.
 *   - format: "currency" | "percent" | "plain". Default "plain".
 *   - currency: "USD" | "KRW" when format === "currency". Default "USD".
 *   - sparkline: optional number[] to render a micro line inside the card.
 *   - size: "sm" | "md". "md" is the default dashboard density.
 *
 * Visual: `var(--pq-terminal-bg)` bg, `var(--pq-terminal-line)` border, bronze (`var(--pq-bronze)`) accent label rule.
 * Flash: 300ms bg wash on value change (green/red by delta sign).
 */

import { useEffect, useMemo, useRef } from "react";

export type KpiFormat = "currency" | "percent" | "plain";
export type KpiSize = "sm" | "md";

export interface KpiCardProps {
  label: string;
  value: number | string | null | undefined;
  delta?: number | null;
  /** Absolute (e.g. +$1,240) or percent (+2.41%). Auto-signed if numeric. */
  deltaFormat?: "percent" | "absolute";
  format?: KpiFormat;
  currency?: "USD" | "KRW";
  sparkline?: number[];
  size?: KpiSize;
  /** Optional suffix (e.g. "bps", "positions"). */
  suffix?: string;
  className?: string;
}

function fmtValue(
  v: number | string | null | undefined,
  fmt: KpiFormat,
  currency: "USD" | "KRW",
): string {
  if (v == null || v === "") return "—";
  if (typeof v === "string") return v;
  if (!Number.isFinite(v)) return "—";

  if (fmt === "percent") {
    return `${v >= 0 ? "" : ""}${v.toFixed(2)}%`;
  }
  if (fmt === "currency") {
    const abs = Math.abs(v);
    const sign = v < 0 ? "-" : "";
    const decimals = currency === "KRW" ? 0 : 2;
    const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    const prefix = currency === "KRW" ? "\u20A9" : "$";
    return `${sign}${prefix}${body}`;
  }
  return v.toLocaleString("en-US");
}

function fmtDelta(d: number | null | undefined, mode: "percent" | "absolute"): string {
  if (d == null || !Number.isFinite(d)) return "";
  const sign = d > 0 ? "+" : "";
  if (mode === "percent") return `${sign}${d.toFixed(2)}%`;
  return `${sign}${d.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

/** Lightweight SVG sparkline — no external dep. */
function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length < 2) return null;
  const w = 72;
  const h = 22;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      aria-hidden
      style={{ flexShrink: 0, display: "block" }}
    >
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.92"
      />
    </svg>
  );
}

export function KpiCard({
  label,
  value,
  delta,
  deltaFormat = "percent",
  format = "plain",
  currency = "USD",
  sparkline,
  size = "md",
  suffix,
  className = "",
}: KpiCardProps) {
  // Flash background tinted up/down on value change. Implemented as a direct
  // DOM mutation via ref so the effect doesn't need setState (which would
  // trip react-hooks/set-state-in-effect).
  const cardRef = useRef<HTMLDivElement>(null);
  const prevRef = useRef(value);
  useEffect(() => {
    const prev = prevRef.current;
    prevRef.current = value;
    if (
      typeof prev !== "number" ||
      typeof value !== "number" ||
      prev === value ||
      !Number.isFinite(prev) ||
      !Number.isFinite(value)
    ) {
      return;
    }
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    const el = cardRef.current;
    if (!el) return;
    const dir: "up" | "down" = value > prev ? "up" : "down";
    const tint =
      dir === "up" ? "rgba(125,180,135,0.14)" : "rgba(209,136,136,0.14)";
    el.style.backgroundColor = tint;
    const id = window.setTimeout(() => {
      // Restore baseline. Match the static `background` color below.
      if (cardRef.current) cardRef.current.style.backgroundColor = "";
    }, 300);
    return () => window.clearTimeout(id);
  }, [value]);

  const deltaColor = useMemo(() => {
    // KR convention (CEO directive 2026-04-26): ▲ rising = red, ▼ falling = blue.
    if (delta == null) return "rgba(245,240,232,0.55)";
    if (delta > 0) return "var(--pq-terminal-up)";
    if (delta < 0) return "var(--pq-terminal-down)";
    return "rgba(245,240,232,0.55)";
  }, [delta]);

  const padding = size === "sm" ? "10px 12px" : "14px 16px";
  const valueSize = size === "sm" ? 18 : 22;
  const labelSize = size === "sm" ? 9.5 : 10.5;

  return (
    <div
      ref={cardRef}
      className={`pq-kpi-card ${className}`.trim()}
      style={{
        background: "var(--pq-terminal-bg)",
        border: "1px solid var(--pq-terminal-line)",
        padding,
        display: "flex",
        flexDirection: "column",
        gap: 6,
        position: "relative",
        transition: "background-color 0.3s ease, border-color 0.2s ease",
        backgroundColor: "var(--pq-terminal-bg)",
      }}
    >
      {/* Bronze label rule */}
      <div className="flex items-center justify-between gap-2">
        <span
          className="font-mono uppercase"
          style={{
            fontSize: labelSize,
            letterSpacing: "0.22em",
            color: "var(--pq-bronze, #B8956A)",
            opacity: 0.9,
          }}
        >
          {label}
        </span>
        {sparkline && sparkline.length >= 2 && (
          <Sparkline data={sparkline} color={deltaColor} />
        )}
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-2">
        <span
          className="font-mono tabular-nums"
          style={{
            fontSize: valueSize,
            lineHeight: 1.1,
            color: "rgba(245,240,232,0.98)",
            fontWeight: 500,
            letterSpacing: "-0.01em",
          }}
        >
          {fmtValue(value, format, currency)}
        </span>
        {suffix && (
          <span
            className="font-mono uppercase"
            style={{
              fontSize: 12,
              letterSpacing: "0.16em",
              color: "rgba(245,240,232,0.45)",
            }}
          >
            {suffix}
          </span>
        )}
      </div>

      {/* Delta */}
      {delta != null && Number.isFinite(delta) && (
        <div
          className="font-mono tabular-nums"
          style={{
            fontSize: 12,
            color: deltaColor,
            letterSpacing: "0.02em",
          }}
        >
          {fmtDelta(delta, deltaFormat)}
        </div>
      )}
    </div>
  );
}

export default KpiCard;
