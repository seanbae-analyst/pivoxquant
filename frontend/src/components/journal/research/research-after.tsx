/**
 * <ResearchAfter /> — 적은 뒤 이 종목에서 한 일 (2026-10-27).
 *
 * One research note next to what the user did on the same stock after
 * writing it: fills, pauses (and the ones no buy followed), notes, other
 * research, filings, and the note's own 다시 볼 날 · 채점 — oldest first, the
 * story from the day it was written. Read from the stock record
 * (GET /api/stock-record/<ticker>) through lib/research.ts::afterNote.
 *
 * Same rule as the card (research-card.tsx): before the note is scored, fill
 * prices stay hidden — the money seen first pulls the score toward "맞음".
 * Dates, sides and share counts are shown; prices appear once it is scored.
 *
 * Facts and counts only. Nearness in time is not cause: the page says so,
 * and it never says the reason was right or wrong — the user scores that.
 */
import * as React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { afterNote, kstDateOf, researchDate, type AfterItem } from "@/lib/research";
import type { ResearchNote, StockRecordEvent } from "@/lib/types";
import { EventBody, EventChips, dayLabel, kindTitle } from "@/components/journal/stock-record-view";

const LINE = "1px solid var(--pq-ivory-line)";
const DIM = "var(--pq-ivory-dim)";

function Stat({ n, label, sub }: { n: number; label: string; sub?: string }) {
  return (
    <div className="rounded-[var(--pq-radius-card)] px-3.5 py-3" style={{ border: LINE }}>
      <div className="text-[22px] font-semibold tabular-nums" style={{ color: "var(--pq-ivory)" }}>
        {n}
      </div>
      <div className="mt-0.5 text-[12px]" style={{ color: DIM }}>
        {label}
        {sub && <span style={{ color: "var(--pq-bronze)" }}> · {sub}</span>}
      </div>
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[12px]"
      style={{ color: DIM, border: LINE }}
    >
      {children}
    </span>
  );
}

function FillLocked({ e }: { e: Extract<StockRecordEvent, { kind: "fill" }> }) {
  return (
    <p className="mt-1 text-[14px] tabular-nums" style={{ color: "var(--pq-ivory)" }} data-testid="after-fill-locked">
      {e.shares.toLocaleString("ko-KR", { maximumFractionDigits: 4 })}주
    </p>
  );
}

function Row({ item, scored }: { item: AfterItem; scored: boolean }) {
  if (item.kind === "review_day") {
    return (
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[12.5px]" style={{ color: DIM }}>
          {researchDate(item.at.slice(0, 10))} · <span style={{ color: "var(--pq-ivory)" }}>다시 볼 날</span>
        </span>
        {item.upcoming && <Tag>예정</Tag>}
      </div>
    );
  }
  if (item.kind === "scored") {
    return (
      <span className="text-[12.5px]" style={{ color: DIM }}>
        {dayLabel(item.at)} · <span style={{ color: "var(--pq-ivory)" }}>채점함</span>
      </span>
    );
  }
  const e = item.event;
  return (
    <>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[12.5px]" style={{ color: DIM }}>
          {dayLabel(e.at)} ·{" "}
          <span style={{ color: "var(--pq-ivory)" }}>{e.kind === "research" ? "같은 종목 다른 리서치" : kindTitle(e)}</span>
        </span>
        <EventChips e={e} />
      </div>
      {e.kind === "fill" && !scored ? <FillLocked e={e} /> : <EventBody e={e} />}
    </>
  );
}

export interface ResearchAfterProps {
  note: ResearchNote;
  events: StockRecordEvent[];
  /** KST "YYYY-MM-DD". */
  today: string;
}

export function ResearchAfter({ note, events, today }: ResearchAfterProps) {
  const { items, counts } = afterNote(note, events, today);
  const scored = Boolean(note.reviewed_at);
  const fills = counts.buys + counts.sells;
  const acts = items.filter((i) => i.kind === "event").length;

  return (
    <section aria-labelledby="research-after" data-testid="research-after">
      <h2 id="research-after" className="text-pq-body font-semibold text-[var(--pq-ivory)]">
        적은 뒤 이 종목에서 한 일
      </h2>
      <p className="mt-1 text-[12.5px] leading-relaxed [word-break:keep-all]" style={{ color: DIM }}>
        {researchDate(kstDateOf(note.created_at))}부터 이 종목에 남긴 기록을 날짜순으로 이어 놓았어요. 시간이
        가깝다고 그 리서치가 거래의 이유였다는 뜻은 아니에요.
      </p>

      <div className="mt-4 grid grid-cols-2 gap-2.5">
        <Stat n={fills} label="체결" sub={fills ? `산 것 ${counts.buys} · 판 것 ${counts.sells}` : undefined} />
        <Stat n={counts.pauses} label="멈춤" sub={counts.notTaken ? `그 뒤로 안 산 것 ${counts.notTaken}` : undefined} />
        <Stat n={counts.notes} label="관찰 노트" />
        <Stat n={counts.research} label="같은 종목 다른 리서치" />
      </div>

      {!scored && fills > 0 && (
        <p className="mt-3 text-[12.5px] leading-relaxed [word-break:keep-all]" style={{ color: DIM }} data-testid="after-price-locked">
          체결 가격은 채점한 뒤에 보여 드려요. 결과를 먼저 보면 이유를 돈으로 판단하게 되기 쉬워요.
        </p>
      )}

      {acts === 0 ? (
        <p className="mt-5 text-[14px]" style={{ color: DIM }} data-testid="research-after-empty">
          적은 뒤로 이 종목에 남긴 기록이 아직 없어요.
        </p>
      ) : null}

      <ol className="mt-4 list-none p-0" style={{ borderTop: LINE }}>
        {items.map((item, i) => (
          <li key={`${item.kind}-${item.at}-${i}`} className="py-3.5" style={{ borderBottom: LINE }} data-kind={item.kind === "event" ? item.event.kind : item.kind}>
            <Row item={item} scored={scored} />
          </li>
        ))}
      </ol>

      <Link
        href={`/journal/stock/${encodeURIComponent(note.ticker)}`}
        className="mt-6 flex items-center justify-between gap-3 rounded-[var(--pq-radius-card)] px-4 py-3 transition-colors hover:bg-[var(--pq-card-veil-strong)]"
        style={{ border: LINE, background: "var(--pq-card-veil)" }}
      >
        <span>
          <span className="block text-[14px] font-semibold" style={{ color: "var(--pq-ivory)" }}>
            이 종목 기록 전체
          </span>
          <span className="block text-[12px]" style={{ color: DIM }}>
            적기 전 기록까지 모두
          </span>
        </span>
        <ChevronRight aria-hidden className="h-4 w-4 shrink-0" style={{ color: DIM }} />
      </Link>
    </section>
  );
}

export default ResearchAfter;
