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
import { useT, useLocale } from "@/lib/locale";

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
  const t = useT();
  const { locale } = useLocale();
  const init = initials(name, email);
  const investorLabel = investorType
    ? t(`persona.names.${investorType}`)
    : locale === "ko" ? "미설정" : "Not set";
  const calibratedDisplay = calibratedAt
    ? new Date(calibratedAt).toLocaleDateString(locale === "ko" ? "ko-KR" : "en-US", {
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
        border: "1px solid var(--pq-ivory-line)",
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
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.2em",
          color: "rgba(245,240,232,0.55)",
          textTransform: "uppercase",
        }}
      >
        Edit ›
      </span>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
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
            fontSize: "var(--pq-text-avatar)",
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
              fontSize: "var(--pq-text-quote)",
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
              fontSize: "var(--pq-text-eyebrow)",
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
                fontSize: "var(--pq-text-eyebrow)",
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
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.22em",
                  color: "rgba(245,240,232,0.55)",
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
          borderTop: "1px solid var(--pq-ivory-line)",
          paddingTop: 14,
        }}
      >
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.55)",
            marginBottom: 8,
          }}
        >
          Investor type · 20-Q calibration
        </div>
        <div
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: "var(--pq-text-h5)",
            lineHeight: 1.2,
            color: "var(--pq-ivory)",
          }}
        >
          {investorLabel}
        </div>
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
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
