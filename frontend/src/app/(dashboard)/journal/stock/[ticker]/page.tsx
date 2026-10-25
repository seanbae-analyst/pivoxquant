"use client";

/**
 * /journal/stock/[ticker] — 종목별 내 기록 (2026-10-25).
 *
 * One stock, everything the user recorded on it (components/journal/
 * stock-record-view.tsx). Reached from the holding sheet on /portfolio. The
 * app bar carries the title and ‹ back (top-bar.tsx subScreen); the layout
 * mounts the single DisclaimerBanner.
 */
import { useParams } from "next/navigation";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { StockRecordView } from "@/components/journal/stock-record-view";
import { useStockRecord } from "@/lib/hooks";

export default function StockRecordPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = params?.ticker ? decodeURIComponent(params.ticker) : null;
  const { data, error, isLoading, mutate } = useStockRecord(ticker);

  return (
    <ErrorBoundary>
      <div className="mx-auto w-full max-w-2xl pb-10 md:px-6 md:py-8">
        {isLoading && !data ? (
          <div className="space-y-3" aria-hidden>
            <div className="pq-skeleton-dark h-8 w-40" />
            <div className="pq-skeleton-dark h-4 w-56" />
            <div className="mt-5 grid grid-cols-2 gap-2.5">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="pq-skeleton-dark h-[72px]" />
              ))}
            </div>
          </div>
        ) : error || !data ? (
          <div className="py-10 text-center">
            <p className="text-[14px] text-[var(--pq-ivory-dim)]">기록을 불러오지 못했어요.</p>
            <button
              type="button"
              onClick={() => mutate()}
              className="mt-3 text-[13px] text-[var(--pq-bronze)] underline underline-offset-4"
            >
              다시 시도
            </button>
          </div>
        ) : (
          <StockRecordView data={data} />
        )}
      </div>
    </ErrorBoundary>
  );
}
