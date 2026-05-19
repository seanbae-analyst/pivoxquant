// frontend/src/lib/motion.ts
//
// PivoxQuant motion primitives — single source of truth.
//
// All components must import from here instead of redefining EASE / fadeUp /
// stagger inline. Keep one curve, one cadence.
//
// Duration tokens (mirror --motion-duration-* in globals.css):
//   PQ_DUR_MICRO  = 100ms  — SSE price flash / icon hover
//   PQ_DUR_FAST   = 150ms  — button / input / colour transition
//   PQ_DUR_BASE   = 300ms  — card / modal / drawer
//   PQ_DUR_SLOW   = 500ms  — page transitions (use for fadeUp)
//   PQ_DUR_CHART  = 800ms  — chart data count-up / line drawing
//
// SoT: .claude/skills/motion-spec/SKILL.md §2-A + §2-B

import type { Variants } from "motion/react";

/**
 * Apple HIG / Bloomberg cadence — symmetric ease-out cubic.
 * SoT: motion-spec §2-B
 * PQ_EASE === --motion-easing-emphasized (CSS) === cubic-bezier(0.16, 1, 0.3, 1)
 */
export const PQ_EASE = [0.16, 1, 0.3, 1] as const;

// ── Duration constants (seconds, for framer-motion) ──────────────────────
export const PQ_DUR_MICRO = 0.1;  // 100ms — micro / price flash
export const PQ_DUR_FAST  = 0.15; // 150ms — button / input / colour
export const PQ_DUR_BASE  = 0.3;  // 300ms — card / modal / drawer
export const PQ_DUR_SLOW  = 0.5;  // 500ms — page transition
export const PQ_DUR_CHART = 0.8;  // 800ms — chart count-up (CSS only; JS uses requestAnimationFrame)

// ── Variants ─────────────────────────────────────────────────────────────

/** Fade + slight rise — page-section entrance. Duration: PQ_DUR_SLOW (500ms). */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: PQ_DUR_SLOW, ease: PQ_EASE },
  },
};

/**
 * Fade + bottom-sheet rise — modal / drawer entrance (16px = --motion-distance-md).
 * Duration: PQ_DUR_BASE (300ms).
 */
export const slideUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: PQ_DUR_BASE, ease: PQ_EASE },
  },
  exit: {
    opacity: 0,
    y: 16,
    transition: { duration: PQ_DUR_FAST, ease: [0.4, 0.0, 1.0, 1.0] },
  },
};

/** Stagger container — pairs with fadeUp / slideUp children. */
export const stagger: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 },
  },
};

/** Pure opacity fade — no spatial movement. Duration: PQ_DUR_SLOW (500ms). */
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: PQ_DUR_SLOW, ease: PQ_EASE },
  },
};
