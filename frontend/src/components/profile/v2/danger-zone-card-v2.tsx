"use client";

/**
 * <DangerZoneCardV2 />
 *
 * Block 8 of /profile v2 — Agent data + Danger zone (paired cards).
 * Mirror of profile-v2 mockup §731 ("08 · Agent data · PIPA rights").
 *
 * Renders two cards side-by-side:
 *   - Left (col-span-7): "Your CFO's memory is yours." Export agent memory CTA + Delete all agent data red link.
 *   - Right (col-span-5): Danger zone (red border) — mailto support link for account deletion.
 *
 * Pure presentational — host wires `onExport` and `onDelete` (apiFetch).
 *
 * Legal: PIPA · 30-day purge phrasing matches mockup. No advice strings.
 */

import * as React from "react";

interface Props {
  onExport?: () => void;
  onDelete?: () => void;
  exporting?: boolean;
  deleting?: boolean;
  /** Mailto target for account deletion. Defaults to PivoxQuant support address. */
  deleteAccountMailto?: string;
}

const ERROR_COLOR = "var(--pq-error, #d18888)";
const ERROR_BORDER = "rgba(209,136,136,0.18)";
const ERROR_LINK_BORDER = "rgba(209,136,136,0.30)";

export function DangerZoneCardV2({
  onExport,
  onDelete,
  exporting = false,
  deleting = false,
  deleteAccountMailto = "mailto:support@pivoxquant.com?subject=Account%20Deletion%20Request",
}: Props) {
  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(12, minmax(0, 1fr))",
        gap: 12,
        marginBottom: 24,
      }}
      aria-label="Agent data and account deletion"
    >
      {/* Left — Agent data */}
      <div
        style={{
          gridColumn: "span 7",
          background: "rgba(255,255,255,0.02)",
          border: "1px solid var(--pq-ivory-line)",
          borderRadius: 4,
          padding: 24,
          position: "relative",
        }}
      >
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
            marginBottom: 12,
          }}
        >
          08 · Agent data · PIPA rights
        </div>

        <div
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: "var(--pq-text-quote)",
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
            color: "var(--pq-ivory)",
            marginBottom: 12,
          }}
        >
          Your CFO&rsquo;s memory is{" "}
          <span style={{ color: "var(--pq-bronze)", fontStyle: "italic" }}>
            yours.
          </span>
        </div>

        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.82)",
            marginBottom: 20,
          }}
        >
          Export a portable JSON copy of the persona, rolling window, pulses,
          feedback, and Companion history. Or wipe it to start over. Both
          actions comply with PIPA data-rights and run client+server.
        </p>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          <button
            type="button"
            onClick={onExport}
            disabled={exporting}
            className="font-mono uppercase"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 22px",
              background: "var(--pq-bronze)",
              color: "var(--pq-ink, #050505)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              borderRadius: 2,
              border: "none",
              cursor: exporting ? "not-allowed" : "pointer",
              opacity: exporting ? 0.5 : 1,
            }}
          >
            {exporting ? "Preparing…" : "Export agent memory →"}
          </button>

          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: ERROR_COLOR,
              borderBottom: `1px solid ${ERROR_LINK_BORDER}`,
              paddingBottom: 2,
              background: "transparent",
              border: "none",
              borderBottomStyle: "solid",
              cursor: deleting ? "not-allowed" : "pointer",
              opacity: deleting ? 0.5 : 1,
            }}
          >
            {deleting ? "Clearing…" : "Delete all agent data"}
          </button>
        </div>
      </div>

      {/* Right — Danger zone */}
      <div
        style={{
          gridColumn: "span 5",
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${ERROR_BORDER}`,
          borderRadius: 4,
          padding: 24,
          position: "relative",
        }}
      >
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: ERROR_COLOR,
            marginBottom: 12,
          }}
        >
          Danger zone · Account deletion
        </div>

        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.82)",
            marginBottom: 20,
          }}
        >
          Deletion is permanent and removes positions, watchlists, and delivered
          artifacts. PIPA · 30-day purge.
        </p>

        <a
          href={deleteAccountMailto}
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            color: ERROR_COLOR,
            borderBottom: `1px solid ${ERROR_LINK_BORDER}`,
            paddingBottom: 2,
            textDecoration: "none",
          }}
        >
          Contact support to delete
        </a>
      </div>
    </section>
  );
}

export default DangerZoneCardV2;
