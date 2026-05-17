"use client";

/**
 * <GenerateArtifactCta /> — 3 horizontal request tiles. On click the
 * tile POSTs to `generateArtifact()` and surfaces a toast-style status
 * line. New artifact appears in the list once the backend job completes
 * (existing `useArtifacts` SWR revalidates).
 *
 * Tier gating: Earnings Pre-Brief / Risk Note are Pro-only. Brag Card
 * is free-tier.
 *
 * Source: design-mockups/reports-v2/SPEC.md §4.
 *
 * Legal: pure desk metaphor — no banned vocabulary. Description text
 * is reviewed copy, no recommend/advice tokens.
 */

import * as React from "react";
import Link from "next/link";
import { Lock } from "lucide-react";
import {
  generateArtifact,
  type GenerateArtifactBody,
} from "@/lib/hooks";
import type { ArtifactType } from "@/lib/types";
import type { Tier } from "./artifact-kind-card";

const TIER_RANK: Record<Tier, number> = { free: 0, pro: 1, premium: 2 };
function hasAccess(userTier: Tier, required: Tier): boolean {
  return TIER_RANK[userTier] >= TIER_RANK[required];
}

interface RequestTile {
  /** Display name (Playfair 20 ivory). */
  displayName: string;
  /** Mono dim sub-line. */
  subLine: string;
  /** Source Serif 13 description. */
  description: string;
  /** Bronze CTA label. */
  ctaLabel: string;
  /** Backend artifact type to generate. */
  type: ArtifactType;
  /** Optional ticker prompt — when present we ask for input. */
  needsTicker?: boolean;
  /** Optional topic prompt. */
  needsTopic?: boolean;
  /** Minimum tier. */
  minTier: Tier;
}

const TILES: RequestTile[] = [
  {
    displayName: "Brag Card",
    subLine: "Current quarter · 3 trades, 1 chart",
    description:
      "Compose a quarter-to-date brag card — what worked, in language that fits a one-on-one.",
    ctaLabel: "Generate now ›",
    type: "monthly_brag",
    minTier: "free",
  },
  {
    displayName: "Earnings Pre-Brief",
    subLine: "Per ticker · 24h before print",
    description:
      "Queue a pre-brief on the next earnings date for a ticker in your book or watchlist.",
    ctaLabel: "Queue pre-brief ›",
    type: "earnings_prebrief",
    needsTicker: true,
    minTier: "pro",
  },
  {
    displayName: "Risk Note",
    subLine: "Custom · plain-prose answer",
    description:
      "Free-text request — VaR concentration, tail risk, sector exposure. The desk drafts a memo.",
    ctaLabel: "Open request ›",
    type: "risk_report",
    needsTopic: true,
    minTier: "pro",
  },
];

interface Props {
  tier: Tier;
}

interface TileState {
  status: "idle" | "queueing" | "queued" | "error";
  message?: string;
}

