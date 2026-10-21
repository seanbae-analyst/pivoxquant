"use client";

/**
 * /journal/research — 리서치 양식: write what you checked yourself before
 * buying, then score it on the day you chose.
 *
 * docs/design/research-notes_2026-10-15.md. Order on the page:
 *   1. 다시 볼 리서치 — notes whose day has come, scoring open.
 *   2. 새 리서치 — the five-field form (open by default when there is nothing
 *      yet, or when arriving with ?ticker= from a /portfolio row).
 *   3. 채점 결과 — 판단 × 결과 and 출처별, counts only.
 *   4. 내 리서치 — every note, newest first, 100 at a time ("더 보기").
 *
 * The page is a sub-screen of 기록 (bottom-nav subRoutes, top-bar ‹). Nothing
 * here reads a quote or says anything about a stock we did not hear from the
 * user. Not an order surface.
 */
import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWRInfinite from "swr/infinite";
import { API } from "@/lib/endpoints";
import { fetcher, useResearchOverview } from "@/lib/hooks";
import { looksLikeTicker, researchDate } from "@/lib/research";
import type { ResearchNotesResponse } from "@/lib/types";
import { Caption, EditorialHead, RuledKicker } from "@/components/ui/editorial";
import { ResearchForm } from "@/components/journal/research/research-form";
import { ResearchCard } from "@/components/journal/research/research-card";
import { ResearchSummary } from "@/components/journal/research/research-summary";

/** One read of 내 리서치 (the server allows up to 200). */
const RESEARCH_PAGE_SIZE = 100;

/**
 * 내 리서치, page by page on the server's id cursor (`next_before` →
 * `?before=`, routes/research_notes.py). 2026-10-15: the page read one
 * `?limit=100` and dropped `next_before`, so the 101st note on was neither
 * shown nor deletable here. `mutate()` re-reads every loaded page, so a
 * delete or a score never leaves a stale page behind.
 */
function useResearchPages() {
  const swr = useSWRInfinite<ResearchNotesResponse>(
    (_index, prev: ResearchNotesResponse | null) => {
      // `== null` — a body without the field (demo `{}`) is the end, not
      // `?before=undefined` re-reading page 1.
      if (prev && prev.next_before == null) return null;
      const before = prev ? `&before=${prev.next_before}` : "";
      return `${API.research.list}?limit=${RESEARCH_PAGE_SIZE}${before}`;
    },
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );
  const pages = swr.data ?? [];
  const last = pages[pages.length - 1];
  return {
    notes: pages.flatMap((p) => (Array.isArray(p?.notes) ? p.notes : [])),
    hasMore: Boolean(last && last.next_before != null),
    loadingMore: swr.size > pages.length,
    isLoading: swr.isLoading,
    loadMore: () => void swr.setSize(swr.size + 1),
    mutate: swr.mutate,
  };
}

function SectionTitle({ children, id }: { children: React.ReactNode; id?: string }) {
  return (
    <h2 id={id} className="text-pq-body font-semibold text-[var(--pq-ivory)]">
      {children}
    </h2>
  );
}

