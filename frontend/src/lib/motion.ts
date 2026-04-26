// frontend/src/lib/motion.ts
//
// PivoxQuant motion primitives (Wave 1C).
//
// Single source of truth for the easing curve and the most common
// fadeUp / stagger / fadeIn variants used across landing surfaces.
// All landing components must import from here instead of redefining
// EASE / fadeUp / stagger inline — keep one curve, one cadence.

import type { Variants } from "motion/react";

/** Apple HIG / Bloomberg cadence — symmetric ease-out cubic. */
export const PQ_EASE = [0.16, 1, 0.3, 1] as const;

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: PQ_EASE },
  },
};

export const stagger: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 },
  },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.5, ease: PQ_EASE },
  },
};
