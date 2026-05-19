"use client";

/**
 * SectionCurtain — Worldquantfoundry-style scroll-triggered chapter reveal.
 * --------------------------------------------------------------------------
 * Wraps a section so the first 600-800px of it acts as a "curtain":
 *   1. A bronze hairline draws horizontally across the viewport.
 *   2. The section content emerges via clip-path inset reveal (top→bottom).
 *   3. A subtle parallax pushes the content up as it enters.
 *
 * Inspired by worldquantfoundry.com (Three.js + GSAP). Implemented with
 * motion/react useScroll + useTransform — no extra libs, no Three.js.
 *
 * Palette guardrail: ONLY Vantablack / Bronze / Ivory tokens.
 */

import { useRef } from "react";
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";

interface SectionCurtainProps {
  children: React.ReactNode;
  /** Vertical fraction (0-1) of the curtain reveal window. Default 0.45. */
  revealEnd?: number;
  /** When true, draws the bronze divider line. Default true. */
  divider?: boolean;
  className?: string;
  id?: string;
}

export function SectionCurtain({
  children,
  revealEnd = 0.45,
  divider = true,
  className = "",
  id,
}: SectionCurtainProps) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);

  // Entrance phase only: progress 0→1 from "section top at viewport bottom"
  // to "section top at viewport top". Reveal happens as the section enters,
  // not over the full scroll-through (which would stretch on tall sections).
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "start start"],
  });

  // Bronze divider draws from 0 → full width across [0, revealEnd].
  const dividerWidth = useTransform(
    scrollYProgress,
    [0, revealEnd * 0.7],
    ["0%", "100%"],
  );
  const dividerOpacity = useTransform(
    scrollYProgress,
    [0, revealEnd * 0.4, revealEnd, revealEnd + 0.05],
    [0, 0.85, 0.85, 0],
  );

  // Content reveal: clip-path opens from TOP downward over [0.02, revealEnd].
  // inset(0 0 100% 0) → nothing visible (clipped from bottom up).
  // inset(0 0 0 0)    → fully visible.
  // So eyebrow at top of section is the first thing to appear.
  const clipBottom = useTransform(
    scrollYProgress,
    [0.02, revealEnd],
    ["100%", "0%"],
  );
  const clipPath = useTransform(clipBottom, (v) => `inset(0 0 ${v} 0)`);
  const contentY = useTransform(
    scrollYProgress,
    [0, revealEnd, 1],
    [40, 0, -20],
  );
  const contentOpacity = useTransform(
    scrollYProgress,
    [0, revealEnd * 0.4, revealEnd],
    [0, 0.6, 1],
  );

  if (reduce) {
    return (
      <section id={id} className={className}>
        {children}
      </section>
    );
  }

  return (
    <section id={id} ref={ref} className={`relative ${className}`}>
      {/* Bronze hairline curtain divider */}
      {divider && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 z-10 flex justify-center"
          style={{ height: 1 }}
        >
          <motion.span
            className="block h-px"
            style={{
              width: dividerWidth,
              opacity: dividerOpacity,
              backgroundColor: "rgba(184, 149, 106, 0.7)",
            }}
          />
        </div>
      )}

      {/* Content with clip-path mask reveal + subtle parallax */}
      <motion.div
        style={{
          clipPath,
          WebkitClipPath: clipPath,
          y: contentY,
          opacity: contentOpacity,
        }}
      >
        {children}
      </motion.div>
    </section>
  );
}

export default SectionCurtain;
