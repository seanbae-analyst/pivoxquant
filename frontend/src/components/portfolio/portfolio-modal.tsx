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
      className="!bg-[rgba(5,5,5,0.82)]"
    >
      <div
        className="w-full max-w-[520px] rounded-[2px] border border-[rgba(245,240,232,0.1)] bg-[var(--pq-ink,#050505)] shadow-[0_20px_60px_rgba(0,0,0,0.6)]"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="px-8 pt-8 pb-6">
          <h2
            id="portfolio-modal-title"
            className="font-serif text-[24px] leading-tight text-[var(--pq-ivory,#F5F0E8)]"
          >
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-1.5 text-[13px] text-[rgba(245,240,232,0.55)]">
              {subtitle}
            </p>
          ) : null}
        </div>
        <div className="px-8 pb-2">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-3 border-t border-[rgba(245,240,232,0.08)] px-8 py-5">
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
      <span className="text-[11px] font-semibold uppercase tracking-wider text-[rgba(245,240,232,0.5)]">
        {label}
      </span>
      {children}
      {hint ? (
        <span className="text-[11px] text-[rgba(245,240,232,0.35)]">{hint}</span>
      ) : null}
    </label>
  );
}

export const inputClass =
  "h-10 rounded-[2px] border border-[rgba(245,240,232,0.15)] bg-[rgba(255,255,255,0.02)] px-3 text-[14px] text-[var(--pq-ivory,#F5F0E8)] tabular-nums outline-none transition-colors placeholder:text-[rgba(245,240,232,0.3)] focus:border-[var(--pq-bronze,#8B6F47)] focus:ring-1 focus:ring-[var(--pq-bronze,#8B6F47)]/30";

export function CancelButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-10 rounded-[2px] px-4 text-[13px] font-medium text-[rgba(245,240,232,0.6)] transition-colors hover:bg-[rgba(245,240,232,0.06)]"
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
      className="h-10 rounded-[2px] bg-[var(--pq-bronze,#8B6F47)] px-5 text-[13px] font-medium tracking-wide text-[var(--pq-ink,#050505)] transition-colors hover:bg-[var(--pq-bronze-light,#A88655)]"
    >
      {children}
    </button>
  );
}
