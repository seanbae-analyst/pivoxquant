"use client";

/**
 * Zone3 DOSSIER — Insider Form 4 activity. US tickers only (caller gates
 * rendering on `insiderEligible`). SEC EDGAR, last 90 days.
 *
 * KR convention: Acquired → carmine chip (pos), Disposed → indigo chip (neg).
 */

import { Eye } from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionHeading, EmptyNote } from "./shared";
import { formatRelative } from "./types";
import type { InsiderFiling } from "./types";

export function InsiderPanel({ data }: { data: InsiderFiling[] }) {
  return (
    <section>
      <div className="mb-5">
        <SectionHeading
          eyebrow="Form 4 · 90 days"
          title="Insider activity"
          icon={<Eye className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />}
        />
      </div>
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-sm overflow-hidden">
        {data.length > 0 ? (
          <ul className="divide-y divide-[var(--pq-ivory-line-soft)]">
            {data.slice(0, 6).map((f, i) => {
              const acquired = f.acquired === true;
              const shares = Number.isFinite(f.shares as number)
                ? (f.shares as number)
                : 0;
              return (
                <li
                  key={i}
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-[rgba(var(--pq-bronze-wash-rgb),0.03)] transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <span className="text-pq-body text-[var(--pq-ivory)] font-serif">
                      {f.insider || "—"}
                    </span>
                    {f.relationship && (
                      <span className="ml-2.5 pq-field-label">
                        {f.relationship}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span
                      className={cn(
                        "pq-sent-chip",
                        acquired ? "pq-sent-chip--pos" : "pq-sent-chip--neg",
                      )}
                    >
                      {acquired ? "Acquired" : "Disposed"}
                    </span>
                    <span className="font-mono tabular-nums text-pq-caption text-[var(--pq-ivory)]">
                      {shares.toLocaleString()}
                    </span>
                    <span className="text-pq-eyebrow-sm tracking-[0.12em] uppercase text-[var(--pq-ivory-faint)]">
                      {formatRelative(f.transaction_date)}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="p-6 text-center">
            <EmptyNote>
              No public Form 4 filings observed in the last 90 days.
            </EmptyNote>
          </div>
        )}
      </div>
    </section>
  );
}
