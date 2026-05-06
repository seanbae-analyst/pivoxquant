"use client";

/**
 * <OAuthButtonsV2 />
 *
 * Vantablack-tone OAuth button stack used by /login v2 and /signup v2.
 *
 * IMPORTANT — function preservation:
 * The OAuth handler contract is unchanged from v1:
 *   - The Google + Kakao anchors point at the same `API.auth.google` /
 *     `API.auth.kakao` URLs.
 *   - The optional `onGoogleClick` / `onKakaoClick` props let the signup
 *     page intercept the click for legal-consent gating + localStorage
 *     persistence (matches v1 `handleOAuthClick` semantics 1:1).
 *   - `disabled=true` collapses the anchors into <button disabled> just
 *     like v1, so the legal gate works identically.
 *
 * Visual layer only:
 *   - Vantablack background, ivory text, bronze hairline border.
 *   - Hover: bronze border + subtle ink lift.
 *   - Mono uppercase label ("CONTINUE WITH GOOGLE / KAKAO").
 */

import * as React from "react";
import { API } from "@/lib/endpoints";

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A11.96 11.96 0 0 0 1 12c0 1.94.46 3.77 1.18 5.07l3.66-2.98z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

function KakaoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3C6.48 3 2 6.58 2 10.94c0 2.8 1.86 5.27 4.66 6.67-.15.53-.96 3.41-.99 3.63 0 0-.02.16.08.22.1.06.23.01.23.01.3-.04 3.5-2.3 4.05-2.67.62.09 1.27.14 1.97.14 5.52 0 10-3.58 10-7.94S17.52 3 12 3z"
        fill="var(--pq-ivory, #F5F0E8)"
      />
    </svg>
  );
}

interface OAuthButtonsV2Props {
  /** When false, collapses anchors to disabled buttons (legal gate). */
  disabled?: boolean;
  /** Optional click handler for Google — runs alongside default href navigation. */
  onGoogleClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
  /** Optional click handler for Kakao — runs alongside default href navigation. */
  onKakaoClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
  /** Optional callback fired when a disabled button is clicked (so the parent
   *  can pulse-highlight unchecked consent rows). */
  onDisabledClick?: () => void;
  /** Visual variant for the disabled-state hint copy below buttons. */
  hint?: string;
  /** When true, the hint is rendered with an alert role + warning tone. */
  hintEmphasized?: boolean;
}

const buttonShellBase: React.CSSProperties = {
  display: "flex",
  width: "100%",
  alignItems: "center",
  justifyContent: "center",
  gap: 14,
  padding: "14px 20px",
  borderRadius: 2,
  fontSize: 11,
  letterSpacing: "0.22em",
  textTransform: "uppercase",
  textDecoration: "none",
  transition:
    "border-color 200ms cubic-bezier(0.16,1,0.3,1), background-color 200ms cubic-bezier(0.16,1,0.3,1), color 200ms",
};

export function OAuthButtonsV2({
  disabled = false,
  onGoogleClick,
  onKakaoClick,
  onDisabledClick,
  hint,
  hintEmphasized = false,
}: OAuthButtonsV2Props) {
  const enabledShell: React.CSSProperties = {
    ...buttonShellBase,
    border: "1px solid rgba(184,149,106,0.30)",
    background: "rgba(245,240,232,0.02)",
    color: "var(--pq-ivory, #F5F0E8)",
    cursor: "pointer",
  };

  const disabledShell: React.CSSProperties = {
    ...buttonShellBase,
    border: "1px solid rgba(245,240,232,0.06)",
    background: "transparent",
    color: "rgba(245,240,232,0.30)",
    cursor: "not-allowed",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, width: "100%" }}>
      {disabled ? (
        <button
          type="button"
          aria-disabled="true"
          onClick={onDisabledClick}
          className="font-mono"
          style={disabledShell}
        >
          <GoogleIcon />
          Continue with Google
        </button>
      ) : (
        <a
          href={API.auth.google}
          onClick={onGoogleClick}
          className="pq-auth-oauth-btn pq-auth-oauth-btn--google font-mono"
          style={enabledShell}
        >
          <GoogleIcon />
          Continue with Google
        </a>
      )}

      {disabled ? (
        <button
          type="button"
          aria-disabled="true"
          onClick={onDisabledClick}
          className="font-mono"
          style={disabledShell}
        >
          <KakaoIcon />
          Continue with Kakao
        </button>
      ) : (
        <a
          href={API.auth.kakao}
          onClick={onKakaoClick}
          className="pq-auth-oauth-btn pq-auth-oauth-btn--kakao font-mono"
          style={enabledShell}
        >
          <KakaoIcon />
          Continue with Kakao
        </a>
      )}

      {disabled && hint ? (
        <p
          className="font-mono uppercase"
          role={hintEmphasized ? "alert" : undefined}
          style={{
            marginTop: 6,
            fontSize: 10,
            letterSpacing: "0.18em",
            color: hintEmphasized
              ? "rgba(244,108,108,0.95)"
              : "rgba(245,240,232,0.40)",
            textAlign: "center",
            textTransform: "uppercase",
          }}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export default OAuthButtonsV2;
