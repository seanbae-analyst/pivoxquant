"use client";

/**
 * Zone3 DOSSIER — Related artefacts. The user's 3 most recent artifacts
 * (real cross-ticker research, not hardcoded sample PDFs). Empty state links
 * to Reports. Headings upright.
 */

import Link from "next/link";
import { FileText, ExternalLink } from "lucide-react";
import { FieldLabel, EditorialHead } from "@/components/ui/editorial";
import { getArtifactViewerUrl } from "@/lib/artifact-viewer";
import { WEEKLY_MEMO_EMPTY_LINE } from "@/lib/cfo/memo-schedule";
import { SectionHeading } from "./shared";

interface ArtifactLike {
  id: number;
  type: string;
  title?: string | null;
  sent_at?: string | null;
  has_file?: boolean;
}

function artifactLabel(type?: string | null): string {
  return type === "weekly_memo"
    ? "Weekly Memo"
    : type === "earnings_prebrief"
      ? "Earnings Pre-Brief"
      : type === "monthly_brag" || type === "brag_card"
        ? "Brag Card"
        : type === "dd_checklist"
          ? "DD Checklist"
          : type === "risk_board"
            ? "Risk Board"
            : type === "year_end_letter"
              ? "Year-End Letter"
              : (type || "Artifact").replace(/_/g, " ");
}

export function RelatedArtefacts({
  artifacts,
}: {
  artifacts: ArtifactLike[];
}) {
  return (
    <section>
      <div className="mb-5">
        <SectionHeading
          eyebrow="From your archive"
          title="Recent artefacts"
          icon={
            <FileText className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
          }
        />
      </div>
      {artifacts.length === 0 ? (
        <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-sm p-6 text-center">
          <p className="pq-detail-caption">No artefacts yet — {WEEKLY_MEMO_EMPTY_LINE}</p>
          <Link
            href="/reports"
            className="mt-3 inline-flex items-center gap-1.5 text-pq-eyebrow-sm uppercase tracking-[0.18em] text-[var(--pq-bronze)] hover:underline"
          >
            Open Reports
            <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {artifacts.slice(0, 3).map((a) => {
            const dateLabel = a.sent_at
              ? new Date(a.sent_at).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })
              : "Archived";
            return (
              <a
                key={a.id}
                href={getArtifactViewerUrl({
                  id: a.id,
                  type: a.type,
                  has_file: a.has_file,
                })}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-sm p-5 hover:border-[var(--pq-bronze)] hover:bg-[rgba(139,111,71,0.04)] transition-all group"
              >
                <FieldLabel>{dateLabel}</FieldLabel>
                {/* UPRIGHT — no italic. */}
                <EditorialHead
                  size={18}
                  as="div"
                  className="mt-2 group-hover:text-[var(--pq-bronze-light)] transition-colors"
                >
                  {artifactLabel(a.type)}
                </EditorialHead>
                <p className="mt-2 pq-detail-caption truncate">
                  {a.title || "Open the document for context."}
                </p>
                <div className="mt-4 text-pq-eyebrow-sm uppercase tracking-[0.18em] text-[var(--pq-bronze)] opacity-60 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1.5">
                  Open
                  <ExternalLink className="h-3 w-3" />
                </div>
              </a>
            );
          })}
        </div>
      )}
    </section>
  );
}