export function GenerateArtifactCta({ tier }: Props) {
  const [states, setStates] = React.useState<Record<string, TileState>>({});
  const [inputs, setInputs] = React.useState<Record<string, string>>({});

  const handleGenerate = React.useCallback(
    async (tile: RequestTile) => {
      const inputValue = inputs[tile.type]?.trim() ?? "";
      const body: GenerateArtifactBody = { type: tile.type };
      if (tile.needsTicker) {
        if (!inputValue) {
          setStates((s) => ({
            ...s,
            [tile.type]: {
              status: "error",
              message: "Enter a ticker first.",
            },
          }));
          return;
        }
        body.ticker = inputValue.toUpperCase();
      } else if (tile.needsTopic) {
        if (!inputValue) {
          setStates((s) => ({
            ...s,
            [tile.type]: {
              status: "error",
              message: "Describe what to look at.",
            },
          }));
          return;
        }
        body.topic = inputValue;
      }
      setStates((s) => ({
        ...s,
        [tile.type]: { status: "queueing" },
      }));
      try {
        const r = await generateArtifact(body);
        setStates((s) => ({
          ...s,
          [tile.type]: {
            status: "queued",
            message: `Queued · ETA ~${r.eta_seconds}s`,
          },
        }));
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Backend offline";
        setStates((s) => ({
          ...s,
          [tile.type]: {
            status: "error",
            message: msg.includes("404")
              ? "Coming soon — backend pending."
              : msg,
          },
        }));
      }
    },
    [inputs],
  );

  return (
    <section aria-labelledby="ask-heading" style={{ marginTop: 80 }}>
      <h2
        id="ask-heading"
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(26px, 3.4vw, 40px)",
          lineHeight: 1.1,
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "0 0 12px",
        }}
      >
        Ask the desk.
      </h2>
      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.6,
          color: "rgba(245,240,232,0.7)",
          margin: "0 0 24px",
          maxWidth: 620,
        }}
      >
        Three on-demand artifacts. Drafted by AI, reviewed by you before the file
        ever leaves the archive.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 12,
        }}
        className="md:!grid-cols-1"
      >
        {TILES.map((tile) => {
          const locked = !hasAccess(tier, tile.minTier);
          const state = states[tile.type] ?? { status: "idle" as const };
          return (
            <div
              key={tile.type + tile.displayName}
              style={{
                border:
                  "1px solid var(--pq-hairline, var(--pq-ivory-line))",
                borderRadius: 4,
                padding: 24,
                background: "rgba(255,255,255,0.02)",
                position: "relative",
                opacity: locked ? 0.7 : 1,
              }}
            >
              {locked && (
                <div
                  aria-hidden="true"
                  style={{ position: "absolute", top: 14, right: 14 }}
                >
                  <Lock
                    className="h-3.5 w-3.5"
                    style={{ color: "var(--pq-bronze, #B8956A)" }}
                  />
                </div>
              )}

              {/* 종목명 main pattern */}
              <h3
                className="font-display"
                style={{
                  fontWeight: 500,
                  fontSize: "var(--pq-text-h4)",
                  color: "var(--pq-ivory, #F5F0E8)",
                  margin: 0,
                  lineHeight: 1.2,
                }}
              >
                {tile.displayName}
              </h3>
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.18em",
                  color: "rgba(245,240,232,0.45)",
                  marginTop: 4,
                }}
              >
                {tile.subLine}
              </div>

              <p
                className="font-serif"
                style={{
                  fontSize: "var(--pq-text-body)",
                  lineHeight: 1.55,
                  color: "rgba(245,240,232,0.7)",
                  margin: "14px 0 16px",
                }}
              >
                {tile.description}
              </p>

              {(tile.needsTicker || tile.needsTopic) && !locked && (
                <input
                  type="text"
                  value={inputs[tile.type] ?? ""}
                  onChange={(e) =>
                    setInputs((s) => ({ ...s, [tile.type]: e.target.value }))
                  }
                  placeholder={
                    tile.needsTicker ? "AAPL" : "e.g. tail risk in semis"
                  }
                  aria-label={
                    tile.needsTicker
                      ? `Ticker symbol for ${tile.displayName}`
                      : `Topic for ${tile.displayName}`
                  }
                  className="font-mono"
                  style={{
                    width: "100%",
                    background: "rgba(0,0,0,0.3)",
                    border:
                      "1px solid var(--pq-hairline, var(--pq-ivory-line))",
                    borderRadius: 2,
                    color: "var(--pq-ivory, #F5F0E8)",
                    fontSize: "var(--pq-text-eyebrow)",
                    padding: "8px 10px",
                    marginBottom: 12,
                    letterSpacing: tile.needsTicker ? "0.14em" : "normal",
                    textTransform: tile.needsTicker ? "uppercase" : "none",
                  }}
                />
              )}

              {locked ? (
                <Link
                  href="/pricing"
                  className="pq-ink-btn-bronze inline-flex"
                  style={{ fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.18em" }}
                >
                  Upgrade to {tile.minTier}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => handleGenerate(tile)}
                  disabled={state.status === "queueing"}
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.18em",
                    color: "var(--pq-bronze, #B8956A)",
                    background: "transparent",
                    border: "none",
                    borderBottom:
                      "1px solid var(--pq-bronze-15, rgba(184,149,106,0.15))",
                    paddingBottom: 2,
                    cursor:
                      state.status === "queueing" ? "wait" : "pointer",
                  }}
                >
                  {state.status === "queueing" ? "Queueing…" : tile.ctaLabel}
                </button>
              )}

              {state.status !== "idle" && (
                <div
                  aria-live="polite"
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.18em",
                    color:
                      state.status === "error"
                        ? "var(--pq-negative, #d18888)"
                        : "rgba(245,240,232,0.55)",
                    marginTop: 12,
                  }}
                >
                  {state.message}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default GenerateArtifactCta;
