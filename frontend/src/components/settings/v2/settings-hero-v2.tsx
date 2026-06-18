"use client";

/**
 * <SettingsHeroV2 /> — editorial hero for /settings v2.
 *
 * Mirrors the home-v2 / risk-v2 hero rhythm: 80/64 padding, hairline-bottom,
 * Playfair 500 / 48px H1 with bronze italic accents, Source Serif deck.
 *
 * Surface only — observation-language, no advice/recommend strings.
 */

import * as React from "react";

interface Props {
  eyebrow?: string;
}

export function SettingsHeroV2({
  eyebrow = "Operations · Brokers · Subscription · Privacy",
}: Props) {
  return (
    <section
      style={{
        padding: "80px 0 48px",
        borderBottom: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 28,
        }}
      >
        {eyebrow}
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "var(--pq-text-hero-num)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          maxWidth: 940,
          margin: "0 0 28px 0",
        }}
      >
        The dials that run{" "}
        <span style={{ color: "var(--pq-bronze)" }}>
          your CFO room.
        </span>
        <br />
        Adjusted by you,{" "}
        <span style={{ color: "var(--pq-bronze)" }}>
          remembered by us.
        </span>
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-h5)",
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          margin: "0 0 40px 0",
        }}
      >
        Identity and persona live on{" "}
        <a
          href="/profile"
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            color: "var(--pq-bronze)",
            borderBottom: "1px solid rgba(184,149,106,0.15)",
            paddingBottom: 2,
            textDecoration: "none",
          }}
        >
          Profile ›
        </a>
        . Settings is for the operational levers — how you sign in, which
        brokers stream, which artifacts arrive in your inbox, and how you
        exercise your{" "}
        <span style={{ color: "var(--pq-bronze)" }}>
          data rights.
        </span>
      </p>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <a
          href="#section-d"
          className="font-mono uppercase"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 22px",
            background: "var(--pq-bronze)",
            color: "var(--pq-ink, #050505)",
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.2em",
            borderRadius: 2,
            textDecoration: "none",
          }}
        >
          Manage subscription →
        </a>
        <a
          href="#section-b"
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            color: "var(--pq-bronze)",
            borderBottom: "1px solid rgba(184,149,106,0.15)",
            paddingBottom: 2,
            textDecoration: "none",
          }}
        >
          Connect a broker
        </a>
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.55)",
            marginLeft: 8,
          }}
        >
          Drafted by AI · Reviewed by you
        </span>
      </div>
    </section>
  );
}

export default SettingsHeroV2;
