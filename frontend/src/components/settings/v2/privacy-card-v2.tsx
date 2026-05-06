"use client";

/**
 * <PrivacyCardV2 />
 *
 * Section E of /settings v2 — Privacy (Cookie consent + Data export + Danger zone).
 * Mirror of settings-v2 mockup §889 ("E · Privacy · PIPA · GDPR").
 *
 * Three surfaces stacked:
 *   - E1 Cookie consent (4 categories — Strictly necessary always-on, Analytics,
 *     Performance, Marketing). Persisted to localStorage (GAP-C — backend
 *     `consent_log` table not yet present).
 *   - E2 Data export (last export timestamp + "Request new export →" CTA;
 *     GAP-X — backend `/api/profile/export` endpoint not yet declared).
 *   - E3 Danger zone (Sign out + Delete account; mailto fallback per v1 — GAP-J).
 *     ModalShell is reused for the delete-account confirmation flow.
 *
 * Pure presentational. Host wires `useAuth().logout`.
 *
 * Legal: persona vocabulary only. PIPA · 30-day purge phrasing matches mockup.
 */

import * as React from "react";
import { ModalShell } from "@/components/ui/modal-shell";
import { AlertTriangle, X } from "lucide-react";

const ERROR_COLOR = "var(--pq-error, #d18888)";
const ERROR_BORDER = "rgba(209,136,136,0.18)";
const ERROR_LINK_BORDER = "rgba(209,136,136,0.30)";

const COOKIE_LS_KEY = "pq_cookie_consent_v2";

type CookieCategory = "necessary" | "analytics" | "performance" | "marketing";
type CookieState = Record<CookieCategory, boolean>;

const DEFAULT_COOKIES: CookieState = {
  necessary: true, // always on, no toggle
  analytics: true,
  performance: true,
  marketing: false,
};

const COOKIE_ROWS: Array<{
  id: CookieCategory;
  label: string;
  help: string;
  alwaysOn?: boolean;
}> = [
  {
    id: "necessary",
    label: "Strictly necessary",
    help: "Auth session, CSRF, locale. Required for sign-in.",
    alwaysOn: true,
  },
  {
    id: "analytics",
    label: "Analytics",
    help: "Anonymized page-view counts. Self-hosted.",
  },
  {
    id: "performance",
    label: "Performance",
    help: "Web Vitals · LCP / CLS / INP — for engineering.",
  },
  {
    id: "marketing",
    label: "Marketing",
    help: "Off by default. We do not use ad-tech cookies.",
  },
];

function readCookies(): CookieState {
  if (typeof window === "undefined") return DEFAULT_COOKIES;
  try {
    const raw = window.localStorage.getItem(COOKIE_LS_KEY);
    if (!raw) return DEFAULT_COOKIES;
    const parsed = JSON.parse(raw) as Partial<CookieState>;
    return {
      necessary: true,
      analytics: parsed.analytics ?? DEFAULT_COOKIES.analytics,
      performance: parsed.performance ?? DEFAULT_COOKIES.performance,
      marketing: parsed.marketing ?? DEFAULT_COOKIES.marketing,
    };
  } catch {
    return DEFAULT_COOKIES;
  }
}

function writeCookies(state: CookieState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(COOKIE_LS_KEY, JSON.stringify(state));
  } catch {
    /* quota/disabled — silently degrade */
  }
}

function PrivacyToggle({
  on,
  onChange,
  ariaLabel,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={ariaLabel}
      onClick={() => onChange(!on)}
      style={{
        position: "relative",
        display: "inline-block",
        width: 36,
        height: 20,
        background: on ? "var(--pq-bronze)" : "rgba(245,240,232,0.10)",
        borderRadius: 999,
        transition: "background 200ms",
        flexShrink: 0,
        border: "none",
        cursor: "pointer",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 3,
          left: 3,
          width: 14,
          height: 14,
          background: "var(--pq-ivory)",
          borderRadius: 999,
          transition: "transform 200ms",
          transform: on ? "translateX(16px)" : "translateX(0)",
        }}
      />
    </button>
  );
}

