"use client";

/**
 * Zone3 DOSSIER — Companion CTA. Hands off the current snapshot (fundamentals,
 * signal label, recent coverage) to a pre-seeded Companion thread.
 * "AI Assistant" wording only (legal). CTA radius rounded-sm.
 */

import Link from "next/link";
import { MessageSquare, ExternalLink } from "lucide-react";
import { FieldLabel, EditorialHead } from "@/components/ui/editorial";

export function CompanionCta({ ticker }: { ticker: string }) {
  return (
    <section>
      <Link
        href={`/companion?ticker=${encodeURIComponent(ticker || "")}`}
        className="block bg-[rgba(184,149,106,0.04)] border border-[var(--pq-bronze)]/40 rounded-sm p-5 hover:bg-[rgba(184,149,106,0.08)] hover:border-[var(--pq-bronze)] transition-all group"
      >
        <div className="flex items-start gap-4">
          <MessageSquare
            className="h-5 w-5 text-[var(--pq-bronze)] mt-0.5"
            strokeWidth={1.4}
          />
          <div className="flex-1">
            <FieldLabel>AI Assistant · context handoff</FieldLabel>
            {/* UPRIGHT — no italic. */}
            <EditorialHead
              size={26}
              as="div"
              className="mt-1.5 group-hover:text-[var(--pq-bronze-light)] transition-colors"
            >
              Ask Companion about {ticker || "this ticker"}
            </EditorialHead>
            <p className="mt-2 pq-detail-caption">
              Open a Companion thread pre-seeded with the current snapshot —
              fundamentals, signal label, and recent coverage.
            </p>
          </div>
          <div className="text-pq-eyebrow-sm uppercase tracking-[0.18em] text-[var(--pq-bronze)] opacity-60 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1.5 self-center">
            Open
            <ExternalLink className="h-3 w-3" />
          </div>
        </div>
      </Link>
    </section>
  );
}
