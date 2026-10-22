"use client";

/**
 * <YearRecapView /> — /mirror/year, one KST calendar year of the user's own
 * record (routes/year_recap.py).
 *
 * Sections, each dropped when it has nothing of its own:
 *   1. 숫자            — big numbers + a 12-month bar row (the phone redesigns'
 *                        "글 대신 막대와 큰 숫자", fff13e72 / b491e5b6)
 *   2. 일어나지 않은 거래 — what the year's pauses turned into
 *   3. 내 말            — up to three of the user's own sentences, verbatim
 *   4. 내 규칙          — only when the user adopted their lines
 *   5. 문 앞            — the year's 문 앞의 한 줄 counts (2026-10-15), only
 *                        when the user answered at the door that year
 *
 * Facts and the user's own words only: no score, grade, streak, rank or
 * "잘했어요", no comparison with anyone. Counts the backend sent are printed
 * as-is; nothing is computed here but bar heights. No italic. The disclaimer
 * is mounted by (dashboard)/layout.tsx (/mirror → behavior-mirror).
 */
import * as React from "react";

import type { YearRecapDoorway, YearRecapQuote, YearRecapResponse } from "@/lib/types";
import { displayName, normalizeTicker } from "@/lib/format";
import { VERDICT_LABEL, researchDate } from "@/lib/research";

const IVORY = "var(--pq-ivory)";
const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";
const LINE = "1px solid var(--pq-ivory-line)";
const TRACK = "rgba(var(--pq-ivory-rgb), 0.07)";
const BRONZE = "var(--pq-bronze)";
/** Tallest month bar, px. */
const BAR_MAX_PX = 56;

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="pt-6" style={{ borderTop: LINE }} data-testid={`year-${id}`}>
      <h2 id={id} className="text-pq-body font-semibold" style={{ color: IVORY }}>
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function BigNumber({ value, unit, label, sub }: { value: number | string; unit: string; label: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <div className="flex items-baseline gap-1">
        <span className="text-[30px] font-semibold leading-none tracking-[-0.01em] tabular-nums" style={{ color: IVORY }}>
          {value}
        </span>
        <span className="text-[14px]" style={{ color: DIM }}>{unit}</span>
      </div>
      <p className="mt-1.5 text-[13px]" style={{ color: DIM }}>{label}</p>
      {sub && <p className="mt-0.5 text-[12px] tabular-nums" style={{ color: DIM }}>{sub}</p>}
    </div>
  );
}

