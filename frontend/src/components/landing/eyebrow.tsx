import type { CSSProperties, ReactNode } from "react";

/**
 * <Eyebrow/> — bronze tracked-out section label.
 *
 * Used to introduce sections / hero blocks across the landing surface.
 * Replaces the inline pattern:
 *
 *   <span className="h-px w-7" style={{ backgroundColor: "rgba(184,149,106,0.7)" }} />
 *   <span style={{ color: "#B8956A", fontSize: 12, letterSpacing: "0.22em" }}>
 *     LABEL
 *   </span>
 *
 * Tokens consumed: --pq-bronze, --pq-bronze-rgb, --pq-text-eyebrow,
 * --pq-track-eyebrow.
 */
interface EyebrowProps {
  children: ReactNode;
  /** Render the leading bronze hairline (default: true). */
  withDashLeft?: boolean;
  /** Render a trailing bronze hairline (default: false). */
  withDashRight?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function Eyebrow({
  children,
  withDashLeft = true,
  withDashRight = false,
  className = "",
  style,
}: EyebrowProps) {
  return (
    <div
      className={`inline-flex items-center gap-2.5 ${className}`.trim()}
      style={style}
    >
      {withDashLeft ? (
        <span
          aria-hidden
          className="h-px w-7"
          style={{ backgroundColor: "rgba(var(--pq-bronze-rgb), 0.7)" }}
        />
      ) : null}
      <span
        className="font-serif uppercase"
        style={{
          color: "var(--pq-bronze)",
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "var(--pq-track-eyebrow)",
        }}
      >
        {children}
      </span>
      {withDashRight ? (
        <span
          aria-hidden
          className="h-px w-7"
          style={{ backgroundColor: "rgba(var(--pq-bronze-rgb), 0.7)" }}
        />
      ) : null}
    </div>
  );
}
