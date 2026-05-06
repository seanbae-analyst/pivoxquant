"use client";

/**
 * <SettingsIdentityCardV2 />
 *
 * Section A1 of /settings v2 — Identity card.
 * Mirror of settings-v2 mockup §540 ("A1 · Identity").
 *
 * Renders three rows:
 *   - Display name (read-only mono · "Edit" link → /profile)
 *   - Email (read-only)
 *   - Locale (한국어 / English pill toggle — bilingual labels per CEO 2026-04-28)
 *
 * Pure presentational. Host wires `useAuth()` + `useLocale()`.
 *
 * Legal: persona vocabulary only. No advice strings.
 */

import * as React from "react";
import Link from "next/link";

interface Props {
  displayName?: string | null;
  email?: string | null;
  /** Active locale code. */
  locale: "ko" | "en";
  onLocaleChange: (next: "ko" | "en") => void;
  /** Path to the page that owns name editing (Profile). */
  editHref?: string;
}

const ROW_LABEL_STYLE: React.CSSProperties = {
  fontSize: 14,
  color: "var(--pq-ivory)",
};
const ROW_HELP_STYLE: React.CSSProperties = {
  fontSize: 12.5,
  color: "rgba(245,240,232,0.40)",
  marginTop: 2,
};
const ROW_VALUE_STYLE: React.CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontSize: 13,
  color: "rgba(245,240,232,0.82)",
};

export function SettingsIdentityCardV2({
  displayName,
  email,
  locale,
  onLocaleChange,
  editHref = "/profile",
}: Props) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(245,240,232,0.08)",
        borderRadius: 4,
        padding: 24,
        position: "relative",
      }}
    >
      <span
        className="font-mono uppercase"
        style={{
          position: "absolute",
          top: 14,
          right: 14,
          fontSize: 9.5,
          letterSpacing: "0.2em",
          color: "rgba(245,240,232,0.40)",
        }}
      >
        A1 · Identity
      </span>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: 10.5,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 16,
        }}
      >
        Signed-in as
      </div>

      {/* Display name */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 14,
          padding: "0 0 14px",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div className="font-serif" style={ROW_LABEL_STYLE}>Display name</div>
          <div className="font-serif" style={ROW_HELP_STYLE}>
            Used on memos, brag cards, and exports.
          </div>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <span className="font-mono" style={ROW_VALUE_STYLE}>{displayName || "—"}</span>
          <Link
            href={editHref}
            className="font-mono uppercase"
            style={{
              fontSize: 10,
              letterSpacing: "0.18em",
              color: "var(--pq-bronze)",
              borderBottom: "1px solid rgba(184,149,106,0.15)",
              paddingBottom: 2,
              textDecoration: "none",
            }}
          >
            Edit
          </Link>
        </div>
      </div>

      {/* Email */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 14,
          padding: "14px 0",
          borderTop: "1px solid rgba(245,240,232,0.08)",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div className="font-serif" style={ROW_LABEL_STYLE}>Email</div>
          <div className="font-serif" style={ROW_HELP_STYLE}>Verified · primary contact.</div>
        </div>
        <span
          className="font-mono"
          style={{
            ...ROW_VALUE_STYLE,
            fontSize: 12.5,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            maxWidth: 240,
          }}
          title={email ?? undefined}
        >
          {email || "—"}
        </span>
      </div>

      {/* Locale row — bilingual labels per CEO 2026-04-28 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 14,
          padding: "14px 0 0",
          borderTop: "1px solid rgba(245,240,232,0.08)",
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div className="font-serif" style={ROW_LABEL_STYLE}>Locale</div>
          <div className="font-serif" style={ROW_HELP_STYLE}>
            한국어 / English. Number convention follows locale.
          </div>
        </div>
        <div
          role="group"
          aria-label="Language"
          style={{ display: "flex", gap: 8 }}
        >
          {(["ko", "en"] as const).map((code) => {
            const active = locale === code;
            const label = code === "ko" ? "한국어" : "English";
            return (
              <button
                key={code}
                type="button"
                aria-pressed={active}
                onClick={() => onLocaleChange(code)}
                className="font-mono uppercase"
                style={{
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  border: `1px solid ${
                    active
                      ? "var(--pq-bronze)"
                      : "rgba(245,240,232,0.14)"
                  }`,
                  color: active
                    ? "var(--pq-bronze)"
                    : "rgba(245,240,232,0.55)",
                  background: "transparent",
                  borderRadius: 2,
                  padding: "4px 10px",
                  cursor: "pointer",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default SettingsIdentityCardV2;
