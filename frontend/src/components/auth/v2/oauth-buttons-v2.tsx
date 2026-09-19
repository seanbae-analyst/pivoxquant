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
 * Cold-start gate (2026-09-19):
 *   The backend sleeps after 15 idle minutes (Render free plan). Because
 *   these are anchors, a click on a sleeping backend was a full-page
 *   navigation into Render's own unbranded 502 — off our site, no
 *   explanation, nothing to retry. So:
 *     - a single `/api/health` probe fires on mount, which starts the boot
 *       while the visitor reads the page;
 *     - if the backend has already answered 200, the click navigates exactly
 *       as before (no added latency on the normal path);
 *     - otherwise the click is held, a Korean waiting state is announced, and
 *       we navigate the moment health returns 200;
 *     - past the deadline we show our own error + retry instead of Render's.
 *   The `href` stays on the anchor throughout: with JS dead the link still
 *   works, exactly as it did before.
 *
 * Visual layer only:
 *   - Vantablack background, ivory text, bronze hairline border.
 *   - Hover: bronze border + subtle ink lift.
 *   - Mono uppercase label ("CONTINUE WITH GOOGLE / KAKAO").
 */

import * as React from "react";
import { API } from "@/lib/endpoints";
import { useT } from "@/lib/locale";
import { isDemoMode } from "@/lib/demo";
import { useBackendWake } from "@/lib/backend-wake";
import { GoogleIcon, KakaoIcon } from "./oauth-provider-icons";

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

type Provider = "google" | "kakao";

const buttonShellBase: React.CSSProperties = {
  display: "flex",
  width: "100%",
  alignItems: "center",
  justifyContent: "center",
  gap: 14,
  padding: "14px 20px",
  borderRadius: 2,
  fontSize: "var(--pq-text-eyebrow)",
  letterSpacing: "0.22em",
  textTransform: "uppercase",
  textDecoration: "none",
  transition:
    "border-color 200ms cubic-bezier(0.16,1,0.3,1), background-color 200ms cubic-bezier(0.16,1,0.3,1), color 200ms",
};

const noteBase: React.CSSProperties = {
  marginTop: 6,
  fontSize: "var(--pq-text-eyebrow)",
  letterSpacing: "0.18em",
  textAlign: "center",
  textTransform: "uppercase",
  lineHeight: 1.6,
};

/** A modified click (new tab / new window) must stay the browser's business. */
function isModifiedClick(e: React.MouseEvent): boolean {
  return e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0;
}

export function OAuthButtonsV2({
  disabled = false,
  onGoogleClick,
  onKakaoClick,
  onDisabledClick,
  hint,
  hintEmphasized = false,
}: OAuthButtonsV2Props) {
  const t = useT();
  // Demo mode never reaches a backend (lib/demo.ts serves fixtures), so the
  // probe would poll a server that is not there. Leave the anchors untouched:
  // no probe, and no click interception either.
  const gateEnabled = !isDemoMode();
  const backend = useBackendWake({ enabled: gateEnabled });
  const [target, setTarget] = React.useState<{ provider: Provider; href: string } | null>(null);
  const [busy, setBusy] = React.useState(false);

  const enabledShell: React.CSSProperties = {
    ...buttonShellBase,
    border: "1px solid rgba(184,149,106,0.30)",
    background: "var(--pq-ivory-line-ghost)",
    color: "var(--pq-ivory, #F5F0E8)",
    cursor: busy ? "progress" : "pointer",
  };

  const disabledShell: React.CSSProperties = {
    ...buttonShellBase,
    border: "1px solid var(--pq-ivory-line-soft)",
    background: "transparent",
    color: "var(--pq-ivory-dim)",
    cursor: "not-allowed",
  };

  const runWake = React.useCallback(
    async (provider: Provider, href: string) => {
      setTarget({ provider, href });
      setBusy(true);
      const awake = await backend.wake();
      if (!awake) {
        // `backend.status` is now "failed" — render our own error, not Render's.
        setBusy(false);
        return;
      }
      // Stay busy through the navigation: the page is on its way out.
      window.location.assign(href);
    },
    [backend],
  );

  const handleClick = (provider: Provider, href: string) =>
    (e: React.MouseEvent<HTMLAnchorElement>) => {
      const parentHandler = provider === "google" ? onGoogleClick : onKakaoClick;
      parentHandler?.(e);
      // A parent gate (legal consent) that cancelled the click wins outright.
      if (e.defaultPrevented) return;
      if (isModifiedClick(e)) return;
      // Warm backend (or no backend to warm) → behave exactly as before and
      // let the anchor navigate on its own.
      if (!gateEnabled || backend.isReady) return;
      e.preventDefault();
      if (busy) return;
      void runWake(provider, href);
    };

  const retry = () => {
    if (!target || busy) return;
    backend.reset();
    void runWake(target.provider, target.href);
  };

  function providerButton(provider: Provider) {
    const isGoogle = provider === "google";
    const href = isGoogle ? API.auth.google : API.auth.kakao;
    const label = t(
      isGoogle ? "auth.login.continueWithGoogle" : "auth.login.continueWithKakao",
    );
    const icon = isGoogle ? <GoogleIcon /> : <KakaoIcon />;

    if (disabled) {
      return (
        <button
          type="button"
          aria-disabled="true"
          onClick={onDisabledClick}
          className="font-mono"
          style={disabledShell}
        >
          {icon}
          {label}
        </button>
      );
    }

    const isTarget = target?.provider === provider;
    return (
      <a
        href={href}
        onClick={handleClick(provider, href)}
        // Kept focusable and kept its href on purpose: without JS the link
        // still works, and a screen reader still reaches it while we wait.
        aria-disabled={busy ? "true" : undefined}
        aria-busy={busy && isTarget ? "true" : undefined}
        className={`pq-auth-oauth-btn pq-auth-oauth-btn--${provider} font-mono`}
        style={enabledShell}
      >
        {icon}
        {label}
      </a>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, width: "100%" }}>
      {providerButton("google")}
      {providerButton("kakao")}

      {/* Waking state. The live region is always mounted — a region inserted
          at the same moment as its text is announced unreliably — but while
          idle it is `sr-only`, i.e. position:absolute, so it is not a flex
          item and adds no gap to the card. */}
      <p
        className={busy ? "font-mono uppercase" : "sr-only"}
        aria-live="polite"
        style={busy ? { ...noteBase, color: "var(--pq-ivory-dim)" } : undefined}
      >
        {busy ? t("auth.login.waking") : ""}
      </p>

      {!busy && backend.status === "failed" && target ? (
        <div
          role="alert"
          style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}
        >
          <p
            className="font-mono uppercase"
            style={{ ...noteBase, color: "var(--pq-negative, #d18888)" }}
          >
            {t("auth.login.wakeFailed")}
          </p>
          <button
            type="button"
            onClick={retry}
            className="font-mono uppercase"
            style={{
              padding: "8px 18px",
              borderRadius: 2,
              border: "1px solid rgba(184,149,106,0.45)",
              background: "transparent",
              color: "var(--pq-bronze, #B8956A)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              cursor: "pointer",
            }}
          >
            {t("auth.login.wakeRetry")}
          </button>
        </div>
      ) : null}

      {disabled && hint ? (
        <p
          className="font-mono uppercase"
          role={hintEmphasized ? "alert" : undefined}
          style={{
            ...noteBase,
            color: hintEmphasized
              ? "rgba(244,108,108,0.95)"
              : "rgba(245,240,232,0.55)",
          }}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export default OAuthButtonsV2;
