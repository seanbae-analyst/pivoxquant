import type { CSSProperties, ReactNode } from "react";

/**
 * <Eyebrow/> — bronze section label (plain text since 2026-10-22).
 *
 * Used to introduce sections / hero blocks across the landing surface.
 * Replaces the inline pattern:
 *
 *   <span className="h-px w-7" style={{ backgroundColor: "rgba(184,149,106,0.7)" }} />
 *   <span style={{ color: "#B8956A", fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.01em" }}>
 *     LABEL
 *   </span>
 *
 * Tokens consumed: --pq-bronze, --pq-bronze-rgb, --pq-text-eyebrow,
 * --pq-track-eyebrow.
 */
interface EyebrowProps {
  children: ReactNode;
  /** @deprecated 2026-10-22 — hairlines retired; accepted, draws nothing. */
  withDashLeft?: boolean;
  /** @deprecated 2026-10-22 — hairlines retired; accepted, draws nothing. */
  withDashRight?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function Eyebrow({
  children,
  className = "",
  style,
}: EyebrowProps) {
  // 2026-10-22: no hairline, no uppercase — the 2026-10-11 refresh retired
  // ruled kickers and tracked capitals (frontend/CLAUDE.md). The dash props
  // stay accepted so callers need not change; they draw nothing.
  return (
    <div
      className={`inline-flex items-center ${className}`.trim()}
      style={style}
    >
      <span
        style={{
          color: "var(--pq-bronze)",
          fontSize: "var(--pq-text-body-sm)",
          fontWeight: 500,
          letterSpacing: "var(--pq-track-eyebrow)",
        }}
      >
        {children}
      </span>
    </div>
  );
}

