"use client";

import { useState } from "react";
import { FileText } from "lucide-react";
import { useArtifacts } from "@/lib/hooks";
import { useT } from "@/lib/locale";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";
import { ArtifactCard } from "@/components/reports/artifact-card";
import { PreviewModal } from "@/components/reports/preview-modal";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import type { Artifact, ArtifactType } from "@/lib/types";

/* ── Filter options ──────────────────────────────────────────────────── */

type TypeFilter = ArtifactType | "all";
type PeriodFilter = "30d" | "90d" | "all";

const TYPE_FILTERS: { key: TypeFilter; labelKey: string }[] = [
  { key: "all", labelKey: "reports.filters.typeAll" },
  { key: "weekly_memo", labelKey: "reports.filters.typeWeekly" },
  { key: "morning_brief", labelKey: "reports.filters.typeMorning" },
  { key: "earnings_prebrief", labelKey: "reports.filters.typeEarnings" },
  { key: "monthly_brag", labelKey: "reports.filters.typeMonthly" },
];

const PERIOD_FILTERS: { key: PeriodFilter; labelKey: string }[] = [
  { key: "30d", labelKey: "reports.filters.period30" },
  { key: "90d", labelKey: "reports.filters.period90" },
  { key: "all", labelKey: "reports.filters.periodAll" },
];

/* ── Page ────────────────────────────────────────────────────────────── */

function ReportsPageInner() {
  const t = useT();
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [periodFilter, setPeriodFilter] = useState<PeriodFilter>("all");
  const [preview, setPreview] = useState<Artifact | null>(null);

  const { artifacts, isLoading, error } = useArtifacts({
    type: typeFilter,
    since: periodFilter,
  });

  // Show a skeleton grid during initial load only. Once we've loaded once,
  // subsequent filter toggles swap data instantly from SWR cache.
  const showSkeleton = isLoading && artifacts.length === 0;

  // Server-side filtering via `since` query param — we trust the backend
  // response and don't re-filter on the client. Keeps the render pure
  // (no Date.now() at render time).
  const filteredArtifacts = artifacts;

  const handleDownload = (artifact: Artifact) => {
    const url = artifact.pdf_url ?? API.artifacts.download(artifact.id);
    // Open in a new tab — browser will stream the PDF. This bypasses the
    // need for blob juggling and respects the backend's Content-Disposition.
    if (typeof window !== "undefined") {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
      {/* Header */}
      <header className="mb-8">
        <h1 className="font-serif text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          {t("reports.title")}
        </h1>
        <p className="mt-2 text-sm text-slate-500 sm:text-base">
          {t("reports.subtitle")}
        </p>
      </header>

      <DisclaimerBanner type="ai-analysis" className="mb-6" />

      {/* Filters */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            {t("reports.filters.type")}
          </span>
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setTypeFilter(f.key)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-200",
                typeFilter === f.key
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900",
              )}
            >
              {t(f.labelKey)}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            {t("reports.filters.period")}
          </span>
          {PERIOD_FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setPeriodFilter(f.key)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-200",
                periodFilter === f.key
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900",
              )}
            >
              {t(f.labelKey)}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {showSkeleton ? (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <EmptyState
          icon={<FileText className="h-7 w-7" strokeWidth={1.5} />}
          title={t("reports.empty.title")}
          description={t("reports.empty.description")}
        />
      ) : filteredArtifacts.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-7 w-7" strokeWidth={1.5} />}
          title={t("reports.empty.title")}
          description={t("reports.empty.description")}
        />
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {filteredArtifacts.map((artifact) => (
            <ArtifactCard
              key={artifact.id}
              artifact={artifact}
              onPreview={setPreview}
              onDownload={handleDownload}
            />
          ))}
        </div>
      )}

      {/* Preview modal */}
      {preview && (
        <PreviewModal
          artifact={preview}
          onClose={() => setPreview(null)}
          onDownload={handleDownload}
        />
      )}
    </div>
  );
}

export default function ReportsPage() {
  return (
    <ErrorBoundary>
      <ReportsPageInner />
    </ErrorBoundary>
  );
}
