"use client";

/**
 * <SettingsIdentityCardV2 />
 *
 * Section A1 of /settings v2 — Identity card.
 * Mirror of settings-v2 mockup §540 ("A1 · Identity").
 *
 * Renders three rows:
 *   - Display name (read-only mono). 2026-09-12: the "Edit" link pointed at
 *     /profile, which never had a name editor (and is now deleted) — removed.
 *   - Email (read-only)
 *   - Locale (한국어 / English pill toggle — bilingual labels per CEO 2026-04-28)
 *
 * Pure presentational. Host wires `useAuth()` + `useLocale()`.
 *
 * Legal: persona vocabulary only. No advice strings.
 */

import * as React from "react";

interface Props {
  displayName?: string | null;
  email?: string | null;
  /** Active locale code. */
  locale: "ko" | "en";
  onLocaleChange: (next: "ko" | "en") => void;
}

const ROW_LABEL_STYLE: React.CSSProperties = {
  fontSize: "var(--pq-text-body)",
  color: "var(--pq-ivory)",
};
const ROW_HELP_STYLE: React.CSSProperties = {
  fontSize: "var(--pq-text-body)",
  color: "var(--pq-ivory-dim)",
  marginTop: 2,
};
const ROW_VALUE_STYLE: React.CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontSize: "var(--pq-text-body)",
  color: "var(--pq-ivory-strong)",
};

export function SettingsIdentityCardV2({
  displayName,
  email,
  locale,
  onLocaleChange,
}: Props) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid var(--pq-ivory-line)",
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
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.2em",
          color: "var(--pq-ivory-dim)",
        }}
      >
        A1 · Identity
      </span>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
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
            Shown in the app and on your data exports.
          </div>
        </div>
        <span className="font-mono" style={ROW_VALUE_STYLE}>{displayName || "—"}</span>
      </div>

      {/* Email */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 14,
          padding: "14px 0",
          borderTop: "1px solid var(--pq-ivory-line)",
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
            fontSize: "var(--pq-text-body)",
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
          borderTop: "1px solid var(--pq-ivory-line)",
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
                  fontSize: "var(--pq-text-eyebrow)",
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
