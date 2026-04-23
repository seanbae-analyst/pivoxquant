"use client";

/**
 * HeroSpotlight — bronze radial gradient that follows the cursor.
 * ------------------------------------------------------------------
 * Pattern adapted from aceternity/hero-highlight — rebuilt on motion v12
 * (useMotionValue + useMotionTemplate). Respects prefers-reduced-motion.
 *
 * Scope: wraps the Hero section. Reads pointer inside the wrapper only.
 * Palette: bronze (#B8956A) at 15% max, fades to transparent.
 */

import { useCallback } from "react";
import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
} from "motion/react";

type Props = {
  children: React.ReactNode;
  className?: string;
};

export function HeroSpotlight({ children, className }: Props) {
  const reduceMotion = useReducedMotion();

  const mouseX = useMotionValue(-1000);
  const mouseY = useMotionValue(-1000);

  // ~520px circle, bronze @ 15%. Fades to transparent ~70%.
  const spotlight = useMotionTemplate`radial-gradient(520px circle at ${mouseX}px ${mouseY}px, rgba(139, 111, 71, 0.15), transparent 72%)`;

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (reduceMotion) return;
      const rect = e.currentTarget.getBoundingClientRect();
      mouseX.set(e.clientX - rect.left);
      mouseY.set(e.clientY - rect.top);
    },
    [mouseX, mouseY, reduceMotion],
  );

  const onMouseLeave = useCallback(() => {
    mouseX.set(-1000);
    mouseY.set(-1000);
  }, [mouseX, mouseY]);

  return (
    <div
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      className={className}
    >
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0 blur-3xl transition-opacity duration-500"
        style={{ background: spotlight }}
      />
      {children}
    </div>
  );
}

export default HeroSpotlight;
