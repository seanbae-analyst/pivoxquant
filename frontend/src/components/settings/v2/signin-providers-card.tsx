"use client";

/**
 * <SignInProvidersCard />
 *
 * Section A2 of /settings v2 — Sign-in (OAuth providers).
 * Mirror of settings-v2 mockup §577 ("A2 · Sign-in").
 *
 * Renders three rows:
 *   - Google      (Linked / Not linked → Disconnect or Connect link)
 *   - Kakao       (Linked / Not linked → Disconnect or Connect link)
 *   - Password    (always "N/A — OAuth-only" — GAP-L · v3-OAuth-pure stays)
 *
 * Helper line warns the user that disconnecting the last provider locks the
 * account.
 *
 * GAP-D: backend `POST /api/auth/<provider>/disconnect` endpoint absent.
 *        UI surfaces the action; host wires a graceful error toast until the
 *        endpoint lands. See settings-v2/MIGRATION.md §2.
 *
 * Pure presentational. Host wires `useAuth()` for the linked provider name.
 *
 * Legal: persona vocabulary only. No advice strings.
 */

import * as React from "react";

interface Props {
  /** "google" | "kakao" | null — the provider currently linked. */
  oauthProvider?: string | null;
  /** Email of the linked Google identity (used in the helper line). */
  email?: string | null;
  onDisconnect?: (provider: "google" | "kakao") => void;
  onConnect?: (provider: "google" | "kakao") => void;
}

const ROW_LABEL_STYLE: React.CSSProperties = {
  fontSize: 14,
  color: "var(--pq-ivory)",
};
const ROW_HELP_STYLE: React.CSSProperties = {
  fontSize: 14,
  color: "rgba(245,240,232,0.40)",
  marginTop: 2,
};

const PILL_LINKED: React.CSSProperties = {
  display: "inline-block",
  padding: "2px 8px",
  fontSize: 12,
  letterSpacing: "0.18em",
  textTransform: "uppercase",
  border: "1px solid rgba(184,149,106,0.15)",
  color: "var(--pq-bronze)",
  borderRadius: 2,
  marginLeft: 6,
};
const PILL_DIM: React.CSSProperties = {
  ...PILL_LINKED,
  border: "1px solid rgba(245,240,232,0.14)",
  color: "rgba(245,240,232,0.40)",
};

function ProviderRow({
  name,
  linked,
  emailHint,
  helpUnlinked,
  onConnect,
  onDisconnect,
  topPad,
}: {
  name: "Google" | "Kakao";
  linked: boolean;
  emailHint?: string | null;
  helpUnlinked: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  topPad?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 14,
        padding: topPad ? "14px 0" : "0 0 14px",
        borderTop: topPad ? "1px solid rgba(245,240,232,0.08)" : undefined,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div className="font-serif" style={ROW_LABEL_STYLE}>
          {name}{" "}
          <span
            className="font-mono"
            style={linked ? PILL_LINKED : PILL_DIM}
            aria-label={linked ? "Linked" : "Not linked"}
          >
            {linked ? "Linked" : "Not linked"}
          </span>
        </div>
        <div className="font-serif" style={ROW_HELP_STYLE}>
          {linked
            ? `${emailHint ?? "Connected"} · primary login.`
            : helpUnlinked}
        </div>
      </div>

      {linked ? (
        <button
          type="button"
          onClick={onDisconnect}
          className="font-mono uppercase"
          style={{
            fontSize: 10,
            letterSpacing: "0.18em",
            color: "var(--pq-error, #d18888)",
            borderBottom: "1px solid rgba(209,136,136,0.30)",
            paddingBottom: 2,
            background: "transparent",
            border: "none",
            borderBottomStyle: "solid",
            cursor: "pointer",
          }}
        >
          Disconnect
        </button>
      ) : (
        <button
          type="button"
          onClick={onConnect}
          className="font-mono uppercase"
          style={{
            fontSize: 10,
            letterSpacing: "0.18em",
            color: "var(--pq-bronze)",
            borderBottom: "1px solid rgba(184,149,106,0.15)",
            paddingBottom: 2,
            background: "transparent",
            border: "none",
            borderBottomStyle: "solid",
            cursor: "pointer",
          }}
        >
          Connect {name}
        </button>
      )}
    </div>
  );
}

export function SignInProvidersCard({
  oauthProvider,
  email,
  onDisconnect,
  onConnect,
}: Props) {
  const googleLinked = oauthProvider === "google";
  const kakaoLinked = oauthProvider === "kakao";

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
          fontSize: 12,
          letterSpacing: "0.2em",
          color: "rgba(245,240,232,0.40)",
        }}
      >
        A2 · Sign-in
      </span>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: 12,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 16,
        }}
      >
        How you authenticate
      </div>

      <ProviderRow
        name="Google"
        linked={googleLinked}
        emailHint={googleLinked ? email : null}
        helpUnlinked="Add Google as a sign-in method."
        onConnect={() => onConnect?.("google")}
        onDisconnect={() => onDisconnect?.("google")}
      />

      <ProviderRow
        name="Kakao"
        linked={kakaoLinked}
        emailHint={kakaoLinked ? email : null}
        helpUnlinked="Add Kakao as a backup sign-in method."
        onConnect={() => onConnect?.("kakao")}
        onDisconnect={() => onDisconnect?.("kakao")}
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
          borderTop: "1px solid rgba(245,240,232,0.08)",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div className="font-serif" style={ROW_LABEL_STYLE}>Password</div>
          <div className="font-serif" style={ROW_HELP_STYLE}>
            OAuth-only — no password set on this account.
          </div>
        </div>
        <span
          className="font-mono uppercase"
          style={{
            fontSize: 12,
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.40)",
          }}
        >
          N/A
        </span>
      </div>

      <p
        className="font-serif"
        style={{
          fontSize: 14,
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.40)",
          marginTop: 12,
        }}
      >
        At least one OAuth provider must remain connected. Disconnecting your
        last provider locks the account.
      </p>
    </div>
  );
}

export default SignInProvidersCard;
