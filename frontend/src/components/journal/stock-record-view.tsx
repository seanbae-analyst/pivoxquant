/**
 * <StockRecordView /> — 종목별 내 기록 (2026-10-25).
 *
 * CEO "토스처럼 … 종목별로 정리": Toss explains why a stock moved; this app
 * cannot and does not (no vendor price on screen, and per-stock reading is
 * the 투자자문 line). What only this app holds is the user's own trail on a
 * name, so that is the page: what they bought and sold and at what price,
 * the pauses before it — and the ones no buy followed — the research they
 * wrote cold and how they scored it, the notes they left. Newest first,
 * grouped by month (KST).
 *
 * Pure view over GET /api/stock-record/<ticker>. Counts, never rates; no
 * score, no label, no verdict on the stock. The user's words are printed as
 * written.
 */
import * as React from "react";
import Link from "next/link";
import { ChevronRight, ExternalLink } from "lucide-react";

import { displayTicker, fmtMoneyKo, parseIsoUtc } from "@/lib/format";
import type { StockRecordEvent, StockRecordResponse } from "@/lib/types";

const LINE = "1px solid var(--pq-ivory-line)";
const DIM = "var(--pq-ivory-dim)";

function kst(iso: string | null): Date | null {
  return parseIsoUtc(iso);
}

/** "2026년 6월" in KST — the month a group heads. */
export function monthKey(iso: string | null): string {
  const d = kst(iso);
  if (!d) return "날짜 없음";
  return d.toLocaleDateString("ko-KR", { year: "numeric", month: "long", timeZone: "Asia/Seoul" });
}

function dayLabel(iso: string | null): string {
  const d = kst(iso);
  if (!d) return "—";
  return d.toLocaleDateString("ko-KR", { month: "long", day: "numeric", timeZone: "Asia/Seoul" });
}

function money(v: number | null | undefined, currency: string | null | undefined): string {
  return fmtMoneyKo(v ?? null, currency === "KRW" ? "KRW" : "USD");
}

function shares(n: number): string {
  return `${n.toLocaleString("ko-KR", { maximumFractionDigits: 4 })}주`;
}

const STATUS_LABEL: Record<string, string> = {
  proceeded: "진행",
  cancelled: "취소",
  pending: "미결",
  ready: "미결",
  expired: "만료",
};

const VERDICT_LABEL: Record<string, string> = { right: "맞음", wrong: "틀림", unknown: "모름" };

function Chip({ children, strong = false }: { children: React.ReactNode; strong?: boolean }) {
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px]"
      style={{
        color: strong ? "var(--pq-bronze)" : DIM,
        border: `1px solid ${strong ? "var(--pq-bronze)" : "var(--pq-ivory-line)"}`,
      }}
    >
      {children}
    </span>
  );
}

function kindTitle(e: StockRecordEvent): string {
  switch (e.kind) {
    case "fill":
      return e.side === "buy" ? "샀어요" : "팔았어요";
    case "registered":
      return "보유 등록";
    case "pause":
      return e.side === "exit" ? "팔기 전 멈춤" : "사기 전 멈춤";
    case "research":
      return "리서치";
    case "note":
      return "관찰 노트";
    case "filing":
      return e.label;
  }
}

