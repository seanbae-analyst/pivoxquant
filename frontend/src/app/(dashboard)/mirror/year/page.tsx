"use client";

/**
 * /mirror/year — 올해의 기록: one KST calendar year of the user's own record
 * and their own words (routes/year_recap.py, services/year_recap/).
 *
 * A sub-screen of 거울 (bottom-nav subRoutes, top-bar ‹). The title avoids
 * "결산" — the CFO metaphor is retired (pwa-assets copy test). The year
 * selector shows only when the user has records in more than one year. The
 * share button draws a counts-only PNG on the device (share-card.ts).
 *
 * Disclaimer: mounted once by (dashboard)/layout.tsx — /mirror/year falls
 * under the /mirror prefix → "behavior-mirror". This page mounts none.
 */
import * as React from "react";
import Link from "next/link";

import { useYearRecap } from "@/lib/hooks";
import { researchDate } from "@/lib/research";
import { Caption, EditorialHead } from "@/components/ui/editorial";
import { YearRecapView } from "@/components/mirror/year/year-recap-view";
import { canShareCard, shareYearCard, type ShareResult } from "@/components/mirror/year/share-card";

const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";

const SHARE_STATUS: Record<ShareResult, string | null> = {
  shared: null,
  cancelled: null,
  downloaded: "이미지를 저장했어요.",
  failed: "이미지를 만들지 못했어요.",
};

function YearSelector({ years, year, onPick }: { years: number[]; year: number; onPick: (y: number) => void }) {
  return (
    <div role="group" aria-label="연도" className="mt-4 flex flex-wrap gap-2">
      {years.map((y) => (
        <button
          key={y}
          type="button"
          aria-pressed={y === year}
          onClick={() => onPick(y)}
          className="rounded-[var(--pq-radius-cta)] px-3 py-1.5 text-[13px] tabular-nums"
          style={{
            border: "1px solid var(--pq-ivory-line)",
            color: y === year ? "var(--pq-ink)" : "var(--pq-ivory)",
            background: y === year ? "var(--pq-bronze)" : "transparent",
          }}
        >
          {y}년
        </button>
      ))}
    </div>
  );
}

export default function YearRecapPage() {
  const [year, setYear] = React.useState<number | null>(null);
  const { data, isLoading, error } = useYearRecap(year);
  const [status, setStatus] = React.useState<string | null>(null);
  const [sharing, setSharing] = React.useState(false);

  const onShare = async () => {
    if (!data) return;
    setSharing(true);
    try {
      setStatus(SHARE_STATUS[await shareYearCard(data)]);
    } catch {
      setStatus(SHARE_STATUS.failed);
    } finally {
      setSharing(false);
    }
  };

  const shownYear = data?.year ?? year;
  return (
    <div className="mx-auto w-full max-w-2xl px-0 pb-8 md:px-6 md:py-8" data-testid="year-recap-page">
      <header className="mb-8">
        <EditorialHead as="h1" size={26}>
          {shownYear ? `${shownYear}년, 내 기록` : "올해의 기록"}
        </EditorialHead>
        {data && !data.empty && (
          <Caption className="mt-2 max-w-lg">
            {researchDate(data.range.start)}부터 {researchDate(data.range.end)}까지, 여기에 남긴 기록만 셌어요.
          </Caption>
        )}
        {data && data.years.length > 1 && (
          <YearSelector years={data.years} year={data.year} onPick={(y) => { setStatus(null); setYear(y); }} />
        )}
        <Link
          href="/mirror"
          // Phone: the app bar's ‹ carries back (top-bar.tsx subScreen).
          className="mt-3 hidden text-pq-caption text-[var(--pq-bronze-light)] underline-offset-4 hover:underline md:inline-flex"
        >
          ← 거울로
        </Link>
      </header>

      {isLoading && <div className="h-40 w-full animate-pulse rounded-[var(--pq-radius-card)]" style={{ background: "rgba(var(--pq-ivory-rgb), 0.06)" }} aria-hidden />}
      {!isLoading && error && (
        <p className="text-[13px]" style={{ color: DIM }}>기록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</p>
      )}
      {data && !error && <YearRecapView data={data} />}

      {data && !error && canShareCard(data) && (
        <section aria-label="공유" className="mt-10 pt-6" style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
          <button
            type="button"
            onClick={onShare}
            disabled={sharing}
            className="pq-ink-btn-bronze inline-flex items-center px-5 py-2.5 text-pq-mono-sm"
            data-testid="year-share"
          >
            숫자만 이미지로 공유
          </button>
          <p className="mt-2 text-[12px]" style={{ color: DIM }}>
            종목·금액·적은 문장은 넣지 않아요. 이미지는 이 기기에서 그려요.
          </p>
          {status && <p role="status" className="mt-2 text-[12.5px]" style={{ color: DIM }}>{status}</p>}
        </section>
      )}
    </div>
  );
}
