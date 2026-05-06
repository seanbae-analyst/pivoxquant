"use client";

/**
 * <ArtifactGalleryGrid /> — 3×2 gallery (6 cards) of `ArtifactKindCard`.
 *
 * One card per `ArtifactType` user-facing CFO artifact:
 *   1. Weekly Pulse            (weekly_memo)
 *   2. Earnings Pre-Brief      (earnings_prebrief)
 *   3. Brag Card               (monthly_brag)
 *   4. Year-End Letter         (custom)
 *   5. Quarterly Audit         (quarterly_review)
 *
 * 2026-04-29: Today's Memo (morning_brief) entry retired — backend
 * Morning Brief service deprecated. Grid now renders 5 user-facing
 * artifacts; `risk_report` continues to surface via the request box (§4).
 *
 * The 18 `/reports/preview/*` static sample routes remain mounted and
 * untouched — each card's "See sample" CTA links into one of them.
 *
 * Source: design-mockups/reports-v2/SPEC.md §3.
 */

import * as React from "react";
import {
  ArtifactKindCard,
  type ArtifactKindEntry,
  type Tier,
} from "./artifact-kind-card";
import type { Artifact, ArtifactType } from "@/lib/types";

const TIER_RANK: Record<Tier, number> = { free: 0, pro: 1, premium: 2 };
function hasAccess(userTier: Tier, required: Tier): boolean {
  return TIER_RANK[userTier] >= TIER_RANK[required];
}

const KIND_ENTRIES: Array<Omit<ArtifactKindEntry, "lastPublished" | "nextDue">> = [
  // Today's Memo (morning_brief) entry REMOVED 2026-04-29 — backend deprecated.
  {
    displayName: "Weekly Pulse",
    cadenceLabel: "Weekly",
    schedule: "Auto · Sun 07:00 KST",
    description:
      "Five-question reflection on the week's trades, a peer-context chart, and one decision flagged for review.",
    type: "weekly_memo",
    previewSlug: "weekly-memo",
    minTier: "free",
  },
  {
    displayName: "Earnings Pre-Brief",
    cadenceLabel: "Pre-Earnings",
    schedule: "On-demand · 24h before print",
    description:
      "Setup, consensus vs. whisper, your exposure, and the lines that matter on the call.",
    type: "earnings_prebrief",
    previewSlug: "earnings-prebrief",
    minTier: "pro",
  },
  {
    displayName: "Brag Card",
    cadenceLabel: "Quarterly",
    schedule: "Auto · End of quarter",
    description:
      "What worked, framed for an interview answer. Three trades, one chart, no spin.",
    type: "monthly_brag",
    previewSlug: "brag-card",
    minTier: "free",
  },
  {
    displayName: "Year-End Letter",
    cadenceLabel: "Annual",
    schedule: "Auto · 31 Dec",
    description:
      "A founder-tone letter from your CFO chair: the year's lessons, the regrets, what to do less of.",
    type: "custom",
    previewSlug: "year-end-letter",
    minTier: "premium",
  },
  {
    displayName: "Quarterly Audit",
    cadenceLabel: "Self-Audit",
    schedule: "Auto · End of quarter",
    description:
      "Process audit on attribution, risk discipline, and behaviour bias — not a report card.",
    type: "quarterly_review",
    previewSlug: "quarterly-self-report",
    minTier: "pro",
  },
];

interface Props {
  artifacts: Artifact[];
  tier: Tier;
}

function findLatestByType(
  artifacts: Artifact[],
  type: ArtifactType,
): Artifact | undefined {
  let best: Artifact | undefined;
  let bestTs = -Infinity;
  for (const a of artifacts) {
    if (a.type !== type) continue;
    const ts = a.sent_at ? Date.parse(a.sent_at) : 0;
    if (ts > bestTs) {
      bestTs = ts;
      best = a;
    }
  }
  return best;
}

function fmtDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function ArtifactGalleryGrid({ artifacts, tier }: Props) {
  const enriched: ArtifactKindEntry[] = React.useMemo(
    () =>
      KIND_ENTRIES.map((e) => {
        const live = findLatestByType(artifacts, e.type);
        return {
          ...e,
          lastPublished: fmtDate(live?.sent_at) ?? null,
          nextDue: null,
        };
      }),
    [artifacts],
  );

  return (
    <section aria-labelledby="kinds-heading" style={{ marginTop: 56 }}>
      <h2
        id="kinds-heading"
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(26px, 3.4vw, 40px)",
          lineHeight: 1.1,
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "0 0 28px",
        }}
      >
        Kinds.
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 12,
        }}
        className="md:!grid-cols-2 sm:!grid-cols-1"
      >
        {enriched.map((entry) => (
          <ArtifactKindCard
            key={`${entry.type}-${entry.previewSlug}`}
            entry={entry}
            locked={!hasAccess(tier, entry.minTier)}
          />
        ))}
      </div>
    </section>
  );
}

export default ArtifactGalleryGrid;
