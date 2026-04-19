"use client";

import Image from "next/image";
import {
  FileText,
  Sunrise,
  Sparkles,
  Award,
  BarChart3,
  Shield,
  Download,
  Eye,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useLocale, useT } from "@/lib/locale";
import type { Artifact, ArtifactType } from "@/lib/types";

/* ── Type → icon / badge styling ──────────────────────────────────────── */

const TYPE_ICON: Record<ArtifactType, React.ElementType> = {
  weekly_memo: FileText,
  morning_brief: Sunrise,
  earnings_prebrief: Sparkles,
  monthly_brag: Award,
  quarterly_review: BarChart3,
  risk_report: Shield,
  custom: FileText,
};

const TYPE_BADGE_KEY: Record<ArtifactType, string> = {
  weekly_memo: "reports.badge.weeklyMemo",
  morning_brief: "reports.badge.morningBrief",
  earnings_prebrief: "reports.badge.earningsPrebrief",
  monthly_brag: "reports.badge.monthlyBrag",
  quarterly_review: "reports.badge.quarterlyReview",
  risk_report: "reports.badge.riskReport",
  custom: "reports.badge.custom",
};

/* Badge accent colors — kept muted so cards read as a cohesive library,
 * not a technicolor mess. Warm gold is reserved for the NEW dot. */
const TYPE_ACCENT: Record<ArtifactType, string> = {
  weekly_memo: "bg-blue-50 text-blue-700 border-blue-200",
  morning_brief: "bg-amber-50 text-amber-700 border-amber-200",
  earnings_prebrief: "bg-indigo-50 text-indigo-700 border-indigo-200",
  monthly_brag: "bg-rose-50 text-rose-700 border-rose-200",
  quarterly_review: "bg-teal-50 text-teal-700 border-teal-200",
  risk_report: "bg-red-50 text-red-700 border-red-200",
  custom: "bg-slate-50 text-slate-700 border-slate-200",
};

/* ── Helpers ──────────────────────────────────────────────────────────── */

function formatDate(iso: string, locale: "ko" | "en"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  if (locale === "ko") {
    return d.toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/* ── Card ─────────────────────────────────────────────────────────────── */

export interface ArtifactCardProps {
  artifact: Artifact;
  onPreview: (artifact: Artifact) => void;
  onDownload: (artifact: Artifact) => void;
}

export function ArtifactCard({
  artifact,
  onPreview,
  onDownload,
}: ArtifactCardProps) {
  const t = useT();
  const { locale } = useLocale();
  const Icon = TYPE_ICON[artifact.type] ?? FileText;
  const isUnread = artifact.opened_at === null;

  return (
    <article
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white",
        "transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
        "hover:-translate-y-1 hover:shadow-lg hover:shadow-slate-200/60 hover:border-slate-300",
      )}
    >
      {/* Thumbnail zone — PDF first-page preview if available, else gradient + icon */}
      <button
        type="button"
        onClick={() => onPreview(artifact)}
        className="relative block aspect-[4/3] w-full overflow-hidden bg-gradient-to-br from-slate-50 to-slate-100"
        aria-label={t("reports.card.preview")}
      >
        {artifact.thumbnail_url ? (
          <Image
            src={artifact.thumbnail_url}
            alt={artifact.title}
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 33vw"
            className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Icon
              className="h-14 w-14 text-slate-300"
              strokeWidth={1.25}
            />
          </div>
        )}

        {/* NEW dot — warm gold per design system */}
        {isUnread && (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white shadow-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-white" />
            {t("reports.card.new")}
          </span>
        )}
      </button>

      {/* Content */}
      <div className="flex flex-1 flex-col gap-3 p-5">
        {/* Title — serif for that library-archive feel */}
        <h3 className="font-serif line-clamp-2 text-[17px] font-semibold leading-snug text-slate-900">
          {artifact.title}
        </h3>

        {artifact.subtitle && (
          <p className="line-clamp-2 text-sm text-slate-500">
            {artifact.subtitle}
          </p>
        )}

        {/* Meta row: date + type badge */}
        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <time
            dateTime={artifact.sent_at}
            className="text-xs font-medium text-slate-400"
          >
            {formatDate(artifact.sent_at, locale)}
          </time>
          <span
            className={cn(
              "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold",
              TYPE_ACCENT[artifact.type] ?? TYPE_ACCENT.custom,
            )}
          >
            {t(TYPE_BADGE_KEY[artifact.type] ?? TYPE_BADGE_KEY.custom)}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 border-t border-slate-100 pt-3">
          <button
            type="button"
            onClick={() => onPreview(artifact)}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            <Eye className="h-3.5 w-3.5" strokeWidth={1.75} />
            {t("reports.card.preview")}
          </button>
          <button
            type="button"
            onClick={() => onDownload(artifact)}
            disabled={!artifact.pdf_url}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <Download className="h-3.5 w-3.5" strokeWidth={1.75} />
            {t("reports.card.download")}
          </button>
        </div>
      </div>
    </article>
  );
}