/** One thin bar per month, height ∝ count. The counts are in the aria label. */
function MonthBars({ months }: { months: YearRecapResponse["fills"]["by_month"] }) {
  const max = Math.max(1, ...months.map((m) => m.count));
  const label = months.map((m) => `${Number(m.month.slice(5))}월 ${m.count}건`).join(", ");
  return (
    <div role="img" aria-label={`달마다 체결 — ${label}`} data-testid="year-month-bars">
      <div className="flex items-end gap-[6px]" style={{ height: BAR_MAX_PX }}>
        {months.map((m) => (
          <div key={m.month} className="flex-1" style={{ height: "100%", display: "flex", alignItems: "flex-end" }}>
            <div
              className="w-full rounded-t-[3px]"
              style={{
                height: m.count ? Math.max(4, Math.round((m.count / max) * BAR_MAX_PX)) : 2,
                background: m.count ? BRONZE : TRACK,
              }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex gap-[6px]" aria-hidden>
        {months.map((m) => (
          <span key={m.month} className="flex-1 text-center text-[11px] tabular-nums" style={{ color: DIM }}>
            {Number(m.month.slice(5))}
          </span>
        ))}
      </div>
    </div>
  );
}

function NumbersSection({ data }: { data: YearRecapResponse }) {
  const { fills, pauses, records, holding } = data;
  const verdicts = records.verdicts;
  return (
    <Section id="numbers" title="숫자">
      <div className="grid grid-cols-2 gap-x-4 gap-y-6">
        <BigNumber value={fills.total} unit="건" label="기록한 체결" sub={`매수 ${fills.buys} · 매도 ${fills.sells}`} />
        <BigNumber value={pauses.started} unit="번" label="거래 전에 멈춤" />
        <BigNumber value={records.reasoned_fills} unit="건" label="이유를 적은 체결" />
        {holding.median_days !== null ? (
          <BigNumber value={holding.median_days} unit="일" label="판 것의 보유 기간 중앙값" sub={`매도 ${holding.sells}번`} />
        ) : (
          <BigNumber value={records.observation_notes} unit="개" label="관찰 노트" />
        )}
      </div>
      {fills.total > 0 && (
        <div className="mt-7">
          <MonthBars months={fills.by_month} />
          <p className="mt-2 text-[12.5px] tabular-nums" style={{ color: DIM }}>
            체결이 있던 달 {fills.months_active}개월 · 종목 {fills.tickers}개
          </p>
        </div>
      )}
      {(records.research_written > 0 || records.research_reviewed > 0 || records.observation_notes > 0) && (
        <p className="mt-4 text-[13px] tabular-nums" style={{ color: DIM }} data-testid="year-records-line">
          리서치 {records.research_written}편
          {records.research_reviewed > 0 &&
            ` · 채점 ${records.research_reviewed}편 (${VERDICT_LABEL.right} ${verdicts.right} · ${VERDICT_LABEL.wrong} ${verdicts.wrong} · ${VERDICT_LABEL.unknown} ${verdicts.unknown})`}
          {` · 관찰 노트 ${records.observation_notes}개`}
        </p>
      )}
    </Section>
  );
}

type Segment = { key: string; label: string; n: number; color: string };

function NotTakenSection({ pauses }: { pauses: YearRecapResponse["pauses"] }) {
  const segments: Segment[] = [
    { key: "never", label: "사려다 멈추고 사지 않음", n: pauses.never_bought, color: BRONZE },
    { key: "later", label: "멈췄다가 나중에 삼", n: pauses.bought_later_anyway, color: "rgba(var(--pq-bronze-rgb), 0.45)" },
    { key: "proceeded", label: "멈춘 뒤 진행", n: pauses.proceeded, color: "rgba(var(--pq-ivory-rgb), 0.35)" },
    { key: "other", label: "그 밖(매도 쪽 취소 · 미결)", n: Math.max(0, pauses.started - pauses.never_bought - pauses.bought_later_anyway - pauses.proceeded), color: TRACK },
  ].filter((s) => s.n > 0);
  return (
    <Section id="not-taken" title="일어나지 않은 거래">
      <BigNumber value={pauses.never_bought} unit="번" label={`멈춤 ${pauses.started}번 중, 사려다 멈추고 지금까지 사지 않은 것`} />
      <div className="mt-5 flex h-[10px] gap-[2px] overflow-hidden rounded-[4px]" aria-hidden>
        {segments.map((s) => (
          <div key={s.key} style={{ flexGrow: s.n, background: s.color }} />
        ))}
      </div>
      <ul className="mt-3 list-none space-y-1.5 p-0">
        {segments.map((s) => (
          <li key={s.key} className="flex items-center gap-2 text-[13px] tabular-nums" style={{ color: DIM }}>
            <span aria-hidden className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
            <span>{s.label}</span>
            <span className="ml-auto" style={{ color: IVORY }}>{s.n}번</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[12px]" style={{ color: DIM }}>
        샀는지는 여기에 남긴 체결로만 봐요. 기록하지 않은 매수는 알 수 없어요.
      </p>
    </Section>
  );
}

const QUOTE_LABEL: Record<YearRecapQuote["kind"], string> = {
  first_reason: "올해 처음 적은 이유",
  not_taken: "사지 않은 멈춤에 적은 이유",
  scored_thesis: "나중에 채점한 리서치",
};

function QuoteCard({ q }: { q: YearRecapQuote }) {
  // 접미사 없는 코드로 — 이름이 없을 때 화면에 ".KS" 가 남지 않게.
  const who = q.ticker ? displayName(normalizeTicker(q.ticker), q.name) : q.name;
  return (
    <figure className="m-0 rounded-[var(--pq-radius-card)] px-4 py-4" style={{ border: LINE }} data-testid={`year-quote-${q.kind}`}>
      <p className="text-[12.5px]" style={{ color: BRONZE }}>{QUOTE_LABEL[q.kind]}</p>
      <blockquote className="m-0 mt-2 text-[16px] leading-[1.6]" style={{ color: IVORY }}>
        &ldquo;{q.text}&rdquo;
      </blockquote>
      <figcaption className="mt-2 text-[12.5px] tabular-nums" style={{ color: DIM }}>
        {researchDate(q.date)}
        {who ? ` · ${who}` : ""}
        {q.kind === "scored_thesis" && q.verdict ? ` · 내 채점 ${VERDICT_LABEL[q.verdict]}` : ""}
      </figcaption>
    </figure>
  );
}

function RulesSection({ rules }: { rules: NonNullable<YearRecapResponse["rules"]> }) {
  const freq = rules.frequency;
  const scale = freq ? Math.max(freq.ceiling, ...freq.months.map((m) => m.count), 1) : 1;
  return (
    <Section id="rules" title="내 규칙">
      <p className="text-[13px]" style={{ color: DIM }}>{researchDate(rules.confirmed_on)}부터 센 것만이에요.</p>
      {freq && (
        <div className="mt-4">
          <p className="text-[14px] tabular-nums" style={{ color: IVORY }}>
            한 달에 매수·매도 {freq.ceiling}번 이하 — 선 안 {freq.within}달 · 선 밖 {freq.outside}달
          </p>
          <ul className="mt-3 list-none space-y-2 p-0">
            {freq.months.map((m) => (
              <li key={m.month} className="flex items-center gap-3 text-[12.5px] tabular-nums" style={{ color: DIM }}>
                <span className="w-9 shrink-0">{Number(m.month.slice(5))}월</span>
                <span className="relative h-[6px] flex-1 rounded-[3px]" style={{ background: TRACK }}>
                  <span
                    className="absolute inset-y-0 left-0 rounded-[3px]"
                    style={{ width: `${(m.count / scale) * 100}%`, background: m.over ? "var(--pq-ivory)" : BRONZE }}
                  />
                </span>
                <span className="w-16 shrink-0 text-right" style={{ color: IVORY }}>
                  {m.count}번{m.over ? " · 밖" : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {rules.holding && (
        <p className="mt-4 text-[14px] tabular-nums" style={{ color: IVORY }} data-testid="year-rules-holding">
          {rules.holding.sells > 0
            ? `매도 ${rules.holding.sells}번 중 ${rules.holding.min_days}일 전에 판 것 ${rules.holding.sooner}번`
            : "규칙을 정한 뒤 매도 기록 없음"}
        </p>
      )}
    </Section>
  );
}

/** The year at the door — how often the broker app was opened and why, and
 *  what the 살 게 있음 / 팔 게 있음 opens turned into. Counts only. */
function DoorwaySection({ d }: { d: YearRecapDoorway }) {
  const rows: Array<{ key: string; label: string; n: number }> = [
    { key: "look", label: "그냥 보기", n: d.intents.look },
    { key: "buy", label: "살 게 있음", n: d.intents.buy },
    { key: "sell", label: "팔 게 있음", n: d.intents.sell },
  ];
  const top = Math.max(1, ...rows.map((r) => r.n));
  const said = d.said.buy.n + d.said.sell.n;
  const asSaid = d.said.buy.as_said + d.said.sell.as_said;
  return (
    <Section id="doorway" title="문 앞">
      <BigNumber value={d.total} unit="번" label="증권 앱을 열 때 남긴 답" />
      <ul className="mt-5 list-none space-y-2 p-0">
        {rows.map((r) => (
          <li key={r.key} className="flex items-center gap-3 text-[12.5px] tabular-nums" style={{ color: DIM }}>
            <span className="w-[72px] shrink-0">{r.label}</span>
            <span className="relative h-[6px] flex-1 rounded-[3px]" style={{ background: TRACK }}>
              <span
                className="absolute inset-y-0 left-0 rounded-[3px]"
                style={{ width: `${(r.n / top) * 100}%`, background: BRONZE }}
              />
            </span>
            <span className="w-10 shrink-0 text-right" style={{ color: IVORY }}>{r.n}번</span>
          </li>
        ))}
      </ul>
      <ul className="mt-4 list-none space-y-1.5 p-0 text-[13px] tabular-nums" style={{ color: DIM }}>
        {d.look.n > 0 && (
          <li>그냥 보기 {d.look.n}번 중 {d.look.traded}번은 {d.follow_minutes}분 안에 체결이 있었어요.</li>
        )}
        {said > 0 && <li>살 게 · 팔 게 있다고 한 {said}번 중 말한 대로 체결 {asSaid}번</li>}
        {d.not_happened.n > 0 && (
          <li>
            종목을 적고 체결 없이 끝난 {d.not_happened.n}번 중 {d.later_days}일 안에 그 종목 체결{" "}
            {d.not_happened.later} · 체결 없음 {d.not_happened.never}
          </li>
        )}
      </ul>
    </Section>
  );
}

export function YearRecapView({ data }: { data: YearRecapResponse }) {
  if (data.empty) {
    return (
      <p className="text-[14px]" style={{ color: DIM }} data-testid="year-empty">
        {data.year}년에는 남긴 기록이 없어요.
      </p>
    );
  }
  return (
    <div className="space-y-8">
      <NumbersSection data={data} />
      {data.pauses.started > 0 && <NotTakenSection pauses={data.pauses} />}
      {data.quotes.length > 0 && (
        <Section id="words" title="내 말">
          {/* gap, not space-y: the figure's own m-0 out-ranks space-y's
              :where() margin, and the cards sat edge to edge. */}
          <div className="flex flex-col gap-3">
            {data.quotes.map((q) => <QuoteCard key={q.kind} q={q} />)}
          </div>
        </Section>
      )}
      {data.rules && <RulesSection rules={data.rules} />}
      {data.doorway && <DoorwaySection d={data.doorway} />}
    </div>
  );
}

export default YearRecapView;
