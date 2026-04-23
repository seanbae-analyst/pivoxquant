"use client";

/**
 * <PaperDocument /> — primitive sheet-of-paper card.
 *
 * Renders children on an ivory #F5F0E8 surface with bronze-tinted
 * shadow + top-edge curl highlight. Position in 3D space via rotation,
 * zOffset, xOffset. Active paper lifts to z-index 30 and flattens to
 * rotate(0).
 *
 * On mobile (< 768px) all transforms are suppressed by globals.css.
 * All transforms also suppressed when prefers-reduced-motion: reduce.
 *
 * Purely presentational — no data, no legal concern.
 */

import * as React from "react";

interface Props {
  /** Degrees of rotation in the natural stack (e.g. 0, -4, -7). */
  rotation?: number;
  /** Pixels of Z depth offset (negative = further back). */
  zOffset?: number;
  /** Pixels of X-axis offset (for fanning left/right). */
  xOffset?: number;
  /** When true, lifts + flattens + raises z-index. */
  active?: boolean;
  /** When true, dims + pushes back. */
  dimmed?: boolean;
  /** Optional click handler. */
  onClick?: () => void;
  /** Aria label for the paper container. */
  ariaLabel?: string;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}

export function PaperDocument({
  rotation = 0,
  zOffset = 0,
  xOffset = 0,
  active = false,
  dimmed = false,
  onClick,
  ariaLabel,
  className = "",
  style,
  children,
}: Props) {
  const cls = [
    "pq-paper",
    active ? "pq-paper--active" : "",
    dimmed ? "pq-paper--dimmed" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={cls}
      role={onClick ? "button" : "article"}
      tabIndex={onClick ? 0 : undefined}
      aria-label={ariaLabel}
      onClick={onClick}
      onKeyDown={(e) => {
        if (!onClick) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      style={
        {
          "--pq-paper-r": `${rotation}deg`,
          "--pq-paper-z": `${zOffset}px`,
          "--pq-paper-x": `${xOffset}px`,
          ...style,
        } as React.CSSProperties
      }
    >
      {children}
    </div>
  );
}

export default PaperDocument;
