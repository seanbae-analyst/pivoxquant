"use client";

/**
 * CtaInkBleed — primary CTA with an SVG "ink bleed" hover effect.
 * -----------------------------------------------------------------------
 * Composition
 *   • Base button layer (ivory or bronze fill) — LCP-friendly, renders
 *     identically on SSR.
 *   • Overlay <svg> with feTurbulence + feDisplacementMap driven by a
 *     CSS-animated <feGaussianBlur> and a scaling radial gradient ink
 *     blob. On hover, the blob expands from 0 → 200% in 0.35 s; on
 *     leave it fades in 0.2 s. On active/click the whole button scales
 *     down 0.98 then back.
 *
 * Variants
 *   • `variant="bronze"` — ivory text on bronze fill (primary CTA).
 *   • `variant="ghost"`  — bronze outline, ivory text (secondary).
 *
 * A11y
 *   • Forwards all anchor props (href, target, rel, onClick).
 *   • The ink layer is `aria-hidden`.
 *   • Focus ring: bronze outline, 2px offset.
 *
 * Reduced motion
 *   • The ink blob + scale-on-click are disabled; a simple opacity
 *     hover remains.
 */

import { forwardRef, useId } from "react";
import Link from "next/link";
import { useReducedMotion } from "motion/react";

type Variant = "bronze" | "ivory" | "ghost";

type Props = React.AnchorHTMLAttributes<HTMLAnchorElement> & {
  variant?: Variant;
  /** Use Next <Link> vs plain <a>. Default: Link when href is internal. */
  as?: "link" | "anchor";
  href: string;
  children: React.ReactNode;
  className?: string;
};

function variantStyle(v: Variant): React.CSSProperties {
  switch (v) {
    case "bronze":
      // Ink-on-bronze: WCAG AA contrast ~6.4:1 (was ivory-on-bronze ~2.6:1
      // which read as gold-on-gold and triggered the CEO illegibility flag).
      return {
        backgroundColor: "var(--pq-bronze)",
        color: "var(--pq-ink)",
        border: "1px solid rgba(10, 10, 10, 0.16)",
        boxShadow:
          "0 1px 0 0 rgba(245, 240, 232, 0.32) inset, 0 14px 36px -14px rgba(184, 149, 106, 0.55)",
      };
    case "ivory":
      return {
        backgroundColor: "var(--pq-ivory)",
        color: "var(--pq-ink)",
        border: "1px solid rgba(10, 10, 10, 0.08)",
        boxShadow:
          "0 1px 0 0 rgba(245, 240, 232, 0.30) inset, 0 10px 28px -10px rgba(245, 240, 232, 0.28)",
      };
    case "ghost":
      return {
        backgroundColor: "transparent",
        color: "rgba(245, 240, 232, 0.88)",
        border: "1px solid rgba(139, 111, 71, 0.5)",
        boxShadow: "none",
      };
  }
}

export const CtaInkBleed = forwardRef<HTMLAnchorElement, Props>(
  function CtaInkBleed(
    {
      variant = "bronze",
      as,
      href,
      children,
      className,
      ...rest
    },
    ref,
  ) {
    const reduceMotion = useReducedMotion();
    const filterId = useId().replace(/:/g, "");

    const useLink =
      (as === "link") ||
      (as === undefined && href.startsWith("/") && !href.startsWith("//"));

    const inner = (
      <>
        {/* Ink-bleed overlay — absolute, clipped to the button shape. */}
        {!reduceMotion && (
          <span
            aria-hidden="true"
            className="pq-ink-overlay"
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "inherit",
              overflow: "hidden",
              pointerEvents: "none",
            }}
          >
            <svg
              width="100%"
              height="100%"
              viewBox="0 0 200 60"
              preserveAspectRatio="none"
              style={{ position: "absolute", inset: 0 }}
            >
              <defs>
                <filter id={`ink-${filterId}`}>
                  <feTurbulence
                    type="fractalNoise"
                    baseFrequency="0.9"
                    numOctaves="2"
                    seed="7"
                  />
                  <feDisplacementMap in="SourceGraphic" scale="4" />
                </filter>
                <radialGradient id={`blob-${filterId}`} cx="50%" cy="50%" r="50%">
                  <stop
                    offset="0%"
                    stopColor={
                      variant === "bronze"
                        ? "rgba(245, 240, 232, 0.85)"
                        : "rgba(184, 149, 106, 0.85)"
                    }
                  />
                  <stop
                    offset="55%"
                    stopColor={
                      variant === "bronze"
                        ? "rgba(245, 240, 232, 0.30)"
                        : "rgba(184, 149, 106, 0.38)"
                    }
                  />
                  <stop offset="100%" stopColor="rgba(0,0,0,0)" />
                </radialGradient>
              </defs>
              <rect
                className="pq-ink-blob"
                x="-50"
                y="-25"
                width="300"
                height="110"
                fill={`url(#blob-${filterId})`}
                filter={`url(#ink-${filterId})`}
                style={{ transformOrigin: "50% 50%" }}
              />
            </svg>
          </span>
        )}

        {/* Inner label: own class — must NOT reuse `.pq-ink-label` (global
            utility forces bronze + 9.5px uppercase, which collides with
            the bronze CTA fill → gold-on-gold). Inherit color from button. */}
        <span
          className="pq-ink-btn-label"
          style={{
            position: "relative",
            zIndex: 1,
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            color: "inherit",
          }}
        >
          {children}
        </span>
      </>
    );

    const base =
      "pq-ink-btn group relative inline-flex h-12 items-center gap-2 overflow-hidden rounded-sm px-6 text-[14px] font-medium tracking-wide";
    const transition =
      "transition-transform duration-200 hover:-translate-y-px active:translate-y-0";
    const style = variantStyle(variant);

    if (useLink) {
      return (
        <Link
          href={href}
          ref={ref}
          className={`${base} ${transition} ${className ?? ""}`}
          style={style}
          {...rest}
        >
          {inner}
        </Link>
      );
    }

    return (
      <a
        href={href}
        ref={ref}
        className={`${base} ${transition} ${className ?? ""}`}
        style={style}
        {...rest}
      >
        {inner}
      </a>
    );
  },
);

export default CtaInkBleed;
