/**
 * Editorial micro-components — small typographic marks reused across
 * dashboard pages to lift the visual grade from functional to published.
 *
 * These are intentionally stateless, style-driven via inline CSS so they
 * render correctly even before `globals.css` picks up matching utility
 * classes. Matching CSS class names are still applied (`pq-fleuron`,
 * `pq-caption`, `pq-ink-kicker--ruled`, `pq-num-display`, `pq-hairline-soft`)
 * so designer-owned stylesheet upgrades layer cleanly on top.
 *
 * Safe to import anywhere. Pure presentational, no data dependencies.
 */

import * as React from "react";

/** Ornamental fleuron (❦). Sits on its own line, centered by default. */
export function Fleuron({
  className = "",
  char = "\u2766",
  size = 14,
}: {
  className?: string;
  char?: string;
  size?: number;
}) {
  return (
    <span
      aria-hidden="true"
      className={`pq-fleuron ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "var(--font-serif), Georgia, serif",
        fontSize: `${size}px`,
        lineHeight: 1,
        letterSpacing: "0.4em",
        color: "var(--pq-bronze)",
        opacity: 0.75,
      }}
    >
      {char}
    </span>
  );
}

/** Thin 24px bronze rule + small-caps kicker. Sits above a section heading. */
export function RuledKicker({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`pq-ink-kicker pq-ink-kicker--ruled ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        fontFamily: "var(--font-sans), system-ui, sans-serif",
        fontSize: "9.5px",
        letterSpacing: "0.24em",
        textTransform: "uppercase",
        color: "var(--pq-bronze)",
        fontWeight: 500,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          display: "inline-block",
          width: 24,
          height: 1,
          background: "var(--pq-bronze)",
          opacity: 0.7,
        }}
      />
      <span>{children}</span>
    </div>
  );
}

/** Italic serif deck line — reads as a one-sentence chapeau under the kicker. */
export function DeckLine({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={`font-serif italic ${className}`}
      style={{
        fontFamily: "var(--font-serif), Georgia, serif",
        fontStyle: "italic",
        fontSize: "clamp(1.1rem, 1.6vw, 1.35rem)",
        lineHeight: 1.25,
        color: "var(--pq-ivory)",
        letterSpacing: "-0.005em",
        marginTop: 8,
      }}
    >
      {children}
    </p>
  );
}

/** Small italic serif caption — descriptive annotation under a heading/stat. */
export function Caption({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={`pq-caption ${className}`}
      style={{
        fontFamily: "var(--font-serif), Georgia, serif",
        fontStyle: "italic",
        fontSize: "11.5px",
        lineHeight: 1.4,
        color: "rgba(245,240,232,0.55)",
      }}
    >
      {children}
    </p>
  );
}

/** Tabular-mono display numeric with tight tracking. Drop into stat cards. */
export function NumDisplay({
  children,
  className = "",
  tone,
  size = 30,
}: {
  children: React.ReactNode;
  className?: string;
  tone?: "pos" | "neg" | "neu";
  size?: number;
}) {
  const color =
    tone === "pos"
      ? "#7db487"
      : tone === "neg"
      ? "#d18888"
      : "var(--pq-ivory)";
  return (
    <span
      className={`pq-num-display ${className}`}
      style={{
        fontFamily:
          "var(--font-mono), 'JetBrains Mono', ui-monospace, monospace",
        fontVariantNumeric: "tabular-nums",
        fontFeatureSettings: "\"tnum\"",
        fontSize: `${size}px`,
        lineHeight: 1.05,
        letterSpacing: "-0.015em",
        color,
      }}
    >
      {children}
    </span>
  );
}

/** Hair-line top divider on ink. 0.5px bronze-tinted ivory. */
export function HairlineSoft({ className = "" }: { className?: string }) {
  return (
    <div
      className={`pq-hairline-soft ${className}`}
      style={{
        height: 0,
        borderTop: "0.5px solid rgba(245,240,232,0.08)",
      }}
    />
  );
}

/**
 * Footer signature — placed at the base of each dashboard page, just
 * above the DisclaimerBanner. Fleuron + italic caption.
 */
export function FootSignature({
  note = "PivoxQuant \u00b7 Observational research only \u00b7 Not investment advice",
}: {
  note?: string;
}) {
  return (
    <footer
      className="pq-foot-signature"
      style={{
        marginTop: "2.5rem",
        paddingTop: "1.25rem",
        borderTop: "0.5px solid rgba(245,240,232,0.06)",
        textAlign: "center",
      }}
    >
      <div style={{ marginBottom: 6 }}>
        <Fleuron size={13} />
      </div>
      <p
        className="pq-caption"
        style={{
          fontFamily: "var(--font-serif), Georgia, serif",
          fontStyle: "italic",
          fontSize: "11px",
          lineHeight: 1.45,
          color: "rgba(245,240,232,0.45)",
          letterSpacing: "0.02em",
        }}
      >
        {note}
      </p>
    </footer>
  );
}
