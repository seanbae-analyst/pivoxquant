"use client";

/**
 * <CompanionArchiveCard /> — Card 6 of /home v2.
 *
 * Maps v1's "Companion entry + ArtifactQueue" pair onto a single editorial
 * card. Reuses `useArtifacts({ limit: 3 })` for the recent-3 list and a
 * static "memos written" count derived from the `total` field of the
 * artifacts list (no new hook — keeps lib/hooks.ts untouched).
 */

import * as React from "react";
import { HomeCard } from "./home-card";
import { useArtifacts } from "@/lib/hooks";

interface ArtifactRow {
  id?: number | string;
  title?: string;
  display_title?: string;
  created_at?: string;
  delivered_at?: string;
}

function shortDate(iso?: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  } catch {
    return "";
  }
}

export function CompanionArchiveCard() {
  const { artifacts, total } = useArtifacts({ limit: 3 });
  const rows = ((artifacts ?? []) as ArtifactRow[]).slice(0, 3);

  return (
    <HomeCard
      href="/reports"
      eyebrow="Companion · Past briefs"
      cornerCta="Archive ›"
    >
      <div
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: 32,
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          color: "var(--pq-bronze)",
          marginBottom: 8,
        }}
      >
        {Number.isFinite(total) ? total : 0}
      </div>
      <p
        className="font-serif"
        style={{
          fontSize: 14,
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.82)",
          margin: "0 0 24px 0",
        }}
      >
        memos archived for your record. Open the library to revisit any of them.
      </p>

      {rows.length > 0 ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 12,
            marginBottom: 24,
          }}
        >
          {rows.map((a, i) => {
            const title = a.display_title || a.title || "Untitled brief";
            const date = shortDate(a.delivered_at || a.created_at);
            return (
              <div
                key={a.id ?? `art-${i}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  fontSize: 14,
                  gap: 12,
                }}
              >
                <span
                  className="font-serif"
                  style={{
                    color: "rgba(245,240,232,0.82)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {title}
                </span>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 12,
                    color: "rgba(245,240,232,0.40)",
                    flexShrink: 0,
                  }}
                >
                  {date}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <p
          className="font-serif"
          style={{
            fontSize: 14,
            lineHeight: 1.6,
            color: "rgba(245,240,232,0.55)",
            margin: "0 0 24px 0",
            fontStyle: "italic",
          }}
        >
          The archive is empty. Your first weekly memo lands Monday 07:00 KST.
        </p>
      )}

      <div
        style={{
          display: "flex",
          gap: 14,
          marginTop: "auto",
        }}
      >
        <span
          className="font-mono uppercase"
          style={{
            fontSize: 12,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--pq-bronze)",
          }}
        >
          Brag Card ›
        </span>
        <span
          className="font-mono uppercase"
          style={{
            fontSize: 12,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--pq-bronze)",
          }}
        >
          Voice memos ›
        </span>
      </div>
    </HomeCard>
  );
}

export default CompanionArchiveCard;
