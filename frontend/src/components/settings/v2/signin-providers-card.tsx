"use client";

/**
 * <SignInProvidersCard />
 *
 * Section A2 of /settings v2 — Sign-in (OAuth providers).
 * Mirror of settings-v2 mockup §577 ("A2 · Sign-in").
 *
 * Renders three rows:
 *   - Google      (Linked → "Primary" / Not linked → Connect link)
 *   - Kakao       (Linked → "Primary" / Not linked → Connect link)
 *   - Password    (always "N/A — OAuth-only" — GAP-L · v3-OAuth-pure stays)
 *
 * 2026-09-10: the Disconnect button was removed. There is no backend
 * disconnect endpoint, so it could only toast "not supported". Add it back
 * together with the endpoint, and with the last-provider lockout guard.
 *
 * Pure presentational. Host wires `useAuth()` for the linked provider name.
 *
 * Legal: persona vocabulary only. No advice strings.
 */

import * as React from "react";
import { useT } from "@/lib/locale";

interface Props {
  /** "google" | "kakao" | null — the provider currently linked. */
  oauthProvider?: string | null;
  /** Email of the linked Google identity (used in the helper line). */
  email?: string | null;
  onConnect?: (provider: "google" | "kakao") => void;
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

const PILL_LINKED: React.CSSProperties = {
  display: "inline-block",
  padding: "2px 8px",
  fontSize: "var(--pq-text-eyebrow)",
  border: "1px solid rgba(184,149,106,0.15)",
  color: "var(--pq-bronze)",
  borderRadius: 2,
  marginLeft: 6,
};
const PILL_DIM: React.CSSProperties = {
  ...PILL_LINKED,
  border: "1px solid rgba(245,240,232,0.14)",
  color: "var(--pq-ivory-dim)",
};

function ProviderRow({
  name,
  linked,
  emailHint,
  helpUnlinked,
  onConnect,
  topPad,
}: {
  name: "Google" | "Kakao";
  linked: boolean;
  emailHint?: string | null;
  helpUnlinked: string;
  onConnect?: () => void;
  topPad?: boolean;
}) {
  const t = useT();
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 14,
        padding: topPad ? "14px 0" : "0 0 14px",
        borderTop: topPad ? "1px solid var(--pq-ivory-line)" : undefined,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div className="font-serif" style={ROW_LABEL_STYLE}>
          {name}{" "}
          <span
            className="font-mono"
            style={linked ? PILL_LINKED : PILL_DIM}
            aria-label={linked ? "연결됨" : "연결 안 됨"}
          >
            {linked ? "연결됨" : "연결 안 됨"}
          </span>
        </div>
        <div className="font-serif" style={ROW_HELP_STYLE}>
          {linked
            ? t("settingsV2.signin.linkedHelp", {
                who: emailHint ?? t("settingsV2.signin.connected"),
              })
            : helpUnlinked}
        </div>
      </div>

      {linked ? (
        <span
          className="font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-ivory-dim)",
          }}
        >
          기본
        </span>
      ) : (
        <button
          type="button"
          onClick={onConnect}
          className="font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-bronze)",
            borderBottom: "1px solid rgba(184,149,106,0.15)",
            paddingBottom: 2,
            background: "transparent",
            border: "none",
            borderBottomStyle: "solid",
            cursor: "pointer",
          }}
        >
          {name} 연결
        </button>
      )}
    </div>
  );
}

export function SignInProvidersCard({
  oauthProvider,
  email,
  onConnect,
}: Props) {
  const t = useT();
  const googleLinked = oauthProvider === "google";
  const kakaoLinked = oauthProvider === "kakao";

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
        className="font-mono"
        style={{
          position: "absolute",
          top: 14,
          right: 14,
          fontSize: "var(--pq-text-eyebrow)",
          color: "var(--pq-ivory-dim)",
        }}
      >
        로그인
      </span>

      <div
        className="font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          color: "var(--pq-bronze)",
          marginBottom: 16,
        }}
      >
        로그인 수단
      </div>

      <ProviderRow
        name="Google"
        linked={googleLinked}
        emailHint={googleLinked ? email : null}
        helpUnlinked={t("settingsV2.signin.googleUnlinked")}
        onConnect={() => onConnect?.("google")}
      />

      <ProviderRow
        name="Kakao"
        linked={kakaoLinked}
        emailHint={kakaoLinked ? email : null}
        helpUnlinked={t("settingsV2.signin.kakaoUnlinked")}
        onConnect={() => onConnect?.("kakao")}
        topPad
      />

      {/* Password row — always N/A · OAuth-only stance (GAP-L) */}
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
          <div className="font-serif" style={ROW_LABEL_STYLE}>비밀번호</div>
          <div className="font-serif" style={ROW_HELP_STYLE}>
            {t("settingsV2.signin.passwordHelp")}
          </div>
        </div>
        <span
          className="font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-ivory-dim)",
          }}
        >
          없음
        </span>
      </div>
    </div>
  );
}

export default SignInProvidersCard;
