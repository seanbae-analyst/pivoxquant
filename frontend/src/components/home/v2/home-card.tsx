"use client";

/**
 * <HomeCard /> — generic gallery card shell for /home v2.
 *
 * SPEC §2 (home-v2):
 * - Border 1px hairline → bronze on hover; bg fades to bronze 0.025 alpha.
 * - 240ms cubic-bezier(0.16,1,0.3,1) transition.
 * - Eyebrow kicker (mono uppercase, bronze) at top.
 * - Optional "corner CTA" mono uppercase top-right, ivory→bronze on hover.
 * - Whole card is the link target (href).
 * - Min height 280 (220 on mobile via CSS clamp).
 */

import * as React from "react";
import Link from "next/link";

interface HomeCardProps {
  href: string;
  eyebrow: string;
  cornerCta?: string;
  ariaLabel?: string;
  minHeight?: number;
  children: React.ReactNode;
}

export function HomeCard({
  href,
  eyebrow,
  cornerCta,
  ariaLabel,
  minHeight = 280,
  children,
}: HomeCardProps) {
  return (
    <Link
      href={href}
      aria-label={ariaLabel ?? `${eyebrow} — open ${href}`}
      className="pq-home-card-v2"
      style={{
        position: "relative",
        display: "flex",
        flexDirection: "column",
        background: "var(--pq-card-bg-ink, rgba(255,255,255,0.02))",
        border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
        borderRadius: 4,
        padding: 24,
        minHeight,
        textDecoration: "none",
        color: "inherit",
        transition:
          "border-color 240ms cubic-bezier(0.16,1,0.3,1), background-color 240ms cubic-bezier(0.16,1,0.3,1)",
      }}
    >
      {cornerCta ? (
        <span
          className="pq-home-card-v2__corner font-mono uppercase"
          style={{
            position: "absolute",
            top: 14,
            right: 14,
            fontSize: 12,
            letterSpacing: "0.2em",
            color: "rgba(245,240,232,0.55)",
            textTransform: "uppercase",
            transition: "color 240ms",
          }}
        >
          {cornerCta}
        </span>
      ) : null}

      <div
        className="font-mono uppercase"
        style={{
          fontSize: 12,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          color: "rgba(245, 240, 232, 0.6)",
          marginBottom: 20,
        }}
      >
        {eyebrow}
      </div>

      {children}
    </Link>
  );
}

/** Hover styles applied via inline <style> (scoped to this component class). */
export function HomeCardStyles() {
  return (
    <style jsx global>{`
      .pq-home-card-v2:hover {
        border-color: var(--muted-foreground) !important;
        background: rgba(184, 149, 106, 0.025) !important;
      }
      .pq-home-card-v2:hover .pq-home-card-v2__corner {
        color: var(--muted-foreground) !important;
      }
      @media (prefers-reduced-motion: reduce) {
        .pq-home-card-v2 {
          transition: none !important;
        }
      }
    `}</style>
  );
}

export default HomeCard;
