"use client";

/**
 * <IdentityCardV2 />
 *
 * Block 1 of /profile v2 — 4-col identity card.
 * Mirror of mockup §390 (`Identity card · 01`).
 *
 * Renders:
 *   - 96×96 bronze-ring monogram avatar (initials)
 *   - Name (Playfair 22px), email (mono small)
 *   - PRO/Premium pill + OAuth provider eyebrow
 *   - Investor-type hairline-separated section: "Risk-managed Growth" + last calibrated date
 *
 * Pure presentational. Host wires useAuth + useInvestmentProfile.
 */

import * as React from "react";

const INVESTOR_TYPE_LABELS: Record<string, string> = {
  passive_index_hugger: "Passive index",
  steady_accumulator: "Steady accumulator",
  value_hunter: "Value hunter",
  risk_managed_growth: "Risk-managed Growth",
  swing_trader: "Swing trader",
  momentum_rider: "Momentum rider",
  macro_rotator: "Macro rotator",
  aggressive_scalper: "Aggressive scalper",
};

function initials(name?: string | null, email?: string | null): string {
  if (name) {
    return name
      .split(/\s+/)
      .map((w) => w[0] ?? "")
      .join("")
      .slice(0, 2)
      .toUpperCase();
  }
  if (email) return email.slice(0, 2).toUpperCase();
  return "PQ";
}

interface IdentityCardV2Props {
  name?: string | null;
  email?: string | null;
  tierLabel: string;
  oauthProvider?: string | null;
  investorType?: string | null;
  /** ISO date string of last calibration. */
  calibratedAt?: string | null;
}

export function IdentityCardV2({
  name,
  email,
  tierLabel,
  oauthProvider,
  investorType,
  calibratedAt,
}: IdentityCardV2Props) {
  const init = initials(name, email);
  const investorLabel = investorType
    ? INVESTOR_TYPE_LABELS[investorType] ?? investorType
    : "Not set";
  const calibratedDisplay = calibratedAt
    ? new Date(calibratedAt).toLocaleDateString("en-US", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : null;

  return (
    <div
      className="pq-card"
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(245,240,232,0.08)",
        borderRadius: 4,
        padding: 24,
        minHeight: 320,
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
          textTransform: "uppercase",
        }}
      >
        Edit ›
      </span>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: 10.5,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 20,
        }}
      >
        01 · Identity
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 20,
          marginBottom: 24,
        }}
      >
        <div
          aria-hidden
          style={{
            width: 96,
            height: 96,
            border: "1px solid var(--pq-bronze)",
            color: "var(--pq-bronze)",
            fontSize: 28,
            letterSpacing: "0.04em",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 999,
            flexShrink: 0,
          }}
        className="font-mono" >
          {init}
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: 22,
              lineHeight: 1.15,
              color: "var(--pq-ivory)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {name || "Unnamed"}
          </div>
          <div
            className="font-mono"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: 11.5,
              color: "rgba(245,240,232,0.55)",
              marginTop: 4,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {email}
          </div>
          <div
            style={{
              marginTop: 12,
              display: "flex",
              alignItems: "center",
              gap: 8,
              flexWrap: "wrap",
            }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 10.5,
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
                border: "1px solid var(--pq-bronze)",
                padding: "2px 8px",
                textTransform: "uppercase",
              }}
            >
              {tierLabel}
            </span>
            {oauthProvider ? (
              <span
                className="font-mono uppercase"
                style={{
                  fontSize: 10.5,
                  letterSpacing: "0.22em",
                  color: "rgba(245,240,232,0.40)",
                  textTransform: "uppercase",
                }}
              >
                via {oauthProvider === "kakao" ? "Kakao" : oauthProvider}
              </span>
            ) : null}
          </div>
        </div>
      </div>

      <div
        style={{
          borderTop: "1px solid rgba(245,240,232,0.08)",
          paddingTop: 14,
        }}
      >
        <div
          className="font-mono uppercase"
          style={{
            fontSize: 10.5,
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.40)",
            marginBottom: 8,
          }}
        >
          Investor type · 20-Q calibration
        </div>
        <div
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: 18,
            lineHeight: 1.2,
            color: "var(--pq-ivory)",
          }}
        >
          {investorLabel}
        </div>
        <p
          className="font-serif"
          style={{
            fontSize: 13,
            lineHeight: 1.5,
            color: "rgba(245,240,232,0.65)",
            marginTop: 8,
          }}
        >
          {calibratedDisplay ? (
            <>
              Last calibrated{" "}
              <span
                style={{
                  fontVariantNumeric: "tabular-nums",
                }}
              className="font-mono" >
                {calibratedDisplay}.
              </span>{" "}
              Recalibrate after material life events or every six months.
            </>
          ) : (
            <>
              Take the 20-question assessment to calibrate every analytical
              surface to your declared persona.
            </>
          )}
        </p>
      </div>
    </div>
  );
}

export default IdentityCardV2;
