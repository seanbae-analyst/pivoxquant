"use client";

/**
 * <AuthLinkV2 />
 *
 * Bronze-accented switch link used at the foot of /login v2 and /signup v2.
 *
 *   "계정이 없으신가요?  회원가입 ›"   (login → /signup)
 *   "이미 계정이 있으신가요?  로그인 ›"  (signup → /login)
 *
 * Pure presentational. Uses next/link so client routing is preserved.
 */

import * as React from "react";
import Link from "next/link";

interface AuthLinkV2Props {
  /** Short prompt sentence, ivory muted. */
  prompt: string;
  /** Action label, bronze. */
  action: string;
  /** Destination href, e.g. "/signup". */
  href: string;
}

export function AuthLinkV2({ prompt, action, href }: AuthLinkV2Props) {
  return (
    <p
      className="font-serif"
      style={{
        fontSize: "var(--pq-text-body)",
        lineHeight: 1.5,
        color: "rgba(245,240,232,0.55)",
        textAlign: "center",
      }}
    >
      {prompt}{" "}
      <Link
        href={href}
        className="pq-auth-link-v2 font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.20em",
          textTransform: "uppercase",
          color: "var(--pq-bronze, #B8956A)",
          borderBottom: "1px solid rgba(184,149,106,0.35)",
          paddingBottom: 1,
          marginLeft: 8,
          textDecoration: "none",
        }}
      >
        {action} ›
      </Link>
    </p>
  );
}

export default AuthLinkV2;
