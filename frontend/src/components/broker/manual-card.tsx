"use client";

import { PencilLine } from "lucide-react";
import { useT } from "@/lib/locale";

/**
 * Option 2 on the broker-onboarding screen: skip broker linking entirely
 * and manage positions by hand (same flow as /portfolio "add position").
 *
 * Vantablack ink theme — paired alongside KisCard.
 */
export function ManualCard({ onSelect }: { onSelect: () => void }) {
  const t = useT();
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-[2px] p-5 sm:p-6 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1">
            Manual entry · No connection
          </div>
          <h3 className="font-serif text-lg text-[var(--pq-ivory)]">
            {t("brokerOnboarding.manual.title")}
          </h3>
          <p className="mt-1 text-[11px] text-[rgba(245,240,232,0.5)]">
            {t("brokerOnboarding.manual.subtitle")}
          </p>
        </div>
        <span className="inline-flex items-center gap-1 border border-[rgba(245,240,232,0.2)] px-2 py-0.5 text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.5)] shrink-0">
          <PencilLine className="h-2.5 w-2.5" />
          Manual
        </span>
      </div>

      <p className="text-[12px] leading-relaxed text-[rgba(245,240,232,0.6)]">
        {t("brokerOnboarding.manual.description")}
      </p>

      <button
        type="button"
        onClick={onSelect}
        className="pq-ink-btn-ghost mt-auto w-full"
      >
        {t("brokerOnboarding.manual.cta")}
      </button>
    </div>
  );
}
