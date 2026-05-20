"use client";

/**
 * Detail-page shared presentational atoms.
 *
 * `SectionHeading` — the single Zone2/Zone3 heading mark. Uses <Eyebrow>
 * (bronze tracked label, ~0.22em) above an UPRIGHT Playfair head. Replaces
 * the former RuledKicker + `<EditorialHead ... italic>` pair that violated
 * the v3 "no synthetic italic on Playfair" lock-in (CEO 2026-05-20).
 *
 * `LoadFailure` — P0 resilience surface. When a section's own data source
 * errors or times out it renders an explicit failure note + a "다시 시도"
 * (retry) button instead of an infinite skeleton. Each section owns its own
 * boundary so one slow source can never blank the others.
 */

import * as React from "react";
import { Eyebrow } from "@/components/landing/eyebrow";
import { EditorialHead } from "@/components/ui/editorial";

export function SectionHeading({
  eyebrow,
  title,
  icon,
  size = 22,
}: {
  eyebrow: string;
  title: React.ReactNode;
  icon?: React.ReactNode;
  size?: 18 | 22 | 26 | 30;
}) {
  return (
    <div className="flex items-center gap-3">
      {icon ? <span className="shrink-0">{icon}</span> : null}
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        {/* UPRIGHT — no italic. v3 lock-in (CEO 2026-05-20). */}
        <EditorialHead size={size} as="h2" className="mt-1.5">
          {title}
        </EditorialHead>
      </div>
    </div>
  );
}

/**
 * Editorial empty / unavailable note. Replaces `pq-detail-empty-note`
 * (which carried `font-style: italic` — now upright per the cross-cutting
 * fix). Plain serif, dim ivory, upright.
 */
export function EmptyNote({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={`font-serif ${className}`}
      style={{
        fontStyle: "normal",
        fontSize: 14,
        lineHeight: 1.5,
        color: "rgba(245,240,232,0.5)",
        letterSpacing: "-0.005em",
      }}
    >
      {children}
    </p>
  );
}

/**
 * P0 resilience: a self-contained failure card with an explicit retry.
 * Used by any section whose data source errored or exceeded its timeout.
 */
export function LoadFailure({
  label,
  onRetry,
  retrying = false,
  note,
}: {
  label: string;
  onRetry: () => void;
  retrying?: boolean;
  note?: string;
}) {
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-6 rounded-sm text-center">
      <p className="font-serif text-pq-body text-[var(--pq-ivory-mid)]">
        {label}
      </p>
      {note ? (
        <p className="mt-1.5 text-pq-mono-xs font-mono text-[var(--pq-ivory-faint)]">
          {note}
        </p>
      ) : null}
      <button
        type="button"
        onClick={onRetry}
        disabled={retrying}
        className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 text-pq-mono-xs uppercase tracking-[0.18em] border border-[var(--pq-bronze)] text-[var(--pq-bronze)] hover:bg-[rgba(184,149,106,0.08)] hover:text-[var(--pq-bronze-light)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors rounded-sm"
      >
        {retrying ? "다시 시도 중…" : "다시 시도"}
      </button>
    </div>
  );
}