function DeleteAccountModal({
  onClose,
  mailto,
}: {
  onClose: () => void;
  mailto: string;
}) {
  return (
    <ModalShell onClose={onClose} ariaLabel="Delete account">
      <div
        className="my-auto w-full max-w-md"
        style={{
          background: "var(--pq-ink, #050505)",
          border: "1px solid rgba(245,240,232,0.12)",
          padding: 24,
          borderRadius: 2,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 16,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle
              className="h-4 w-4"
              style={{ color: ERROR_COLOR }}
            />
            <h3
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: 20,
                color: "var(--pq-ivory)",
              }}
            >
              Delete account
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              color: "rgba(245,240,232,0.55)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
            }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p
          className="font-serif"
          style={{
            fontSize: 14,
            color: "rgba(245,240,232,0.65)",
            marginBottom: 24,
          }}
        >
          Deletion is permanent and removes all positions, watchlists,
          persona snapshots, and delivered artifacts. PIPA · 30-day purge
          after request.
        </p>
        <div style={{ display: "flex", gap: 12 }}>
          <a
            href={mailto}
            className="font-mono uppercase"
            style={{
              flex: 1,
              textAlign: "center",
              padding: "11px 20px",
              background: "var(--pq-bronze)",
              color: "var(--pq-ink, #050505)",
              fontSize: 11,
              letterSpacing: "0.2em",
              borderRadius: 2,
              textDecoration: "none",
            }}
          >
            Contact support
          </a>
          <button
            type="button"
            onClick={onClose}
            className="font-mono uppercase"
            style={{
              flex: 1,
              padding: "11px 20px",
              background: "transparent",
              color: "var(--pq-bronze)",
              border: "1px solid var(--pq-bronze)",
              fontSize: 11,
              letterSpacing: "0.2em",
              borderRadius: 2,
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

interface Props {
  /** Last export metadata, for the E2 row. */
  lastExport?: { at: string; size?: string };
  onRequestExport?: () => void;
  onSignOut?: () => void;
  signingOut?: boolean;
  /** Mailto for account deletion — defaults to PivoxQuant support address. */
  deleteAccountMailto?: string;
}

export function PrivacyCardV2({
  lastExport,
  onRequestExport,
  onSignOut,
  signingOut,
  deleteAccountMailto = "mailto:support@pivoxquant.com?subject=Account%20Deletion%20Request",
}: Props) {
  const [cookies, setCookies] = React.useState<CookieState>(DEFAULT_COOKIES);
  const [showDelete, setShowDelete] = React.useState(false);

  React.useEffect(() => {
    setCookies(readCookies());
  }, []);

  const setCookie = (id: CookieCategory, next: boolean) => {
    setCookies((prev) => {
      const updated: CookieState = { ...prev, [id]: next, necessary: true };
      writeCookies(updated);
      return updated;
    });
  };

  return (
    <section
      id="section-e"
      style={{ scrollMarginTop: 96 }}
      aria-label="Privacy"
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 16,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: 10.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            E · Privacy · PIPA · GDPR
          </div>
          <div
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: 30,
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
            }}
          >
            Your data is{" "}
            <span style={{ color: "var(--pq-bronze)", fontStyle: "italic" }}>
              yours.
            </span>
          </div>
        </div>
        <a
          href="/privacy"
          className="font-mono uppercase"
          style={{
            fontSize: 11,
            letterSpacing: "0.18em",
            color: "var(--pq-bronze)",
            borderBottom: "1px solid rgba(184,149,106,0.15)",
            paddingBottom: 2,
            textDecoration: "none",
          }}
        >
          Privacy policy ›
        </a>
      </div>

      {/* E1 + E2 split */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 12,
          marginBottom: 12,
        }}
        className="pq-privacy-grid"
      >
        {/* E1 — Cookie consent */}
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
            E1 · Consent
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
            Cookie consent · Granular
          </div>

          {COOKIE_ROWS.map((row, idx) => (
            <div
              key={row.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 14,
                padding: "14px 0",
                borderTop:
                  idx === 0
                    ? undefined
                    : "1px solid rgba(245,240,232,0.08)",
                paddingTop: idx === 0 ? 0 : 14,
                paddingBottom: idx === COOKIE_ROWS.length - 1 ? 0 : 14,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  className="font-serif"
                  style={{
                    fontSize: 14,
                    color: "var(--pq-ivory)",
                  }}
                >
                  {row.label}
                </div>
                <div
                  className="font-serif"
                  style={{
                    fontSize: 12.5,
                    color: "rgba(245,240,232,0.40)",
                    marginTop: 2,
                  }}
                >
                  {row.help}
                </div>
              </div>
              {row.alwaysOn ? (
                <span
                  className="font-mono uppercase"
                  style={{
                    display: "inline-block",
                    padding: "2px 8px",
                    fontSize: 9.5,
                    letterSpacing: "0.18em",
                    border: "1px solid rgba(184,149,106,0.15)",
                    color: "var(--pq-bronze)",
                    borderRadius: 2,
                  }}
                >
                  Always on
                </span>
              ) : (
                <PrivacyToggle
                  on={cookies[row.id]}
                  onChange={(next) => setCookie(row.id, next)}
                  ariaLabel={row.label}
                />
              )}
            </div>
          ))}
        </div>

        {/* E2 — Data export */}
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
            E2 · Export
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
            Data export · PIPA Art. 35
          </div>

          <p
            className="font-serif"
            style={{
              fontSize: 13,
              lineHeight: 1.55,
              color: "rgba(245,240,232,0.82)",
              marginBottom: 20,
            }}
          >
            Download a portable JSON copy of your account: positions,
            watchlist, persona snapshots, pulse history, and delivered
            artifact metadata.
          </p>

          {lastExport ? (
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
                <div
                  className="font-serif"
                  style={{
                    fontSize: 14,
                    color: "var(--pq-ivory)",
                  }}
                >
                  Last export
                </div>
                <div
                  className="font-mono"
                  style={{
                    fontVariantNumeric: "tabular-nums",
                    fontSize: 12.5,
                    color: "rgba(245,240,232,0.40)",
                    marginTop: 2,
                  }}
                >
                  {lastExport.at}
                  {lastExport.size ? <> · {lastExport.size}</> : null}
                </div>
              </div>
            </div>
          ) : null}

          <button
            type="button"
            onClick={onRequestExport}
            className="font-mono uppercase"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 22px",
              background: "var(--pq-bronze)",
              color: "var(--pq-ink, #050505)",
              fontSize: 11,
              letterSpacing: "0.2em",
              borderRadius: 2,
              border: "none",
              cursor: "pointer",
              marginTop: 12,
            }}
          >
            Request new export →
          </button>
          <p
            className="font-serif"
            style={{
              fontSize: 11.5,
              color: "rgba(245,240,232,0.40)",
              marginTop: 12,
            }}
          >
            Email delivery within{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
              }}
            >
              24 h
            </span>
            . Includes Companion archive on Premium.
          </p>
        </div>
      </div>

      {/* E3 — Danger zone */}
      <div
        style={{
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${ERROR_BORDER}`,
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
            color: ERROR_COLOR,
          }}
        >
          E3 · Danger zone
        </span>
        <div
          className="font-mono uppercase"
          style={{
            fontSize: 10.5,
            letterSpacing: "0.22em",
            color: ERROR_COLOR,
            marginBottom: 16,
          }}
        >
          Account deletion · PIPA Art. 36
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 24,
          }}
          className="pq-danger-grid"
        >
          <div>
            <div
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: 22,
                lineHeight: 1.2,
                color: "var(--pq-ivory)",
                marginBottom: 12,
                letterSpacing: "-0.02em",
              }}
            >
              Sign out
            </div>
            <p
              className="font-serif"
              style={{
                fontSize: 13,
                lineHeight: 1.55,
                color: "rgba(245,240,232,0.82)",
                marginBottom: 16,
              }}
            >
              Ends this browser session. Your data is preserved.
            </p>
            <button
              type="button"
              onClick={onSignOut}
              disabled={signingOut}
              className="font-mono uppercase"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "11px 20px",
                background: "transparent",
                color: "var(--pq-bronze)",
                border: "1px solid var(--pq-bronze)",
                fontSize: 11,
                letterSpacing: "0.2em",
                borderRadius: 2,
                cursor: signingOut ? "not-allowed" : "pointer",
                opacity: signingOut ? 0.5 : 1,
              }}
            >
              {signingOut ? "Signing out…" : "Sign out →"}
            </button>
          </div>

          <div>
            <div
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: 22,
                lineHeight: 1.2,
                color: "var(--pq-ivory)",
                marginBottom: 12,
                letterSpacing: "-0.02em",
              }}
            >
              Delete account
            </div>
            <p
              className="font-serif"
              style={{
                fontSize: 13,
                lineHeight: 1.55,
                color: "rgba(245,240,232,0.82)",
                marginBottom: 16,
              }}
            >
              Permanent. Removes positions, watchlists, persona snapshots,
              and delivered artifacts. PIPA · 30-day purge after request.
            </p>
            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="font-mono uppercase"
              style={{
                fontSize: 11,
                letterSpacing: "0.18em",
                color: ERROR_COLOR,
                borderBottom: `1px solid ${ERROR_LINK_BORDER}`,
                paddingBottom: 2,
                background: "transparent",
                border: "none",
                borderBottomStyle: "solid",
                cursor: "pointer",
              }}
            >
              Contact support to delete
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        @media (max-width: 1023px) {
          :global(.pq-privacy-grid),
          :global(.pq-danger-grid) {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>

      {showDelete ? (
        <DeleteAccountModal
          onClose={() => setShowDelete(false)}
          mailto={deleteAccountMailto}
        />
      ) : null}
    </section>
  );
}

export default PrivacyCardV2;
