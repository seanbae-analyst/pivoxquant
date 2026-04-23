"use client";

/**
 * FlipPage — a single "book page" within FlipLandingShell.
 *
 * - In shell-active mode (desktop + motion allowed), only the active page is
 *   pointer-interactive. Neighbors stay in the DOM (SEO, a11y) but are
 *   visually hidden behind a 3D rotateX transform with opacity 0 + aria-hidden.
 * - In fallback mode (reduced-motion, mobile, SSR), the page renders as a
 *   normal in-flow section with min-h-screen — no 3D, no hijack.
 *
 * The shell supplies `active`, `direction`, and `enabled`. This component
 * makes no scroll-lock decisions itself.
 */

import { type ReactNode, forwardRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import { useFlipContext } from "./flip-landing-shell";

export interface FlipPageProps {
  /** Zero-based page index within the shell. */
  index: number;
  /** Optional label for a11y / screen readers. */
  label?: string;
  children: ReactNode;
}

export const FlipPage = forwardRef<HTMLElement, FlipPageProps>(function FlipPage(
  { index, label, children },
  ref,
) {
  const prefersReduced = useReducedMotion();
  const { enabled, activeIndex, direction, total } = useFlipContext();
  const active = activeIndex === index;

  // Fallback: stack pages normally as a long scroll page.
  if (!enabled || prefersReduced) {
    return (
      <section
        ref={ref}
        data-flip-index={index}
        data-flip-active={active ? "true" : "false"}
        aria-label={label}
        className="pq-flip-page pq-flip-page--fallback"
      >
        {children}
      </section>
    );
  }

  // Active page → rotateX 0, opacity 1
  // Non-active pages → rotateX ±90deg (above/below based on direction)
  // We bias offscreen pages so the LEAVING page continues in the last direction.
  const rotateX = active ? 0 : direction === 1 ? 90 : -90;
  const y = active ? 0 : direction === 1 ? "6vh" : "-6vh";

  return (
    <motion.section
      ref={ref as never}
      data-flip-index={index}
      data-flip-active={active ? "true" : "false"}
      aria-label={label}
      aria-hidden={!active}
      aria-roledescription="slide"
      role="group"
      className="pq-flip-page pq-flip-page--stage"
      initial={false}
      animate={{
        rotateX,
        opacity: active ? 1 : 0,
        y,
      }}
      transition={{
        duration: 0.95,
        ease: [0.22, 1, 0.36, 1],
      }}
      style={{
        pointerEvents: active ? "auto" : "none",
        transformOrigin: direction === 1 ? "center top" : "center bottom",
        transformStyle: "preserve-3d",
      }}
    >
      <div className="pq-flip-page__inner" tabIndex={active ? undefined : -1}>
        {children}
      </div>
      <span className="sr-only">
        Page {index + 1} of {total}
      </span>
    </motion.section>
  );
});
