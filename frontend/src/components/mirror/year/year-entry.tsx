"use client";

/**
 * <YearRecapEntry /> — the way into /mirror/year from 거울.
 *
 * One quiet row, not a hero: the recap is a once-a-year look back, the
 * mirror's own blocks stay first. Fetches nothing — the recap page reads its
 * own data, so the mirror home pays no extra request for a link.
 */
import Link from "next/link";
import { ChevronRight } from "lucide-react";

export function YearRecapEntry({ className = "" }: { className?: string }) {
  return (
    <Link
      href="/mirror/year"
      data-testid="year-recap-entry"
      className={`flex items-center justify-between gap-3 rounded-[var(--pq-radius-card)] px-4 py-3 transition-colors hover:bg-[var(--pq-card-veil-strong)] ${className}`}
      style={{ border: "1px solid var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
    >
      <span className="min-w-0">
        <span className="block text-pq-body-sm font-semibold text-[var(--pq-ivory)]">올해의 기록</span>
        <span className="mt-0.5 block text-pq-caption text-[var(--pq-ivory-dim)]">
          한 해의 멈춤과 기록, 내가 쓴 문장을 모아 봐요
        </span>
      </span>
      <ChevronRight size={16} aria-hidden className="shrink-0 text-[var(--pq-ivory-faint)]" />
    </Link>
  );
}

export default YearRecapEntry;
