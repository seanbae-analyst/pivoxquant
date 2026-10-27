"use client";

/**
 * The text-field class and the toggle chip shared by the research form and
 * the 다시 찾기 bar (research-finder.tsx) — one look for both, and a test that
 * mocks the form still renders the bar.
 */
import * as React from "react";

export const INPUT =
  "w-full rounded-[var(--pq-radius-card)] border border-[var(--pq-ivory-line)] bg-transparent px-3 py-2 text-pq-body-sm text-[var(--pq-ivory)] outline-none placeholder:text-[var(--pq-ivory-faint)] focus:border-[var(--pq-bronze)]";

export function Chip({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className="min-h-[36px] rounded-full border px-3 text-pq-body-sm transition-colors"
      style={{
        borderColor: on ? "var(--pq-bronze)" : "var(--pq-ivory-line)",
        background: on ? "rgba(var(--pq-bronze-rgb), 0.14)" : "transparent",
        color: on ? "var(--pq-bronze-light)" : "var(--pq-ivory-dim)",
      }}
    >
      {children}
    </button>
  );
}
