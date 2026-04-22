"use client";

/**
 * InteractiveBarChart — horizontal bar list with hover tooltip showing
 * label, weight percentage, and (optional) absolute value. Designed for
 * /portfolio sector allocation and similar observation-grade breakdowns.
 *
 * Neutral observation language only.
 */

import { useState } from "react";

export interface BarItem {
  label: string;
  pct: number;
  value?: number;
  /** Optional subtitle (e.g. position count) shown in tooltip. */
  sub?: string;
}

export interface InteractiveBarChartProps {
  items: BarItem[];
  valueFormatter?: (v: number) => string;
  barColor?: string;
}

export function InteractiveBarChart({
  items,
  valueFormatter,
  barColor,
}: InteractiveBarChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const bronze = barColor || "var(--pq-bronze, #8B6F47)";

  if (!items.length) {
    return <div className="pq-ink-empty">—</div>;
  }

  return (
    <ul className="space-y-3">
      {items.map((item, i) => {
        const isActive = hoverIdx === i;
        return (
          <li
            key={item.label + i}
            className="relative cursor-crosshair"
            onMouseEnter={() => setHoverIdx(i)}
            onMouseLeave={() => setHoverIdx(null)}
            onTouchStart={() => setHoverIdx(i)}
            onTouchEnd={() => setHoverIdx(null)}
          >
            <div className="flex items-baseline justify-between text-[12px]">
              <span
                style={{
                  color: isActive
                    ? "var(--pq-ivory, #F5F0E8)"
                    : "rgba(245,240,232,0.85)",
                  transition: "color 180ms cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              >
                {item.label}
              </span>
              <span
                className="font-mono tabular-nums"
                style={{
                  color: isActive
                    ? "var(--pq-bronze, #8B6F47)"
                    : "rgba(245,240,232,0.7)",
                  transition: "color 180ms cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              >
                {item.pct.toFixed(1)}%
              </span>
            </div>
            <div
              className="mt-1.5 h-[3px]"
              style={{ background: "rgba(245,240,232,0.08)" }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${Math.min(100, item.pct)}%`,
                  background: bronze,
                  opacity: isActive ? 1 : 0.8,
                  transition: "opacity 180ms cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              />
            </div>

            {/* Tooltip */}
            {isActive && (
              <div
                className="pq-chart-tooltip absolute pointer-events-none"
                style={{
                  left: `${Math.min(92, Math.max(0, item.pct))}%`,
                  top: "-8px",
                  transform: "translate(-50%, -100%)",
                  minWidth: 140,
                }}
              >
                <div
                  className="uppercase"
                  style={{
                    fontSize: "9px",
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze, #8B6F47)",
                    marginBottom: "4px",
                  }}
                >
                  {item.label}
                </div>
                <div
                  className="tabular-nums"
                  style={{
                    fontSize: "14px",
                    color: "var(--pq-ivory, #F5F0E8)",
                    fontFamily: "var(--pq-font-mono, ui-monospace, monospace)",
                  }}
                >
                  {item.pct.toFixed(2)}%
                </div>
                {item.value != null && (
                  <div
                    className="tabular-nums"
                    style={{
                      fontSize: "11px",
                      color: "rgba(245,240,232,0.65)",
                      fontFamily: "var(--pq-font-mono, ui-monospace, monospace)",
                      marginTop: "2px",
                    }}
                  >
                    {valueFormatter ? valueFormatter(item.value) : item.value.toFixed(2)}
                  </div>
                )}
                {item.sub && (
                  <div
                    style={{
                      fontSize: "10px",
                      color: "rgba(245,240,232,0.5)",
                      marginTop: "2px",
                    }}
                  >
                    {item.sub}
                  </div>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
