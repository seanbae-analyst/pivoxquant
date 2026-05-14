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
            className="font-serif text-pq-quote leading-tight text-[var(--pq-ivory,#F5F0E8)]"
          >
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-1.5 text-pq-body-sm text-[rgba(245,240,232,0.55)]">
              {subtitle}
            </p>
          ) : null}
        </div>
        <div className="px-8 pb-2">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-3 border-t border-[var(--pq-ivory-line)] px-8 py-5">
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
      <span className="text-pq-mono-sm font-semibold uppercase tracking-wider text-[rgba(245,240,232,0.5)]">
        {label}
      </span>
      {children}
      {hint ? (
        <span className="text-pq-mono-sm text-[rgba(245,240,232,0.55)]">{hint}</span>
      ) : null}
    </label>
  );
}

export const inputClass =
  "h-10 rounded-[2px] border border-[rgba(245,240,232,0.15)] bg-[rgba(255,255,255,0.02)] px-3 text-pq-body text-[var(--pq-ivory,#F5F0E8)] tabular-nums outline-none transition-colors placeholder:text-[rgba(245,240,232,0.3)] focus:border-[var(--pq-bronze,#B8956A)] focus:ring-1 focus:ring-[var(--pq-bronze,#B8956A)]/30";

export function CancelButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-10 rounded-[2px] px-4 text-pq-body-sm font-medium text-[rgba(245,240,232,0.6)] transition-colors hover:bg-[var(--pq-ivory-line-soft)]"
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
      className="h-10 rounded-[2px] bg-[var(--pq-bronze,#B8956A)] px-5 text-pq-body-sm font-medium tracking-wide text-[var(--pq-ink,#050505)] transition-colors hover:bg-[var(--pq-bronze-light,#A88655)]"
    >
      {children}
    </button>
  );
}
