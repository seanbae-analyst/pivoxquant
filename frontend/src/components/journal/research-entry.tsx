"use client";

/**
 * <ResearchEntry /> — the way into /journal/research from the 기록 page.
 *
 * One quiet row under the observation-note composer: what the form is, and
 * how many notes have reached their review day. Renders nothing while the
 * overview loads or fails — a wrong count is worse than none.
 */
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useResearchOverview } from "@/lib/hooks";

export function ResearchEntry() {
  const { data, isLoading, error } = useResearchOverview();
  if (isLoading || error) return null;
  const due = data?.counts?.due ?? 0;
  return (
    <Link
      href="/journal/research"
      data-testid="research-entry"
      className="flex items-center justify-between gap-3 rounded-[var(--pq-radius-card)] px-4 py-3 transition-colors hover:bg-[var(--pq-card-veil-strong)]"
      style={{ border: "1px solid var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
    >
      <span className="min-w-0">
        <span className="block text-pq-body-sm font-semibold text-[var(--pq-ivory)]">리서치 양식으로 쓰기</span>
        <span className="mt-0.5 block text-pq-caption text-[var(--pq-ivory-dim)]">
          사기 전에 직접 확인한 것을 다섯 칸에 적고, 정한 날 채점해요
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-1 text-pq-caption tabular-nums">
        {due > 0 && <span className="text-[var(--pq-bronze-light)]">다시 볼 것 {due}개</span>}
        <ChevronRight size={16} aria-hidden className="text-[var(--pq-ivory-faint)]" />
      </span>
    </Link>
  );
}

export default ResearchEntry;
