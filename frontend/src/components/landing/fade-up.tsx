"use client";

/**
 * FadeUp — Revolut-style fade-up entry wrapper.
 *
 * Typography / decks / cards enter with y:40 → 0 + opacity 0 → 1 when scrolled
 * into view. Stagger via `delay` prop. Respects prefers-reduced-motion (static
 * render, no animation).
 *
 * Usage:
 *   <FadeUp>…</FadeUp>
 *   <FadeUp delay={0.06}>…</FadeUp>
 *   <FadeUp as="h2" delay={0.12}>…</FadeUp>
 */

import { type ReactNode, type ElementType } from "react";
import { motion, useReducedMotion } from "motion/react";

export interface FadeUpProps {
  children: ReactNode;
  /** Delay in seconds (use for stagger). Default 0. */
  delay?: number;
  /** Distance in px. Default 32. */
  distance?: number;
  /** Duration in seconds. Default 0.7. */
  duration?: number;
  /** Element tag. Default "div". */
  as?: ElementType;
  /** Margin for in-view detection. Default "-10% 0px". */
  viewportMargin?: string;
  /** Additional className. */
  className?: string;
  /** Inline style. */
  style?: React.CSSProperties;
}

export function FadeUp({
  children,
  delay = 0,
  distance = 32,
  duration = 0.7,
  as = "div",
  viewportMargin = "-10% 0px",
  className,
  style,
}: FadeUpProps) {
  const prefersReduced = useReducedMotion();

  if (prefersReduced) {
    const Tag = as as ElementType;
    return (
      <Tag className={className} style={style}>
        {children}
      </Tag>
    );
  }

  const MotionTag = motion(as as keyof React.JSX.IntrinsicElements);

  return (
    <MotionTag
      className={className}
      style={style}
      initial={{ opacity: 0, y: distance }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: viewportMargin }}
      transition={{
        duration,
        delay,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {children}
    </MotionTag>
  );
}