function ResearchPageInner() {
  const params = useSearchParams();
  // An old link can carry a typed name — only a symbol is pre-picked.
  const rawTicker = params.get("ticker");
  const tickerParam = rawTicker && looksLikeTicker(rawTicker) ? rawTicker.trim().toUpperCase() : null;
  const from = params.get("from");
  const surface = from === "portfolio" || from === "pre_trade" ? from : "journal";
  const overview = useResearchOverview();
  const list = useResearchPages();
  const [formOpen, setFormOpen] = useState<boolean | null>(rawTicker || params.get("new") ? true : null);
  const [saved, setSaved] = useState<string | null>(null);

  const refresh = () => {
    void overview.mutate();
    void list.mutate();
  };

  const loaded = !overview.isLoading && !list.isLoading;
  const empty = loaded && list.notes.length === 0;
  // Open by default for a first visit; after that it is a button.
  const showForm = formOpen ?? empty;
  const due = overview.data?.due ?? [];
  const dueIds = new Set(due.map((n) => n.id));
  // The due ones are shown (with scoring open) above; the list holds the rest.
  const rest = list.notes.filter((n) => !dueIds.has(n.id));

  return (
    <div className="mx-auto w-full max-w-2xl px-0 pb-8 md:px-6 md:py-8" data-testid="research-page">
      <header className="mb-6">
        <RuledKicker>리서치</RuledKicker>
        <EditorialHead as="h1" size={26} className="mt-3">
          사기 전에, 직접 확인한 것
        </EditorialHead>
        <Caption className="mt-2 max-w-lg">
          모든 종목에 같은 다섯 칸이에요. 정한 날 다시 보고, 그때 적은 이유가 맞았는지 스스로 채점해요.
        </Caption>
        <Link
          href="/journal"
          // Phone: the app bar's ‹ carries back (top-bar.tsx subScreen).
          className="mt-3 hidden text-pq-caption text-[var(--pq-bronze-light)] underline-offset-4 hover:underline md:inline-flex"
        >
          ← 기록으로
        </Link>
      </header>

      {saved && (
        <p role="status" className="mb-5 text-pq-body-sm text-[var(--pq-bronze-light)]" data-testid="research-saved">
          저장했어요. {saved}에 다시 보여 드려요.
        </p>
      )}

      {/* 1. 다시 볼 리서치 */}
      {due.length > 0 && (
        <section aria-labelledby="research-due" className="mb-8">
          <SectionTitle id="research-due">
            다시 볼 리서치 <span className="tabular-nums">{due.length}</span>개
          </SectionTitle>
          <ul className="mt-3 list-none space-y-3 p-0">
            {due.map((n) => (
              <li key={n.id}>
                <ResearchCard note={n} onChanged={refresh} startOpen />
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 2. 새 리서치 */}
      <section aria-labelledby="research-new" className="mb-8">
        {showForm ? (
          <div className="rounded-[var(--pq-radius-card)] p-4 md:p-6" style={{ border: "1px solid var(--pq-ivory-line)" }}>
            <SectionTitle id="research-new">새 리서치</SectionTitle>
            <div className="mt-4">
              <ResearchForm
                defaultTicker={tickerParam ? { ticker: tickerParam, name: params.get("name") ?? "" } : null}
                surface={surface}
                onSaved={(note) => {
                  setSaved(researchDate(note.review_on));
                  setFormOpen(false);
                  refresh();
                }}
                onCancel={empty ? undefined : () => setFormOpen(false)}
              />
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => {
              setSaved(null);
              setFormOpen(true);
            }}
            className="pq-ink-btn-bronze inline-flex items-center px-5 py-2.5 text-pq-mono-sm"
            id="research-new"
          >
            새 리서치 쓰기
          </button>
        )}
      </section>

      {/* 3. 채점 결과 */}
      {overview.data?.counts && overview.data.counts.notes > 0 && (
        <section aria-label="채점 결과" className="mb-8 pt-6" style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
          <ResearchSummary data={overview.data} />
        </section>
      )}

      {/* 4. 내 리서치 */}
      {(rest.length > 0 || list.hasMore) && (
        <section aria-labelledby="research-all" className="pt-6" style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
          <SectionTitle id="research-all">
            {due.length > 0 ? "그 밖의 리서치" : "내 리서치"} <span className="tabular-nums">{rest.length}</span>개
          </SectionTitle>
          <ul className="mt-3 list-none space-y-3 p-0">
            {rest.map((n) => (
              <li key={n.id}>
                <ResearchCard note={n} onChanged={refresh} />
              </li>
            ))}
          </ul>
          {list.hasMore && (
            <button
              type="button"
              onClick={list.loadMore}
              disabled={list.loadingMore}
              className="mt-4 inline-flex h-10 items-center text-pq-body-sm text-[var(--pq-bronze-light)] underline-offset-4 hover:underline disabled:opacity-60"
              data-testid="research-load-more"
            >
              {list.loadingMore ? "불러오는 중…" : "이전 리서치 더 보기"}
            </button>
          )}
        </section>
      )}
    </div>
  );
}

export default function ResearchPage() {
  return (
    <Suspense fallback={<div className="mx-auto w-full max-w-2xl px-4 py-8" aria-hidden />}>
      <ResearchPageInner />
    </Suspense>
  );
}
