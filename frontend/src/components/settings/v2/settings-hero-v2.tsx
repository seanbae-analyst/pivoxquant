"use client";

/**
 * <SettingsHeroV2 /> — editorial hero for /settings v2.
 *
 * Mirrors the home-v2 / risk-v2 hero rhythm: 80/64 padding, hairline-bottom,
 * Playfair 500 / 48px H1 with bronze accents (upright), Source Serif deck.
 *
 * 2026-09-19: the H1 and deck were hardcoded English while every section
 * heading below them was already Korean. Both now read from settingsV2.hero
 * via useT; the eyebrow stays English (EN mono eyebrow is the house rule).
 *
 * Surface only — observation-language, no advice/recommend strings.
 */

import * as React from "react";
import { useT } from "@/lib/locale";

interface Props {
  eyebrow?: string;
}

export function SettingsHeroV2({
  eyebrow = "Operations · Notifications · Privacy",
}: Props) {
  const t = useT();
  const h = (k: string) => t(`settingsV2.hero.${k}`);
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
        {h("h1Lead")}{" "}
        <span style={{ color: "var(--pq-bronze)" }}>{h("h1Accent")}</span>
        <br />
        {h("h1Lead2")}{" "}
        <span style={{ color: "var(--pq-bronze)" }}>{h("h1Accent2")}</span>
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-h5)",
          lineHeight: 1.55,
          color: "var(--pq-ivory-strong)",
          maxWidth: 720,
          margin: 0,
        }}
      >
        {h("deckPrefix")}
        <span style={{ color: "var(--pq-bronze)" }}>{h("deckAccent")}</span>
        {h("deckSuffix")}
      </p>

    </section>
  );
}

export default SettingsHeroV2;
