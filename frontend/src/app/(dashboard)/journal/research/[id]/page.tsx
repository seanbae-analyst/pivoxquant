"use client";

/**
 * /journal/research/[id] — 리서치 한 건과 적은 뒤 이 종목에서 한 일 (2026-10-27).
 *
 * CEO "리서치 노트 연결 화면": what was read and written, then what the user
 * did on that stock after it. Two existing reads put together — the note
 * (GET /api/research-notes/<id>) and the stock record (GET /api/stock-record/
 * <ticker>) — no new endpoint. Reached from each research card and from a
 * research row on 종목 기록. The app bar carries ‹ back to the list
 * (top-bar.tsx subScreen); the layout mounts the single DisclaimerBanner.
 */
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ResearchCard } from "@/components/journal/research/research-card";
import { ResearchAfter } from "@/components/journal/research/research-after";
import { useResearchNote, useStockRecord } from "@/lib/hooks";
import { kstToday } from "@/lib/research";

function parseId(raw: string | undefined): number | null {
  if (!raw || !/^\d+$/.test(raw)) return null;
  return Number(raw);
}

export default function ResearchDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = parseId(params?.id);
  const { note, error, isLoading, mutate } = useResearchNote(id);
  const record = useStockRecord(note?.ticker ?? null);

  const refresh = () => {
    void mutate();
    void record.mutate();
  };

  let body: React.ReactNode;
  if (id === null || (!isLoading && (error || !note))) {
    body = (
      <div className="py-10 text-center" data-testid="research-detail-missing">
        <p className="text-[14px] text-[var(--pq-ivory-dim)]">이 리서치를 찾을 수 없어요.</p>
        <Link
          href="/journal/research"
          className="mt-3 inline-block text-[13px] text-[var(--pq-bronze)] underline underline-offset-4"
        >
          리서치 목록으로
        </Link>
      </div>
    );
  } else if (!note) {
    body = (
      <div className="space-y-3" aria-hidden>
        <div className="pq-skeleton-dark h-48" />
        <div className="pq-skeleton-dark h-24" />
      </div>
    );
  } else {
    body = (
      <>
        <ResearchCard
          note={note}
          onChanged={refresh}
          detailLink={false}
          onDeleted={() => router.replace("/journal/research")}
        />
        <div className="mt-8">
          {record.data ? (
            <ResearchAfter note={note} events={record.data.events} today={kstToday()} />
          ) : record.error ? (
            <p className="text-[14px] text-[var(--pq-ivory-dim)]">
              이 종목의 기록을 불러오지 못했어요.{" "}
              <button type="button" onClick={() => record.mutate()} className="text-[var(--pq-bronze)] underline underline-offset-4">
                다시 시도
              </button>
            </p>
          ) : (
            <div className="pq-skeleton-dark h-40" aria-hidden />
          )}
        </div>
      </>
    );
  }

  return (
    <ErrorBoundary>
      <div className="mx-auto w-full max-w-2xl pb-10 md:px-6 md:py-8" data-testid="research-detail">
        {body}
      </div>
    </ErrorBoundary>
  );
}
