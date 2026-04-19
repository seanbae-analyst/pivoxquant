"use client";

import { Check, Upload } from "lucide-react";
import { useT } from "@/lib/locale";

interface KiwoomCardProps {
  /** Null if never uploaded, otherwise the most recent upload timestamp. */
  lastUpload?: string | null;
  /** Opens the upload modal. */
  onUpload: () => void;
}

/**
 * Shared Kiwoom (키움증권) connection card used in both onboarding and settings.
 * Kiwoom has no public OAuth/API for retail accounts, so we support the
 * 영웅문 잔고 엑셀 export flow: user uploads a .xls / .xlsx / .csv file.
 */
export function KiwoomCard({ lastUpload, onUpload }: KiwoomCardProps) {
  const t = useT();
  const hasUpload = Boolean(lastUpload);

  return (
    <div className="sp-card p-4 sm:p-5 relative overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-10 -right-10 h-28 w-28 rounded-full opacity-30 blur-2xl"
        style={{ background: "linear-gradient(135deg, #f59e0b, #ef4444)" }}
      />

      <div className="flex items-center gap-3 mb-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-[10px] font-bold tracking-wide text-white">
          키움
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900 truncate">
            {t("brokerOnboarding.kiwoom.name")}
          </p>
          <p className="text-xs text-slate-500 truncate">
            {t("brokerOnboarding.kiwoom.desc")}
          </p>
        </div>
        {hasUpload ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-medium text-emerald-600 shrink-0">
            <Check className="h-3 w-3" />
            {t("brokerOnboarding.badge.connected")}
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500 shrink-0">
            {t("brokerOnboarding.badge.uploadNeeded")}
          </span>
        )}
      </div>

      {hasUpload && (
        <p className="mb-3 text-[11px] text-slate-400">
          {t("brokerOnboarding.kiwoom.lastUpload")}: {lastUpload}
        </p>
      )}

      <button
        type="button"
        onClick={onUpload}
        className={`flex w-full items-center justify-center gap-1.5 rounded-full px-4 py-2.5 text-sm font-semibold transition-all active:scale-[0.97] ${
          hasUpload
            ? "border border-slate-200 text-slate-700 hover:bg-slate-50"
            : "bg-slate-950 text-white hover:bg-slate-800"
        }`}
      >
        <Upload className="h-4 w-4" />
        {hasUpload
          ? t("brokerOnboarding.kiwoom.reupload")
          : t("brokerOnboarding.kiwoom.upload")}
      </button>
    </div>
  );
}
