"use client";

/**
 * 다시 찾기 — the bar above 내 리서치 (2026-10-27).
 *
 * A word box plus three chip rows: 어디서 알게 됐나 · 상태 · 적은 기간. The
 * words match the ticker, the stock name and everything the user wrote on the
 * form (services/research_notes/service.py::list_research — matched on the
 * server after decrypting the user's own rows). Controlled: the page owns
 * the filters and turns them into the list URL (lib/research.ts).
 *
 * Typing is debounced here so a word costs one request, not one per key.
 * Nothing on the bar says anything about a stock we did not hear from the
 * user.
 */
import * as React from "react";
import { Chip, INPUT } from "@/components/journal/research/research-controls";
import { FieldLabel } from "@/components/ui/editorial";
import {
  EMPTY_RESEARCH_FILTERS,
  INFO_SOURCE_LABEL,
  INFO_SOURCE_ORDER,
  RESEARCH_MAX_QUERY,
  RESEARCH_PERIOD_LABEL,
  RESEARCH_PERIOD_ORDER,
  RESEARCH_STATUS_LABEL,
  RESEARCH_STATUS_ORDER,
  researchFiltersActive,
  type ResearchFilters,
} from "@/lib/research";

export const RESEARCH_QUERY_DEBOUNCE_MS = 300;

export interface ResearchFinderProps {
  filters: ResearchFilters;
  onChange: (next: ResearchFilters) => void;
}

export function ResearchFinder({ filters, onChange }: ResearchFinderProps) {
  const [text, setText] = React.useState(filters.q);

  // A chip tapped mid-typing restarts the wait with the new chips, so the
  // commit never writes back stale ones.
  React.useEffect(() => {
    if (text === filters.q) return;
    const id = setTimeout(() => onChange({ ...filters, q: text }), RESEARCH_QUERY_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [text, filters, onChange]);

  const set = (patch: Partial<ResearchFilters>) => onChange({ ...filters, ...patch });

  return (
    <div className="space-y-3" data-testid="research-finder">
      <input
        type="search"
        value={text}
        maxLength={RESEARCH_MAX_QUERY}
        onChange={(e) => setText(e.target.value)}
        placeholder="종목, 적은 이유, 틀린 선… 아무 말로 찾기"
        aria-label="리서치 찾기"
        className={INPUT}
        data-testid="research-search"
      />

      <div>
        <FieldLabel tone="muted">어디서 알게 됐나</FieldLabel>
        <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="출처로 찾기">
          {[...INFO_SOURCE_ORDER, "none" as const].map((s) => (
            <Chip key={s} on={filters.source === s} onClick={() => set({ source: filters.source === s ? null : s })}>
              {INFO_SOURCE_LABEL[s]}
            </Chip>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-3">
        <div>
          <FieldLabel tone="muted">상태</FieldLabel>
          <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="상태로 찾기">
            {RESEARCH_STATUS_ORDER.map((s) => (
              <Chip key={s} on={filters.status === s} onClick={() => set({ status: filters.status === s ? null : s })}>
                {RESEARCH_STATUS_LABEL[s]}
              </Chip>
            ))}
          </div>
        </div>
        <div>
          <FieldLabel tone="muted">적은 기간</FieldLabel>
          <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="적은 기간으로 찾기">
            {RESEARCH_PERIOD_ORDER.map((p) => (
              <Chip key={p} on={filters.period === p} onClick={() => set({ period: p })}>
                {RESEARCH_PERIOD_LABEL[p]}
              </Chip>
            ))}
          </div>
        </div>
      </div>

      {researchFiltersActive(filters) && (
        <button
          type="button"
          onClick={() => {
            setText("");
            onChange(EMPTY_RESEARCH_FILTERS);
          }}
          className="inline-flex h-9 items-center text-pq-body-sm text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
          data-testid="research-filters-clear"
        >
          조건 지우기
        </button>
      )}
    </div>
  );
}
