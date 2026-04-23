"use client";

/**
 * StickyScrubSection — Apple/Revolut sticky-pin pattern.
 *
 * A tall outer container (`totalHeight` viewports) with an inner sticky pane.
 * A scroll-linked `activeIndex` callback fires as the user scrolls, allowing
 * consumers to cross-fade through N "stages" (artifact 1 → 2 → 3 …) while
 * the pinned visual stays locked.
 *
 * - On mobile (<1024px) OR prefers-reduced-motion: renders a simple flat
 *   div; stages all show; no sticky, no scrub.
 * - On desktop: outer height is `stages * 100vh`, inner is `position: sticky`
 *   at top.
 *
 * Usage:
 *   <StickyScrubSection
 *     stages={17}
 *     render={(active) => (
 *       <div className="grid grid-cols-2">
 *         <div className="sticky">{visual}</div>
 *         <div>{labels[active]}</div>
 *       </div>
 *     )}
 *   />
 */

import { type ReactNode, useRef, useState, useEffect } from "react";
import { useScroll, useMotionValueEvent, useReducedMotion } from "motion/react";

export interface StickyScrubSectionProps {
  /** Number of discrete stages. */
  stages: number;
  /** Height per stage in viewport units. Default 0.6. */
  stageVh?: number;
  /** Render children; receives current active stage (0..stages-1). */
  render: (activeIndex: number, progress: number) => ReactNode;
  /** Optional className for the outer container. */
  className?: string;
}

export function StickyScrubSection({
  stages,
  stageVh = 0.6,
  render,
  className,
}: StickyScrubSectionProps) {
  const prefersReduced = useReducedMotion();
  const outerRef = useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const [active, setActive] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    setMounted(true);
    const check = () => setIsDesktop(window.innerWidth >= 1024);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const enabled = mounted && isDesktop && !prefersReduced;

  const { scrollYProgress } = useScroll({
    target: outerRef,
    offset: ["start start", "end end"],
  });

  useMotionValueEvent(scrollYProgress, "change", (latest) => {
    if (!enabled) return;
    const clamped = Math.max(0, Math.min(0.9999, latest));
    const idx = Math.floor(clamped * stages);
    setActive(idx);
    setProgress(latest);
  });

  if (!enabled) {
    // Mobile / reduced motion: flat render with active=0 (consumer can still
    // render full list statically if needed by ignoring the index).
    return (
      <div ref={outerRef} className={className}>
        <div>{render(active, 0)}</div>
      </div>
    );
  }

  const outerHeight = `${Math.max(stages * stageVh, 1.5) * 100}vh`;

  return (
    <div
      ref={outerRef}
      className={className}
      style={{ position: "relative", height: outerHeight }}
    >
      <div
        style={{
          position: "sticky",
          top: 0,
          height: "100vh",
          display: "flex",
          alignItems: "center",
          overflow: "hidden",
        }}
      >
        {render(active, progress)}
      </div>
    </div>
  );
}