function EventBody({ e }: { e: StockRecordEvent }) {
  switch (e.kind) {
    case "fill":
      return (
        <p className="mt-1 text-[14px] tabular-nums" style={{ color: "var(--pq-ivory)" }}>
          {shares(e.shares)} · {money(e.price, e.currency)}
        </p>
      );
    case "registered":
      return (
        <p className="mt-1 text-[14px] tabular-nums" style={{ color: "var(--pq-ivory)" }}>
          {shares(e.shares)} · 평균가 {money(e.price, e.currency)}
        </p>
      );
    case "pause":
      return (
        <p className="mt-1 text-[14px] leading-relaxed [word-break:keep-all]" style={{ color: "var(--pq-ivory)" }}>
          {e.rationale}
        </p>
      );
    case "research":
      return (
        <div className="mt-1 space-y-1.5">
          <ul className="list-none space-y-1 p-0">
            {e.theses.map((t, i) => (
              <li key={i} className="flex items-start justify-between gap-3 text-[14px]" style={{ color: "var(--pq-ivory)" }}>
                <span className="[word-break:keep-all]">{t}</span>
                {e.verdicts[i] && <Chip>{VERDICT_LABEL[e.verdicts[i]] ?? e.verdicts[i]}</Chip>}
              </li>
            ))}
          </ul>
          {e.invalidation && (
            <p className="text-[12.5px] [word-break:keep-all]" style={{ color: DIM }}>
              틀렸다고 볼 신호 · {e.invalidation}
            </p>
          )}
        </div>
      );
    case "note":
      return (
        <div className="mt-1">
          <p className="text-[14px] leading-relaxed [word-break:keep-all]" style={{ color: "var(--pq-ivory)" }}>
            {e.body}
          </p>
          {e.tags.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {e.tags.map((t) => (
                <Chip key={t}>{t}</Chip>
              ))}
            </div>
          )}
        </div>
      );
    case "filing":
      return (
        <a
          href={e.url}
          target="_blank"
          rel="noopener noreferrer"
          className="pq-hit mt-1 inline-flex items-center gap-1 text-[13px] underline-offset-2 hover:underline"
          style={{ color: DIM }}
        >
          {e.form} · 원문 보기
          <ExternalLink aria-hidden className="h-3 w-3" />
        </a>
      );
  }
}

function EventChips({ e }: { e: StockRecordEvent }) {
  if (e.kind === "fill" && e.after_pause) return <Chip>멈춤 뒤</Chip>;
  if (e.kind === "filing") return <Chip>공시</Chip>;
  if (e.kind === "pause") {
    return (
      <span className="flex shrink-0 gap-1.5">
        {e.status && STATUS_LABEL[e.status] && <Chip>{STATUS_LABEL[e.status]}</Chip>}
        {e.bought_after === false && <Chip strong>그 뒤로 사지 않음</Chip>}
      </span>
    );
  }
  if (e.kind === "research") {
    if (e.reviewed_at) return <Chip>채점함</Chip>;
    if (e.due) return <Chip strong>다시 볼 날</Chip>;
    if (e.review_on) return <Chip>{dayLabel(e.review_on)}에 다시 봄</Chip>;
  }
  return null;
}

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

