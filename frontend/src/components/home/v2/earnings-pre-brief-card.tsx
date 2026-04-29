"use client";

/**
 * <EarningsPreBriefCard /> — Card 3 of /home v2.
 *
 * Status: backend endpoint /api/brief/earnings/upcoming does NOT yet exist
 * (MIGRATION.md §3 lists this as a gap). The card therefore degrades
 * gracefully to a "Queue empty — next print outside 7-day window" state.
 *
 * Future: when the endpoint ships, this card will render the headline
 * ticker + EPS/Revenue/Implied move trio + a 3-row queue.
 *
 * Reuses /api/earnings (API.market.earnings) IF it returns user-relevant
 * upcoming prints — but the v1 home didn't wire this either, so we keep
 * it as a placeholder rather than fabricate data.
 */

import * as React from "react";
import { HomeCard } from "./home-card";

export function EarningsPreBriefCard() {
  // No live hook yet. Show empty-state copy and the bronze headline AAPL
  // sigil from the mockup is replaced by an em-dash + caption that the
  // queue is being assembled. Mockup-driven, but legally honest.
  return (
    <HomeCard
      href="/reports"
      eyebrow="Pre-Brief · 7-day window"
      cornerCta="Pre-brief ›"
    >
      <div
        className="font-serif"
        style={{
          fontFamily:
            '"Playfair Display","Source Serif 4",Georgia,serif',
          fontWeight: 500,
          fontSize: 30,
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          marginBottom: 8,
        }}
      >
        —
      </div>

      <p
        className="font-serif"
        style={{
          fontFamily:
            '"Source Serif 4","Iowan Old Style",Georgia,serif',
          fontSize: 14,
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.82)",
          margin: "0 0 24px 0",
        }}
      >
        Pre-brief queue is being assembled. The next print inside the 7-day
        window will surface here with EPS, revenue, and implied-move estimates
        once the briefing endpoint ships.
      </p>

      <div
        className="font-mono uppercase"
        style={{
          fontFamily:
            '"JetBrains Mono","SF Mono",ui-monospace,monospace',
          fontSize: 9.5,
          letterSpacing: "0.22em",
          color: "rgba(245,240,232,0.40)",
          textTransform: "uppercase",
          marginTop: "auto",
        }}
      >
        Queue · 7 days
      </div>
      <div
        className="font-serif"
        style={{
          fontFamily:
            '"Source Serif 4","Iowan Old Style",Georgia,serif',
          fontSize: 13,
          lineHeight: 1.6,
          color: "rgba(245,240,232,0.55)",
          margin: "8px 0 0 0",
          fontStyle: "italic",
        }}
      >
        No upcoming prints inside the window.
      </div>
    </HomeCard>
  );
}

export default EarningsPreBriefCard;
