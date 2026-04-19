"use client";

import { useState } from "react";
import { Download, Share2, X, MessageCircle, Camera } from "lucide-react";
import { ModalShell } from "@/components/ui/modal-shell";
import { useT } from "@/lib/locale";
import { API } from "@/lib/endpoints";
import type { Artifact } from "@/lib/types";

export interface PreviewModalProps {
  artifact: Artifact;
  onClose: () => void;
  onDownload: (artifact: Artifact) => void;
}

/**
 * PreviewModal — PDF iframe renderer with share actions.
 *
 * Content source priority:
 *   1. artifact.pdf_url  → render as iframe
 *   2. artifact.thumbnail_url → render as image (fallback for non-PDF types)
 *   3. backend preview endpoint → iframe via /api/artifacts/{id}/preview
 *   4. "not available" placeholder
 *
 * Share actions are only meaningful for Monthly Brag cards, so we only
 * surface them when the artifact is image-based (thumbnail_url present).
 */
export function PreviewModal({ artifact, onClose, onDownload }: PreviewModalProps) {
  const t = useT();
  const [shareOpen, setShareOpen] = useState(false);

  const previewUrl = artifact.pdf_url ?? API.artifacts.preview(artifact.id);
  const isImagePreview =
    !artifact.pdf_url && Boolean(artifact.thumbnail_url);
  const canShare =
    artifact.type === "monthly_brag" || artifact.type === "quarterly_review";

  const handleKakaoShare = () => {
    // Placeholder — real Kakao SDK integration lives in a separate ticket.
    // For now we copy the preview URL so the user can paste it anywhere.
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(window.location.origin + previewUrl).catch(
        () => {
          /* ignore clipboard denial */
        },
      );
    }
    setShareOpen(false);
  };

  const handleInstaShare = () => {
    // Instagram has no web share intent — users save the image and upload
    // manually. We trigger a download of the thumbnail (or PDF).
    onDownload(artifact);
    setShareOpen(false);
  };

  return (
    <ModalShell onClose={onClose} ariaLabel={t("reports.preview.title")}>
      <div className="flex h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div className="min-w-0 flex-1">
            <h2 className="font-serif truncate text-lg font-semibold text-slate-900">
              {artifact.title}
            </h2>
            {artifact.subtitle && (
              <p className="mt-0.5 truncate text-xs text-slate-500">
                {artifact.subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("reports.preview.close")}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body — iframe or image */}
        <div className="relative flex-1 overflow-auto bg-slate-50">
          {isImagePreview && artifact.thumbnail_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={artifact.thumbnail_url}
              alt={artifact.title}
              className="mx-auto h-full w-auto object-contain"
            />
          ) : previewUrl ? (
            <iframe
              src={previewUrl}
              title={artifact.title}
              className="h-full w-full border-0"
              // PDFs render natively; sandbox kept loose so links inside
              // the document stay clickable.
            />
          ) : (
            <div className="flex h-full items-center justify-center p-8 text-center text-sm text-slate-500">
              {t("reports.preview.notAvailable")}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between gap-2 border-t border-slate-100 bg-white px-5 py-3">
          <div className="relative">
            {canShare && (
              <button
                type="button"
                onClick={() => setShareOpen((v) => !v)}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
              >
                <Share2 className="h-4 w-4" strokeWidth={1.75} />
                {t("reports.preview.share")}
              </button>
            )}
            {shareOpen && (
              <div className="absolute bottom-full left-0 mb-2 w-44 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
                <button
                  type="button"
                  onClick={handleKakaoShare}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-50"
                >
                  <MessageCircle className="h-4 w-4 text-yellow-500" strokeWidth={1.75} />
                  {t("reports.preview.shareKakao")}
                </button>
                <button
                  type="button"
                  onClick={handleInstaShare}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-50"
                >
                  <Camera className="h-4 w-4 text-accent" strokeWidth={1.75} />
                  {t("reports.preview.shareInsta")}
                </button>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => onDownload(artifact)}
            disabled={!artifact.pdf_url}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <Download className="h-4 w-4" strokeWidth={1.75} />
            {t("reports.preview.download")}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