export function StockRecordView({ data }: { data: StockRecordResponse }) {
  const title = data.name || displayTicker(data.ticker, null);
  const c = data.counts;
  const groups: { month: string; items: StockRecordEvent[] }[] = [];
  for (const e of data.events) {
    const m = monthKey(e.at);
    const last = groups[groups.length - 1];
    if (last && last.month === m) last.items.push(e);
    else groups.push({ month: m, items: [e] });
  }
  const q = encodeURIComponent(data.ticker);
  const filingSources = new Set(data.events.flatMap((e) => (e.kind === "filing" ? [e.source] : [])));
  const fr = data.filing_reaction;
  const krBasis = fr?.date_basis === "kr";

  return (
    <article data-testid="stock-record">
      <header>
        <h1 className="text-[26px] font-semibold leading-tight" style={{ color: "var(--pq-ivory)" }}>
          {title}
        </h1>
        <p className="mt-1 text-[13px] tabular-nums" style={{ color: DIM }}>
          {/* The code, not the name again — the heading already says it. */}
          {data.ticker.replace(/\.(KS|KQ|KRX)$/i, "")}
          {data.holding
            ? ` · 보유 ${shares(data.holding.shares)}${
                data.holding.avg_cost != null ? ` · 평균가 ${money(data.holding.avg_cost, data.holding.currency)}` : ""
              }`
            : " · 지금 보유하지 않음"}
        </p>
      </header>

      <section aria-label="기록 수" className="mt-5 grid grid-cols-2 gap-2.5">
        <Stat n={c.fills} label="체결" sub={c.fills ? `산 것 ${c.buys} · 판 것 ${c.sells}` : undefined} />
        <Stat n={c.pauses} label="멈춤" sub={c.not_taken ? `그 뒤로 안 산 것 ${c.not_taken}` : undefined} />
        <Stat n={c.research} label="리서치" />
        <Stat n={c.notes} label="관찰 노트" />
      </section>

      {fr && fr.earnings > 0 && (
        <section aria-label="실적 발표 뒤 체결" className="mt-3 text-[13px] leading-relaxed" data-testid="filing-reaction">
          <p className="tabular-nums" style={{ color: "var(--pq-ivory)" }}>
            실적 발표 {fr.earnings}번 · 그다음 날부터 {fr.window_days}일 안에 산 것 {fr.buys_after}번 · 판 것{" "}
            {fr.sells_after}번
          </p>
          <p className="mt-0.5 text-[12px] [word-break:keep-all]" style={{ color: DIM }}>
            {krBasis ? "한국 날짜로 셌어요." : "미국 날짜로 셌어요."} 발표 당일 체결은 발표 전인지 뒤인지 알 수 없어
            빼요.
            {fr.untimed_fills > 0 && ` 시각 없이 날짜만 있는 체결 ${fr.untimed_fills}건도 빼고 셌어요.`}
          </p>
        </section>
      )}

      {data.events.length === 0 ? (
        <p className="mt-8 text-[14px]" style={{ color: DIM }} data-testid="stock-record-empty">
          이 종목에 남긴 기록이 아직 없어요.
        </p>
      ) : (
        <div className="mt-7 space-y-6">
          {groups.map((g) => (
            <section key={g.month} aria-label={g.month}>
              <h2 className="text-[13px] font-semibold" style={{ color: "var(--pq-bronze)" }}>
                {g.month}
              </h2>
              <ol className="mt-2 list-none p-0" style={{ borderTop: LINE }}>
                {g.items.map((e, i) => (
                  <li key={`${e.kind}-${e.at}-${i}`} className="py-3.5" style={{ borderBottom: LINE }} data-kind={e.kind}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[12.5px]" style={{ color: DIM }}>
                        {dayLabel(e.at)} · <span style={{ color: "var(--pq-ivory)" }}>{kindTitle(e)}</span>
                      </span>
                      <EventChips e={e} />
                    </div>
                    <EventBody e={e} />
                  </li>
                ))}
              </ol>
            </section>
          ))}
          {filingSources.size > 0 && (
            <p className="text-[12px]" style={{ color: DIM }} data-testid="filing-source">
              {filingSources.has("SEC EDGAR") && "공시 출처: SEC EDGAR · 공시 날짜는 미국 날짜예요."}
              {filingSources.has("DART") && "공시 출처: 금융감독원 전자공시(DART)."}
            </p>
          )}
        </div>
      )}

      <nav aria-label="이 종목으로" className="mt-8 grid gap-2">
        {[
          { href: `/pre-trade?ticker=${q}`, label: "이 종목 멈춤 시작", sub: "사기 전에 질문 7개" },
          { href: `/journal/research?ticker=${q}`, label: "리서치 쓰기", sub: "이유와 틀렸다고 볼 신호" },
        ].map((a) => (
          <Link
            key={a.href}
            href={a.href}
            className="flex items-center justify-between gap-3 rounded-[var(--pq-radius-card)] px-4 py-3 transition-colors hover:bg-[var(--pq-card-veil-strong)]"
            style={{ border: LINE, background: "var(--pq-card-veil)" }}
          >
            <span>
              <span className="block text-[14px] font-semibold" style={{ color: "var(--pq-ivory)" }}>
                {a.label}
              </span>
              <span className="block text-[12px]" style={{ color: DIM }}>
                {a.sub}
              </span>
            </span>
            <ChevronRight aria-hidden className="h-4 w-4 shrink-0" style={{ color: DIM }} />
          </Link>
        ))}
      </nav>
    </article>
  );
}

export default StockRecordView;
