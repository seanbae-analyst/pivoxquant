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
      className={`pq-fleuron font-serif ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
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
      className={`pq-ink-kicker pq-ink-kicker--ruled font-sans ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        fontSize: "var(--pq-text-eyebrow)",
        letterSpacing: "0.24em",
        textTransform: "uppercase",
        color: "var(--pq-bronze)",
        fontWeight: 500,
      }}
    >
      <span
        aria-hidden="true"
        className="pq-ruled-kicker-hairline"
        style={{
          display: "inline-block",
          width: 24,
          height: 1,
          background: "var(--pq-bronze)",
          opacity: 0.7,
          transformOrigin: "left center",
        }}
      />
      <span>{children}</span>
    </div>
  );
}

/** Serif deck line — reads as a one-sentence chapeau under the kicker. Upright. */
export function DeckLine({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={`font-serif ${className}`}
      style={{
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

/** Small serif caption — descriptive annotation under a heading/stat. Upright. */
export function Caption({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={`pq-caption font-serif ${className}`}
      style={{
        fontSize: "var(--pq-text-eyebrow)",
        lineHeight: 1.4,
        color: "rgba(245,240,232,0.55)",
      }}
    >
      {children}
    </p>
  );
}

/**
 * Editorial heading — Playfair Display serif, used for v3 section/card
 * headings sized 18~40px. Replaces inline `style={{ fontFamily: '"Playfair
 * Display"...', fontSize: 24~40 }}` patterns scattered across dashboard
 * pages. Anchors design.md §3 typography tokens (h3 = 30px, quote = 22px).
 *
 * - `size`: discrete px value (18 | 22 | 26 | 30 | 32 | 36 | 40)
 * - `tone`: ivory (default) | bronze | muted
 * - `as`: semantic tag (h1 | h2 | h3 | div | p)
 *
 * Children may include `<span>` runs for italic / bronze accents
 * (matches existing pattern: "Tell the CFO <em>how you read.</em>").
 */
export function EditorialHead({
  children,
  size = 30,
  tone = "ivory",
  as = "h2",
  className = "",
  style,
}: {
  children: React.ReactNode;
  size?: 18 | 22 | 26 | 30 | 32 | 36 | 40;
  tone?: "ivory" | "bronze" | "muted";
  as?: "h1" | "h2" | "h3" | "div" | "p";
  className?: string;
  style?: React.CSSProperties;
}) {
  const Tag = as as React.ElementType;
  const color =
    tone === "bronze"
      ? "var(--pq-bronze)"
      : tone === "muted"
      ? "rgba(245,240,232,0.55)"
      : "var(--pq-ivory)";
  return (
    <Tag
      className={`pq-editorial-head font-display ${className}`}
      style={{
        fontWeight: 500,
        fontSize: size,
        lineHeight: 1.15,
        letterSpacing: "-0.02em",
        color,
        margin: 0,
        ...style,
      }}
    >
      {children}
    </Tag>
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
  // KR convention (CEO directive 2026-04-26): pos = red, neg = blue.
  // v3 tokens: --up (#D18888 carmine) / --down (#7AA0C8 indigo).
  const color =
    tone === "pos"
      ? "var(--up)"
      : tone === "neg"
      ? "var(--down)"
      : "var(--pq-ivory)";
  return (
    <span
      className={`pq-num-display font-mono ${className}`}
      style={{
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
        borderTop: "0.5px solid var(--pq-ivory-line)",
      }}
    />
  );
}

/**
 * Field label — tighter tracking than a section kicker, sized for
 * in-panel data labels ("Current price", "Market cap", etc.). Replaces
 * the old `text-[10px] tracking-[0.22em] uppercase` pattern that made
 * labels look like "C U R R E N T  P R I C E" in the detail page.
 *
 * Uses OpenType small-caps + 0.12em tracking for editorial scanability.
 */
export function FieldLabel({
  children,
  className = "",
  tone = "bronze",
}: {
  children: React.ReactNode;
  className?: string;
  tone?: "bronze" | "muted";
}) {
  const color =
    tone === "muted" ? "rgba(245,240,232,0.55)" : "var(--pq-bronze)";
  return (
    <span
      className={`pq-field-label font-sans ${className}`}
      style={{
        display: "inline-block",
        fontSize: "var(--pq-text-eyebrow)",
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        color,
        fontWeight: 500,
        lineHeight: 1.3,
      }}
    >
      {children}
    </span>
  );
}

/**
 * Stat row — key/value inline pair, hairline-separated. Use inside a
 * fundamentals panel as a dense, editorial alternative to box grids.
 */
export function StatRow({
  label,
  value,
  tone,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  tone?: "pos" | "neg" | "neu";
}) {
  // KR convention (CEO directive 2026-04-26): pos = red, neg = blue.
  // v3 tokens: --up (#D18888 carmine) / --down (#7AA0C8 indigo).
  const color =
    tone === "pos"
      ? "var(--up)"
      : tone === "neg"
      ? "var(--down)"
      : "var(--pq-ivory)";
  return (
    <div className="pq-detail-stat-row">
      <span className="pq-detail-stat-row-label">{label}</span>
      <span className="pq-detail-stat-row-value" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

/**
 * Footer signature — placed at the base of each dashboard page, just
 * above the DisclaimerBanner. Fleuron + italic caption.
 */
// FINDING-038: this default used to repeat "Observational research only \u00b7
// Not investment advice" \u2014 the SAME legal text the page-level
// DisclaimerBanner (mounted by (dashboard)/layout.tsx) already carries.
// Stacking the legal disclaimer twice is trust-by-volume, not
// trust-by-clarity. The signature is now a pure brand mark; the single
// consolidated legal disclaimer lives in the DisclaimerBanner only.
export function FootSignature({
  note = "PivoxQuant \u00b7 Living CFO",
}: {
  note?: string;
}) {
  return (
    <footer
      className="pq-foot-signature"
      style={{
        marginTop: "2.5rem",
        paddingTop: "1.25rem",
        borderTop: "0.5px solid var(--pq-ivory-line-soft)",
        textAlign: "center",
      }}
    >
      <div style={{ marginBottom: 6 }}>
        <Fleuron size={13} />
      </div>
      <p
        className="pq-caption font-serif"
        style={{
          fontStyle: "italic",
          fontSize: "var(--pq-text-eyebrow)",
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
