"use client";

/**
 * <AuthHeroV2 />
 *
 * Editorial hero shared by /login v2 and /signup v2.
 *
 * Visual rules (v3 lock-in):
 * - Vantablack background (#050505) — applied by parent route layout.
 * - Bronze ruled kicker (PIVOXQUANT · ENTRY).
 * - Playfair Display H1 with bronze italic accent words via <span class="br">.
 * - Source Serif 4 deck line — one sentence chapeau.
 * - JetBrains Mono uppercase signature on hairline.
 *
 * Pure presentational; no auth state, no data fetching. Caller passes
 * eyebrow / headlineHtml / deck content. Mirrors today-memo-hero-v2 grammar.
 */

import * as React from "react";
import { renderEditorialHeadline } from "@/lib/editorial-html";

interface AuthHeroV2Props {
  /** Mono uppercase eyebrow line, e.g. "PIVOXQUANT · ENTRY". */
  eyebrow: string;
  /**
   * H1 line. May contain <span class="br">…</span> markup for bronze italic
   * accents — same convention as TodayMemoHeroV2. Caller is responsible for
   * not passing user-generated content (CSP-safe within app trust boundary).
   */
  headlineHtml: string;
  /** Optional serif deck — one-sentence chapeau under the H1. */
  deck?: string;
  /** Optional hairline signature, mono uppercase. */
  signature?: string;
}

export function AuthHeroV2({
  eyebrow,
  headlineHtml,
  deck,
  signature,
}: AuthHeroV2Props) {
  return (
    <section
      className="pq-auth-hero-v2"
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        height: "100%",
        padding: "64px 56px",
        maxWidth: 640,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: 10.5,
          letterSpacing: "0.24em",
          color: "var(--pq-bronze, #B8956A)",
          marginBottom: 28,
          textTransform: "uppercase",
        }}
      >
        {eyebrow}
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(32px, 4.2vw, 48px)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "0 0 28px 0",
        }}
      >
        {/* Strict tag allowlist — see lib/editorial-html. */}
        {renderEditorialHeadline(headlineHtml)}
      </h1>

      {deck ? (
        <p
          className="font-serif"
          style={{
            fontSize: 17,
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.72)",
            maxWidth: 480,
            margin: "0 0 40px 0",
          }}
        >
          {deck}
        </p>
      ) : null}

      {signature ? (
        <div
          className="font-mono uppercase"
          style={{
            fontSize: 10.5,
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.40)",
            paddingTop: 24,
            borderTop: "0.5px solid rgba(245,240,232,0.08)",
            textTransform: "uppercase",
          }}
        >
          {signature}
        </div>
      ) : null}
    </section>
  );
}

export default AuthHeroV2;
