"use client";

/**
 * <ArtifactKindCard /> — single card in the 3×2 gallery. 종목명 main
 * pattern: editorial display name (Playfair 22) on top, mono dim cadence
 * sub-line beneath. Bronze type pill, hairline meta-row at the foot.
 *
 * Tier-gated: when the user's tier is below `minTier`, show a Lock badge
 * + "Upgrade to {tier}" CTA instead of the open arrow.
 *
 * Source: design-mockups/reports-v2/SPEC.md §3.
 */

import * as React from "react";
import Link from "next/link";
import { Lock } from "lucide-react";
import type { ArtifactType } from "@/lib/types";
import { cn } from "@/lib/utils";

export type Tier = "free" | "pro" | "premium";

export interface ArtifactKindEntry {
  /** Display label shown as the editorial main name (Playfair 22). */
  displayName: string;
  /** Cadence pill text (e.g. "Daily"). */
  cadenceLabel: string;
  /** Mono dim sub-line (e.g. "Auto · 06:00 KST · Mon–Fri"). */
  schedule: string;
  /** 2-line description (Source Serif 4 13.5). */
  description: string;
  /** Backend artifact type — used for filter drill-down. */
  type: ArtifactType;
  /** Slug for the static preview route under `/reports/preview/{slug}`. */
  previewSlug: string;
  /** Minimum tier required to receive a generated copy. */
  minTier: Tier;
  /** Optional last-published label (resolved from useArtifacts). */
  lastPublished?: string | null;
  /** Optional next-due label. */
  nextDue?: string | null;
}

interface Props {
  entry: ArtifactKindEntry;
  locked: boolean;
}

export function ArtifactKindCard({ entry, locked }: Props) {
  const previewHref = `/reports/preview/${entry.previewSlug}`;
  const archiveHref = `/reports?type=${entry.type}`;
  const cardHref = locked ? "/pricing" : archiveHref;

  return (
    <article
      className={cn(
        "group relative overflow-hidden",
        "transition-colors duration-200",
        locked && "opacity-70",
      )}
      style={{
        border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
        borderRadius: 4,
        padding: 28,
        background: "rgba(255,255,255,0.02)",
      }}
    >
      <Link
        href={cardHref}
        aria-label={`${entry.displayName} — ${locked ? "upgrade to access" : "open archive"}`}
        className="absolute inset-0"
        style={{ overflow: "hidden", textIndent: "-9999px", zIndex: 1 }}
      >
        Open
      </Link>

      {locked && (
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            top: 16,
            right: 16,
            zIndex: 2,
          }}
        >
          <Lock
            className="h-3.5 w-3.5"
            style={{ color: "var(--pq-bronze, #B8956A)" }}
          />
        </div>
      )}

      <span
        className="font-mono uppercase inline-block"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze, #B8956A)",
          border: "1px solid var(--pq-hairline-2, rgba(245,240,232,0.12))",
          borderRadius: 2,
          padding: "3px 8px",
        }}
      >
        {entry.cadenceLabel}
      </span>

      {/* 종목명 main pattern — Playfair name on top, mono dim sub-line beneath */}
      <h3
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "var(--pq-text-quote)",
          lineHeight: 1.2,
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "16px 0 4px",
        }}
      >
        {entry.displayName}
      </h3>
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.18em",
          color: "rgba(245,240,232,0.45)",
        }}
      >
        {entry.schedule}
      </div>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.7)",
          margin: "16px 0 0",
        }}
      >
        {entry.description}
      </p>

      <div
        style={{
          marginTop: 24,
          paddingTop: 14,
          borderTop: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-kicker)",
              letterSpacing: "0.2em",
              color: "rgba(245,240,232,0.45)",
            }}
          >
            Last published
          </div>
          <div
            className="font-mono"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: "var(--pq-text-eyebrow)",
              color: "rgba(245,240,232,0.78)",
              marginTop: 4,
            }}
          >
            {entry.lastPublished ?? "—"}
          </div>
        </div>
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-kicker)",
              letterSpacing: "0.2em",
              color: "rgba(245,240,232,0.45)",
            }}
          >
            Next due
          </div>
          <div
            className="font-mono"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: "var(--pq-text-eyebrow)",
              color: "rgba(245,240,232,0.78)",
              marginTop: 4,
            }}
          >
            {entry.nextDue ?? "—"}
          </div>
        </div>
      </div>

      {locked && (
        <div style={{ position: "relative", zIndex: 2, marginTop: 18 }}>
          <Link
            href="/pricing"
            className="pq-ink-btn-bronze inline-flex items-center"
            style={{ fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.18em" }}
          >
            Upgrade to {entry.minTier}
          </Link>
        </div>
      )}

      {!locked && (
        <div
          style={{ position: "relative", zIndex: 2, marginTop: 14 }}
          className="font-mono uppercase"
        >
          <Link
            href={previewHref}
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "rgba(245,240,232,0.55)",
              borderBottom:
                "1px solid var(--pq-bronze-15, rgba(184,149,106,0.15))",
              paddingBottom: 1,
              textDecoration: "none",
            }}
          >
            See sample ›
          </Link>
        </div>
      )}
    </article>
  );
}

export default ArtifactKindCard;
