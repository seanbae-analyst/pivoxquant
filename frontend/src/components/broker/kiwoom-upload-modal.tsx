"use client";

import { useCallback, useRef, useState } from "react";
import { FileSpreadsheet, Loader2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { ModalShell } from "@/components/ui/modal-shell";
import { API } from "@/lib/endpoints";
import { useT } from "@/lib/locale";

interface KiwoomUploadModalProps {
  onClose: () => void;
  onSuccess?: (importedCount: number) => void;
}

const ACCEPTED = ".xls,.xlsx,.csv";
const MAX_BYTES = 5 * 1024 * 1024; // 5MB

interface KiwoomUploadResponse {
  imported_count?: number;
  error?: string;
}

/**
 * Drag-and-drop Kiwoom 영웅문 balance import.
 * Sends a FormData POST to /api/broker/kiwoom/csv.
 * Note: endpoint is implemented by a separate backend agent — errors are
 * surfaced cleanly if the endpoint is not yet live.
 */
export function KiwoomUploadModal({ onClose, onSuccess }: KiwoomUploadModalProps) {
  const t = useT();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const setValidatedFile = useCallback(
    (candidate: File | null) => {
      if (!candidate) {
        setFile(null);
        return;
      }
      const name = candidate.name.toLowerCase();
      const isAccepted =
        name.endsWith(".xls") ||
        name.endsWith(".xlsx") ||
        name.endsWith(".csv");
      if (!isAccepted) {
        toast.error(t("brokerOnboarding.kiwoom.badFormat"));
        return;
      }
      if (candidate.size > MAX_BYTES) {
        toast.error(t("brokerOnboarding.kiwoom.fileTooLarge"));
        return;
      }
      setFile(candidate);
    },
    [t],
  );

  const handleUpload = async () => {
    if (!file || uploading) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      // FormData + apiFetch: we can't use JSON body, so call fetch directly
      // but retain the CSRF header + credentials posture used elsewhere.
      const csrfCookie = document.cookie
        .split("; ")
        .find((c) => c.startsWith("csrf_token="));
      const csrfToken = csrfCookie
        ? decodeURIComponent(csrfCookie.split("=")[1])
        : undefined;

      const res = await fetch(API.broker.kiwoomCsvUpload, {
        method: "POST",
        credentials: "include",
        headers: csrfToken ? { "X-CSRF-Token": csrfToken } : undefined,
        body: formData,
      });

      if (!res.ok) {
        const body: KiwoomUploadResponse = await res.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${res.status}`);
      }

      const body: KiwoomUploadResponse = await res.json().catch(() => ({}));
      const count = body.imported_count ?? 0;

      toast.success(
        count > 0
          ? t("brokerOnboarding.kiwoom.importSuccess").replace(
              "{count}",
              String(count),
            )
          : t("brokerOnboarding.kiwoom.importEmpty"),
      );
      onSuccess?.(count);
      onClose();
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : t("brokerOnboarding.kiwoom.uploadError");
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <ModalShell onClose={onClose} ariaLabel="Kiwoom 잔고 업로드">
      <div className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-md overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900">
              {t("brokerOnboarding.kiwoom.modalTitle")}
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              {t("brokerOnboarding.kiwoom.modalSubtitle")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const dropped = e.dataTransfer.files?.[0];
            if (dropped) setValidatedFile(dropped);
          }}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          className={`flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-8 text-center cursor-pointer transition-colors ${
            dragOver
              ? "border-[#8b5cf6] bg-[#8b5cf6]/[0.04]"
              : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/50"
          }`}
        >
          {file ? (
            <>
              <FileSpreadsheet className="h-8 w-8 text-emerald-500" />
              <p className="text-sm font-semibold text-slate-900 break-all">
                {file.name}
              </p>
              <p className="text-xs text-slate-500">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </>
          ) : (
            <>
              <Upload className="h-8 w-8 text-slate-400" />
              <p className="text-sm font-semibold text-slate-700">
                {t("brokerOnboarding.kiwoom.dropHere")}
              </p>
              <p className="text-xs text-slate-400">
                {t("brokerOnboarding.kiwoom.acceptHint")}
              </p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            className="hidden"
            onChange={(e) => setValidatedFile(e.target.files?.[0] ?? null)}
          />
        </div>

        <a
          href="https://www.kiwoom.com"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          {t("brokerOnboarding.kiwoom.formatGuide")}
        </a>

        <div className="flex gap-2 pt-4">
          <button
            type="button"
            onClick={handleUpload}
            disabled={!file || uploading}
            className="flex-1 flex items-center justify-center gap-2 rounded-full bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading && <Loader2 className="h-4 w-4 animate-spin" />}
            {uploading
              ? t("brokerOnboarding.kiwoom.uploading")
              : t("brokerOnboarding.kiwoom.uploadBtn")}
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={uploading}
            className="rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t("brokerOnboarding.cancel")}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
