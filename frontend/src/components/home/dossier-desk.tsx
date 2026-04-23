"use client";

/**
 * <DossierDesk /> — top-level /home wrapper.
 *
 * Sets up the 3D stage: Vantablack ink desk + film grain + ivory
 * spotlight + corner vignette, and a tilt frame that responds to
 * pointer position with ±1.5deg of rotateX/Y.
 *
 * The tilt is applied via CSS variables `--pq-tilt-x` / `--pq-tilt-y`
 * so the transform update does not force a React re-render on every
 * mouse move (requestAnimationFrame throttled).
 *
 * Children are rendered inside the tilt frame. Papers (stacked z-3D)
 * live there. Reduced motion + mobile disable tilt via globals.css.
 *
 * No data dependencies. Pure presentation.
 */

import * as React from "react";
import { FilmGrain } from "@/components/landing/film-grain";

interface Props {
  children: React.ReactNode;
  /** Max degrees of rotation. Default 1.5. */
  maxTilt?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function DossierDesk({
  children,
  maxTilt = 1.5,
  className = "",
  style,
}: Props) {
  const deskRef = React.useRef<HTMLDivElement | null>(null);
  const tiltRef = React.useRef<HTMLDivElement | null>(null);
  const rafRef = React.useRef<number | null>(null);
  const pendingRef = React.useRef<{ x: number; y: number } | null>(null);

  const [enabled, setEnabled] = React.useState(true);
  React.useEffect(() => {
    const m = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (m?.matches) setEnabled(false);
    const mobile = window.matchMedia?.("(max-width: 767px)");
    if (mobile?.matches) setEnabled(false);
  }, []);

  React.useEffect(() => {
    if (!enabled) return;
    const desk = deskRef.current;
    const tilt = tiltRef.current;
    if (!desk || !tilt) return;

    const flush = () => {
      rafRef.current = null;
      if (!pendingRef.current || !tiltRef.current) return;
      const { x, y } = pendingRef.current;
      tiltRef.current.style.setProperty("--pq-tilt-x", `${x}deg`);
      tiltRef.current.style.setProperty("--pq-tilt-y", `${y}deg`);
    };

    const onMove = (e: PointerEvent) => {
      const rect = desk.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const nx = (e.clientX - rect.left) / rect.width - 0.5;
      const ny = (e.clientY - rect.top) / rect.height - 0.5;
      pendingRef.current = {
        x: Number((-ny * maxTilt * 2).toFixed(3)),
        y: Number((nx * maxTilt * 2).toFixed(3)),
      };
      if (rafRef.current == null) {
        rafRef.current = requestAnimationFrame(flush);
      }
    };

    const onLeave = () => {
      pendingRef.current = { x: 0, y: 0 };
      if (rafRef.current == null) {
        rafRef.current = requestAnimationFrame(flush);
      }
    };

    desk.addEventListener("pointermove", onMove);
    desk.addEventListener("pointerleave", onLeave);
    return () => {
      desk.removeEventListener("pointermove", onMove);
      desk.removeEventListener("pointerleave", onLeave);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [enabled, maxTilt]);

  return (
    <div
      ref={deskRef}
      className={`pq-dossier-desk ${className}`}
      style={style}
    >
      <FilmGrain opacity={0.04} blendMode="overlay" />
      <div className="pq-dossier-spotlight" aria-hidden />
      <div className="pq-dossier-vignette" aria-hidden />
      <div ref={tiltRef} className="pq-dossier-tilt">
        {children}
      </div>
    </div>
  );
}

export default DossierDesk;
