"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { motion } from "motion/react";
import {
  Download,
  FileText,
  Globe,
  Image as ImageIcon,
  Mail,
  Monitor,
  Smartphone,
  Tablet,
  X,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";

/* ═══════════════════════ types ═══════════════════════ */

type Format = "html" | "pdf" | "email" | "png";

interface ArtifactCatalogEntry {
  type: string;
  title_ko: string;
  title_en: string;
  description: string;
  tier: "free" | "pro" | "premium";
  formats: Format[];
  cadence: string;
}

interface CatalogResponse {
  artifacts: ArtifactCatalogEntry[];
  count: number;
}

type Language = "ko" | "en";
type DeviceSize = "mobile" | "tablet" | "desktop";

/* ═══════════════════════ helpers ═══════════════════════ */

const TIER_STYLE: Record<ArtifactCatalogEntry["tier"], string> = {
  free:    "bg-slate-100 text-slate-700 border-slate-200",
  pro:     "bg-amber-50 text-amber-700 border-amber-200",
  premium: "bg-amber-100 text-amber-900 border-amber-300",
};

const CADENCE_LABEL: Record<string, string> = {
  weekly:    "주간",
  monthly:   "월간",
  quarterly: "분기",
  annual:    "연간",
  event:     "이벤트",
  on_demand: "온디맨드",
};

const FORMAT_ICON: Record<Format, typeof FileText> = {
  html:  Globe,
  pdf:   FileText,
  email: Mail,
  png:   ImageIcon,
};

const FORMAT_LABEL: Record<Format, string> = {
  html:  "HTML 미리보기",
  pdf:   "PDF 다운로드",
  email: "이메일 미리보기",
  png:   "PNG 다운로드",
};

const DEVICE_WIDTH: Record<DeviceSize, number> = {
  mobile:  375,
  tablet:  768,
  desktop: 1024,
};

/* ═══════════════════════ page ═══════════════════════ */

export default function AdminArtifactPreviewPage() {
  const [lang, setLang] = useState<Language>("ko");
  const [tierFilter, setTierFilter] = useState<"all" | ArtifactCatalogEntry["tier"]>("all");
  const [preview, setPreview] = useState<{
    type: string;
    title: string;
    format: Format;
  } | null>(null);

  const { data, error, isLoading } = useSWR<CatalogResponse>(
    API.admin.artifactsList,
    (url: string) => apiFetch<CatalogResponse>(url),
    { revalidateOnFocus: false },
  );

  const items = useMemo(() => {
    const list = data?.artifacts ?? [];
    if (tierFilter === "all") return list;
    return list.filter((a) => a.tier === tierFilter);
  }, [data, tierFilter]);

  const openPreview = (entry: ArtifactCatalogEntry, format: Format) => {
    if (format === "pdf" || format === "png") {
      // Force download.
      const url = API.admin.artifactDownload(entry.type, format);
      window.open(url, "_blank", "noopener");
      return;
    }
    setPreview({
      type: entry.type,
      title: lang === "ko" ? entry.title_ko : entry.title_en,
      format,
    });
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 md:px-6 md:py-10">
      {/* ── Intro ── */}
      <section className="mb-6 flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">
            Artifact Preview
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            유료 유저에게 발송되는 모든 PDF · 이메일 템플릿을 가상의 포트폴리오 샘플
            데이터로 즉시 렌더합니다. 실제 유저 데이터는 포함되지 않습니다.
          </p>
        </div>

        {/* Language + tier toggle */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center rounded-md border border-slate-200 bg-white p-0.5 text-xs">
            {(["ko", "en"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={cn(
                  "rounded px-2.5 py-1 font-medium transition-colors",
                  lang === l ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-900",
                )}
                type="button"
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="flex items-center rounded-md border border-slate-200 bg-white p-0.5 text-xs">
            {(["all", "free", "pro", "premium"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTierFilter(t)}
                className={cn(
                  "rounded px-2.5 py-1 font-medium capitalize transition-colors",
                  tierFilter === t ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-900",
                )}
                type="button"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ── Error / Loading ── */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          카탈로그 로드 실패. 백엔드 `/api/admin/artifacts/list` 상태를 확인하십시오.
        </div>
      )}

      {isLoading && !data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      )}

      {/* ── Cards grid ── */}
      {!isLoading && items.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {items.map((entry, idx) => (
            <ArtifactCard
              key={entry.type}
              entry={entry}
              lang={lang}
              index={idx}
              onSelect={openPreview}
            />
          ))}
        </div>
      )}

      {!isLoading && items.length === 0 && !error && (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          선택한 티어에 해당하는 artifact 가 없습니다.
        </div>
      )}

      {/* ── Footer meta ── */}
      {data && (
        <p className="mt-8 text-xs text-slate-400">
          Showing {items.length} of {data.count} artifacts · 샘플 데이터는
          <code className="mx-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-pq-eyebrow">
            services/artifacts/sample_data.py
          </code>
          에서 제공
        </p>
      )}

      {/* ── Preview Modal ── */}
      {preview && (
        <PreviewModal
          type={preview.type}
          title={preview.title}
          format={preview.format}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}

/* ═══════════════════════ card ═══════════════════════ */

function ArtifactCard({
  entry,
  lang,
  index,
  onSelect,
}: {
  entry: ArtifactCatalogEntry;
  lang: Language;
  index: number;
  onSelect: (entry: ArtifactCatalogEntry, format: Format) => void;
}) {
  const title = lang === "ko" ? entry.title_ko : entry.title_en;
  const thumbnailUrl = API.admin.artifactPreview(entry.type, entry.formats[0] ?? "html");

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.24), duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className="group flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition-shadow hover:shadow-md"
    >
      {/* Header: tier + cadence */}
      <header className="flex items-center justify-between gap-2 px-4 pt-4">
        <span
          className={cn(
            "rounded border px-2 py-0.5 text-pq-eyebrow font-bold uppercase tracking-wider",
            TIER_STYLE[entry.tier],
          )}
        >
          {entry.tier}
        </span>
        <span className="text-pq-eyebrow text-slate-400">
          {CADENCE_LABEL[entry.cadence] ?? entry.cadence}
        </span>
      </header>

      {/* Title + description */}
      <div className="flex-1 px-4 pt-2">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-500">
          {entry.description}
        </p>
      </div>

      {/* Thumbnail (iframe first page) */}
      <div className="relative mt-3 h-40 overflow-hidden border-y border-slate-100 bg-slate-50">
        {entry.formats.includes("html") || entry.formats.includes("email") ? (
          <iframe
            src={thumbnailUrl}
            title={`${entry.type} preview`}
            className="pointer-events-none absolute left-0 top-0 origin-top-left scale-[0.32]"
            style={{ width: "312.5%", height: "312.5%" }}
            sandbox="allow-same-origin"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-slate-400">
            <ImageIcon className="mr-1 h-4 w-4" /> PNG 전용
          </div>
        )}
      </div>

      {/* Action buttons */}
      <footer className="flex flex-wrap gap-2 p-3">
        {entry.formats.map((fmt) => {
          const Icon = FORMAT_ICON[fmt];
          return (
            <button
              key={fmt}
              type="button"
              onClick={() => onSelect(entry, fmt)}
              className={cn(
                "inline-flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-pq-mono-sm font-medium transition-colors",
                fmt === "pdf" || fmt === "png"
                  ? "border border-slate-900 bg-slate-900 text-white hover:bg-slate-800"
                  : "border border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {fmt === "pdf" || fmt === "png" ? (
                <>
                  <Download className="h-3 w-3" />
                  {FORMAT_LABEL[fmt]}
                </>
              ) : (
                FORMAT_LABEL[fmt]
              )}
            </button>
          );
        })}
      </footer>
    </motion.article>
  );
}

/* ═══════════════════════ preview modal ═══════════════════════ */

function PreviewModal({
  type,
  title,
  format,
  onClose,
}: {
  type: string;
  title: string;
  format: Format;
  onClose: () => void;
}) {
  const [device, setDevice] = useState<DeviceSize>("desktop");
  const previewUrl = API.admin.artifactPreview(type, format);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col bg-slate-900/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Modal header */}
      <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 md:px-6">
        <div className="flex items-center gap-3 truncate">
          <h2 className="truncate text-sm font-semibold text-slate-900 md:text-base">
            {title}
          </h2>
          <span className="hidden rounded bg-slate-100 px-2 py-0.5 text-pq-eyebrow font-medium uppercase tracking-wider text-slate-600 md:inline">
            {format}
          </span>
          <span className="hidden rounded bg-amber-50 px-2 py-0.5 text-pq-eyebrow font-medium uppercase tracking-wider text-amber-700 md:inline">
            sample data
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Device toggle — useful for email previews */}
          <div className="hidden items-center rounded-md border border-slate-200 bg-white p-0.5 text-xs md:flex">
            {(["mobile", "tablet", "desktop"] as const).map((d) => {
              const Icon = d === "mobile" ? Smartphone : d === "tablet" ? Tablet : Monitor;
              return (
                <button
                  key={d}
                  onClick={() => setDevice(d)}
                  className={cn(
                    "flex h-6 w-7 items-center justify-center rounded transition-colors",
                    device === d ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-900",
                  )}
                  type="button"
                  aria-label={`${d} view`}
                >
                  <Icon className="h-3.5 w-3.5" />
                </button>
              );
            })}
          </div>

          <a
            href={API.admin.artifactDownload(type, "pdf")}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden items-center gap-1.5 rounded-md border border-slate-900 bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 sm:inline-flex"
          >
            <Download className="h-3.5 w-3.5" />
            PDF
          </a>

          <button
            onClick={onClose}
            type="button"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
            aria-label="Close preview"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* Iframe container */}
      <div className="flex flex-1 items-stretch justify-center overflow-auto bg-slate-100 p-4 md:p-6">
        <div
          className="h-full w-full max-w-none overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg transition-[width] duration-300"
          style={{
            maxWidth: `${DEVICE_WIDTH[device]}px`,
          }}
        >
          <iframe
            key={`${type}-${format}-${device}`}
            src={previewUrl}
            title={`${title} preview`}
            className="h-full w-full border-0"
            sandbox="allow-same-origin allow-popups"
          />
        </div>
      </div>
    </motion.div>
  );
}
