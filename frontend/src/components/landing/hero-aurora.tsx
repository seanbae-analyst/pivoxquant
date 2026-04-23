"use client";

/**
 * HeroAurora — cinematic bronze "sunrise" layer.
 * -----------------------------------------------------------------------
 * Three stacked radial gradients (inner bright / mid warm / outer fade)
 * composited via `mix-blend-mode: screen` so the warm light sits on top
 * of the Vantablack ink without ever brightening the whole canvas.
 *
 * Behavior
 *   • Default center: 50% horizontal, 62% vertical (below H1 — gives the
 *     H1 a sense of standing *in* light rather than being washed out).
 *   • Pointer tracking: center follows the cursor with a slow spring
 *     (stiffness 42, damping 24 → ~1.2s visual settle).
 *   • Reduced motion / no pointer: stays at the default resting center
 *     and the largest (outer) layer pulses gently at 24 s.
 *
 * A11y: fully decorative, `aria-hidden`. Not focusable.
 * Perf:  3 div layers, `will-change: transform`, `pointer-events: none`.
 *        An SVG feGaussianBlur softens the innermost layer's edge so the
 *        gradient doesn't band on cheap panels.
 */

import { useCallback, useEffect, useRef } from "react";
import {
  motion,
  useMotionTemplate,
  useReducedMotion,
  useSpring,
} from "motion/react";

type Props = {
  /** Restrict pointer tracking to a specific element (defaults to the
   *  aurora's own bounding rect — fine for full-bleed hero use). */
  trackTarget?: React.RefObject<HTMLElement | null>;
  className?: string;
};

const SPRING = { stiffness: 42, damping: 24, mass: 0.9 } as const;

export function HeroAurora({ trackTarget, className }: Props) {
  const reduceMotion = useReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);

  // Start at resting center so SSR + first paint match.
  const x = useSpring(50, SPRING);
  const y = useSpring(62, SPRING);

  // Compose gradient strings from the springs.
  const innerBg = useMotionTemplate`radial-gradient(circle at ${x}% ${y}%, rgba(210, 170, 120, 0.32) 0%, rgba(184, 149, 106, 0.18) 18%, transparent 40%)`;
  const midBg = useMotionTemplate`radial-gradient(ellipse 70% 55% at ${x}% ${y}%, rgba(184, 149, 106, 0.22) 0%, rgba(139, 111, 71, 0.12) 34%, transparent 64%)`;
  const outerBg = useMotionTemplate`radial-gradient(ellipse 110% 85% at ${x}% ${y}%, rgba(139, 111, 71, 0.18) 0%, rgba(111, 86, 54, 0.08) 40%, transparent 80%)`;

  const onMove = useCallback(
    (ev: PointerEvent) => {
      if (reduceMotion) return;
      const host = trackTarget?.current ?? rootRef.current;
      if (!host) return;
      const r = host.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      const nx = ((ev.clientX - r.left) / r.width) * 100;
      const ny = ((ev.clientY - r.top) / r.height) * 100;
      // Clamp — keeps the center onscreen even at the very edges.
      x.set(Math.max(8, Math.min(92, nx)));
      y.set(Math.max(12, Math.min(92, ny)));
    },
    [reduceMotion, trackTarget, x, y],
  );

  const onLeave = useCallback(() => {
    x.set(50);
    y.set(62);
  }, [x, y]);

  useEffect(() => {
    if (reduceMotion) return;
    const host = trackTarget?.current ?? rootRef.current;
    if (!host) return;
    host.addEventListener("pointermove", onMove, { passive: true });
    host.addEventListener("pointerleave", onLeave);
    return () => {
      host.removeEventListener("pointermove", onMove);
      host.removeEventListener("pointerleave", onLeave);
    };
  }, [onMove, onLeave, reduceMotion, trackTarget]);

  return (
    <div
      ref={rootRef}
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 z-0 overflow-hidden ${className ?? ""}`}
    >
      {/* Outer field — the widest, softest layer. Gently pulses when
          reduced motion is NOT requested, via keyframe (CSS below). */}
      <motion.div
        className={`absolute inset-0 ${reduceMotion ? "" : "pq-aurora-pulse"}`}
        style={{
          background: outerBg,
          mixBlendMode: "screen",
          willChange: "background",
        }}
      />
      {/* Mid warmth */}
      <motion.div
        className="absolute inset-0"
        style={{
          background: midBg,
          mixBlendMode: "screen",
          willChange: "background",
          filter: "blur(8px)",
        }}
      />
      {/* Inner bright — SVG blur for truly soft edge */}
      <motion.div
        className="absolute inset-0"
        style={{
          background: innerBg,
          mixBlendMode: "screen",
          willChange: "background",
          filter: "url(#pq-aurora-blur)",
        }}
      />
      {/* SVG filter source — 16px Gaussian. Tiny, cached. */}
      <svg
        aria-hidden
        width="0"
        height="0"
        style={{ position: "absolute" }}
      >
        <defs>
          <filter id="pq-aurora-blur">
            <feGaussianBlur stdDeviation="16" />
          </filter>
        </defs>
      </svg>
    </div>
  );
}

export default HeroAurora;
