"use client";

/**
 * ParallaxLayer — subtle background parallax using scroll progress.
 *
 * Translates a background layer at a slower rate than the viewport scroll,
 * producing an Apple-style depth effect. Respects prefers-reduced-motion
 * (static, no transform). Absolute-positioned; wrap in a `position: relative`
 * parent.
 *
 * Usage:
 *   <div style={{ position: "relative" }}>
 *     <ParallaxLayer speed={0.3}>
 *       <BackgroundGrain />
 *     </ParallaxLayer>
 *     …foreground…
 *   </div>
 */

import { type ReactNode, useRef } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "motion/react";

export interface ParallaxLayerProps {
  children: ReactNode;
  /** 0 = locked with scroll, 1 = scrolls with page. 0.3 = moves at 30% page rate. */
  speed?: number;
  /** Pixel amplitude over the full scroll range. Default 80px. */
  amplitude?: number;
  /** z-index; default 0. */
  zIndex?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function ParallaxLayer({
  children,
  speed = 0.3,
  amplitude = 80,
  zIndex = 0,
  className,
  style,
}: ParallaxLayerProps) {
  const prefersReduced = useReducedMotion();
  const ref = useRef<HTMLDivElement | null>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useTransform(
    scrollYProgress,
    [0, 1],
    [-(amplitude * (1 - speed)), amplitude * (1 - speed)],
  );

  if (prefersReduced) {
    return (
      <div
        ref={ref}
        className={className}
        style={{
          position: "absolute",
          inset: 0,
          zIndex,
          pointerEvents: "none",
          ...style,
        }}
      >
        {children}
      </div>
    );
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{
        position: "absolute",
        inset: 0,
        y,
        zIndex,
        pointerEvents: "none",
        willChange: "transform",
        ...style,
      }}
    >
      {children}
    </motion.div>
  );
}
