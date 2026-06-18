/**
 * ArchiveLinks — the 거울 hub's links into the folded record surfaces:
 * Reports (CFO archive) and the decision Journal. Part of the 19→3 fold —
 * Reports/Journal left the primary nav, so 거울 surfaces them here.
 *
 * Plain links (no data fetch) — safe and observational. No italic.
 */
import * as React from "react";
import Link from "next/link";

const LINKS: ReadonlyArray<{ href: string; label: string; note: string }> = [
  { href: "/reports", label: "리포트 보관함", note: "주간·분기 CFO 리포트" },
  { href: "/journal", label: "결정 저널", note: "사기 전 기록 모아보기" },
];

export function ArchiveLinks() {
  return (
    <section>
      <div
        className="text-[10.5px] uppercase tracking-[0.2em]"
        style={{ color: "var(--pq-bronze)" }}
      >
        보관함 · 기록
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="flex items-center justify-between rounded-[4px] px-4 py-3 transition-colors"
            style={{ border: "1px solid var(--pq-ivory-line)" }}
          >
            <span>
              <span className="block text-[13px]" style={{ color: "var(--pq-ivory)" }}>
                {l.label}
              </span>
              <span
                className="block text-[11px]"
                style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
              >
                {l.note}
              </span>
            </span>
            <span style={{ color: "var(--pq-bronze)" }}>→</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
