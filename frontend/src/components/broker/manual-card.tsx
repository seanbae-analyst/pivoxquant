"use client";

import { PencilLine } from "lucide-react";
import { useT } from "@/lib/locale";

/**
 * Option 3 on the broker-onboarding screen: skip broker linking entirely
 * and manage positions by hand (same flow as /portfolio "add position").
 *
 * Users who don't use KIS or Kiwoom (e.g. foreign broker, not disclosed,
 * or just testing) land here so the three-card grid stays symmetric.
 */
export function ManualCard({ onSelect }: { onSelect: () => void }) {
  const t = useT();
  return (
    <div className="sp-card flex flex-col gap-4 p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
          <PencilLine size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-slate-900">
            {t("brokerOnboarding.manual.title")}
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            {t("brokerOnboarding.manual.subtitle")}
          </p>
        </div>
      </div>

      <div className="inline-flex self-start items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-slate-400" />
        {t("brokerOnboarding.manual.badge")}
      </div>

      <p className="text-xs leading-relaxed text-slate-500">
        {t("brokerOnboarding.manual.description")}
      </p>

      <button
        type="button"
        onClick={onSelect}
        className="mt-auto flex items-center justify-center rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800"
      >
        {t("brokerOnboarding.manual.cta")}
      </button>
    </div>
  );
}
