"use client";

import type { ReactNode } from "react";
import { ModalShell } from "@/components/ui/modal-shell";

/**
 * PortfolioModal — editorial dialog surface for Portfolio page.
 * Reuses the accessible ModalShell (focus trap, ESC, backdrop close,
 * body-scroll lock) and wraps it in ivory editorial styling.
 */
interface PortfolioModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Footer actions rendered at the bottom of the sheet (Cancel / CTA). */
  footer?: ReactNode;
}

export function PortfolioModal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
}: PortfolioModalProps) {
  if (!open) return null;

  return (
    <ModalShell
      onClose={onClose}
      ariaLabelledBy="portfolio-modal-title"
      className="!bg-[rgba(10,10,10,0.72)]"
    >
      <div
        className="w-full max-w-[520px] rounded-sm bg-white shadow-[0_20px_60px_rgba(0,0,0,0.15)]"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="px-8 pt-8 pb-6">
          <h2
            id="portfolio-modal-title"
            className="font-serif text-[24px] leading-tight italic text-slate-900"
          >
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-1.5 text-[13px] text-slate-500">{subtitle}</p>
          ) : null}
        </div>
        <div className="px-8 pb-2">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-3 border-t border-slate-100 px-8 py-5">
            {footer}
          </div>
        ) : null}
      </div>
    </ModalShell>
  );
}

/* ── Shared field primitives ── */

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </span>
      {children}
      {hint ? <span className="text-[11px] text-slate-400">{hint}</span> : null}
    </label>
  );
}

export const inputClass =
  "h-10 rounded-sm border border-slate-200 bg-white px-3 text-[14px] text-slate-900 tabular-nums outline-none transition-colors focus:border-[#8B6F47] focus:ring-1 focus:ring-[#8B6F47]/30";

export function CancelButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-10 rounded-sm px-4 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-100"
    >
      Cancel
    </button>
  );
}

export function PrimaryButton({
  children,
  type = "submit",
  onClick,
}: {
  children: ReactNode;
  type?: "button" | "submit";
  onClick?: () => void;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      className="h-10 rounded-sm bg-[#8B6F47] px-5 text-[13px] font-medium tracking-wide text-white transition-colors hover:bg-[#6F5636]"
    >
      {children}
    </button>
  );
}
