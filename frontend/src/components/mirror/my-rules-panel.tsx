/**
 * MyRulesPanel — 「내 규칙」 on /mirror (2026-10-14).
 *
 * The five onboarding answers, read back as the lines the user drew for
 * themselves, with where their own record sits against each — from
 * `rules` in GET /api/mirror-home (services/profile/my_rules.py).
 *
 * The radar shows the same gap as a shape; this block says it in the user's
 * own numbers ("한 달에 5번 이하" · "이번 달 6번"). Every threshold is the
 * user's bucket, never ours. Changing a line = answering the five questions
 * again (/onboarding?retake=1).
 *
 * Legal / product posture: a fact against the user's own number — 선 안 /
 * 선 밖 — never a score, grade, streak or "지키세요". "선 밖" is bronze, not
 * the carmine alarm hue: crossing your own line is information, not an
 * alert. The −10% answer is shown but not counted (no prices are read).
 * No italic.
 */
import * as React from "react";
import Link from "next/link";

import type { MirrorHomeResponse, MyRuleItem, MyRuleMonth, MyRuleStatus } from "@/lib/types";

const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";
const RETAKE_HREF = "/onboarding?retake=1";
const LINE_STROKE = "1px dashed rgba(var(--pq-ivory-rgb), 0.45)";

const STATUS_LABEL: Record<MyRuleStatus, string> = {
  within: "선 안",
  outside: "선 밖",
  no_data: "기록 없음",
  no_line: "상한 없음",
  not_counted: "세지 않음",
};

function StatusChip({ status }: { status: MyRuleStatus }) {
  const outside = status === "outside";
  return (
    <span
      className="shrink-0 rounded-full px-2 py-0.5 text-[11px]"
      style={{
        color: outside ? "var(--pq-bronze)" : DIM,
        border: `1px solid ${outside ? "var(--pq-bronze)" : "var(--pq-ivory-line)"}`,
      }}
      data-testid="my-rule-status"
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

/** "2026-08" → "8월"; the running month reads "이번 달". */
function monthLabel(m: MyRuleMonth): string {
  if (m.partial) return "이번 달";
  return `${Number(m.month.slice(5, 7))}월`;
}

/**
 * Monthly fill counts as thin bars with the user's ceiling as one threshold
 * line. One series, one hue; only the running month carries a number (the
 * sentence above already says it; the rest are in each bar's title and the
 * screen-reader list). Fewer than two months is not a chart — the sentence is.
 */
function MonthBars({ months, ceiling }: { months: MyRuleMonth[]; ceiling: number | null }) {
  if (months.length < 2) return null;
  const top = Math.max(ceiling ?? 0, ...months.map((m) => m.count), 1) * 1.15;
  const pct = (n: number) => `${(n / top) * 100}%`;
  return (
    <figure className="mt-3" data-testid="my-rule-months">
      <div className="relative h-14" aria-hidden>
        <div className="absolute inset-0 flex items-end gap-[2px]">
          {months.map((m) => (
            <div key={m.month} className="relative flex h-full flex-1 items-end justify-center">
              {m.partial && (
                <span
                  className="absolute text-[10.5px] tabular-nums"
                  style={{ bottom: `calc(${pct(m.count)} + 2px)`, color: "var(--pq-ivory)" }}
                >
                  {m.count}
                </span>
              )}
              <div
                className="w-full max-w-[18px] rounded-t-[4px]"
                style={{
                  height: m.count > 0 ? pct(m.count) : 0,
                  background: "var(--pq-bronze)",
                  opacity: m.partial ? 1 : 0.6,
                }}
                title={`${m.month} · ${m.count}번`}
              />
            </div>
          ))}
        </div>
        {ceiling !== null && (
          <div
            className="absolute inset-x-0"
            style={{ bottom: pct(ceiling), borderTop: LINE_STROKE }}
          />
        )}
        <div className="absolute inset-x-0 bottom-0" style={{ borderTop: "1px solid var(--pq-ivory-line)" }} />
      </div>
      <div className="mt-1 flex gap-[2px]" aria-hidden>
        {months.map((m) => (
          <span key={m.month} className="flex-1 text-center text-[10.5px]" style={{ color: DIM }}>
            {monthLabel(m)}
          </span>
        ))}
      </div>
      {/* The threshold is named under the plot, not at the end of its line,
          where it collided with the running month's count at phone width. */}
      {ceiling !== null && (
        <div className="mt-2 flex items-center gap-1.5 text-[10.5px]" style={{ color: DIM }} aria-hidden>
          <span className="inline-block w-4" style={{ borderTop: LINE_STROKE }} />
          정해 둔 선 {ceiling}번
        </div>
      )}
      <figcaption className="sr-only">
        월별 매수·매도 횟수
        <ul>
          {months.map((m) => (
            <li key={m.month}>
              {monthLabel(m)} {m.count}번{m.over ? " (선 밖)" : ""}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}

function RuleRow({ rule }: { rule: MyRuleItem }) {
  return (
    <li
      className="py-3.5"
      style={{ borderBottom: "1px solid var(--pq-ivory-line)" }}
      data-testid={`my-rule-${rule.id}`}
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[11.5px]" style={{ color: DIM }}>
          {rule.title}
        </span>
        <StatusChip status={rule.status} />
      </div>
      <p className="mt-1 text-[14px] leading-snug" style={{ color: "var(--pq-ivory)" }}>
        {rule.line}
      </p>
      <p className="mt-1 text-[12.5px] leading-relaxed" style={{ color: DIM }}>
        {rule.observed}
      </p>
      {rule.id === "frequency" && rule.months && (
        <MonthBars months={rule.months} ceiling={rule.ceiling ?? null} />
      )}
    </li>
  );
}

/** One fact sentence over the counted lines — no ratio, no grade. */
function summaryLine(counted: number, outside: number): string {
  if (counted === 0) return "아직 셀 수 있는 기록이 없어요. 거래가 쌓이면 여기서 선과 나란히 보여드려요.";
  if (outside === 0) return `지금 셀 수 있는 선 ${counted}개 모두 기록이 선 안에 있어요.`;
  return `지금 셀 수 있는 선 ${counted}개 중 ${outside}개에서 기록이 선 밖에 있어요.`;
}

export function MyRulesPanel({
  data,
  bordered = true,
}: {
  data: MirrorHomeResponse;
  /** The desktop column frames it; the phone card is already a frame. */
  bordered?: boolean;
}) {
  const rules = data.rules;
  if (!rules) return null;

  const frame = bordered
    ? { className: "rounded-[var(--pq-radius-card)] p-4", style: { border: "1px solid var(--pq-ivory-line)" } }
    : { className: undefined, style: undefined };

  const kicker = (
    <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
      내 규칙
    </div>
  );

  if (!rules.available) {
    return (
      <section {...frame} aria-label="내 규칙" data-testid="my-rules-panel">
        {kicker}
        <p className="mt-2 text-[13px] leading-relaxed" style={{ color: DIM }}>
          온보딩 다섯 문항에 답하면, 그 답이 내 규칙이 돼요. 이후 거래가 그 선 안에 있는지
          내 기록만으로 세어 보여드려요.
        </p>
        <Link
          href={RETAKE_HREF}
          className="mt-2 inline-block text-[12.5px] underline underline-offset-2"
          style={{ color: "var(--pq-bronze)" }}
        >
          다섯 문항 답하기 →
        </Link>
      </section>
    );
  }

  return (
    <section {...frame} aria-label="내 규칙" data-testid="my-rules-panel">
      {kicker}
      <p className="mt-1.5 text-[13px] leading-relaxed" style={{ color: DIM }}>
        {summaryLine(rules.counted, rules.outside)}
      </p>
      <ul className="mt-2" style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
        {rules.items.map((rule) => (
          <RuleRow key={rule.id} rule={rule} />
        ))}
      </ul>
      <p className="mt-3 text-[11.5px] leading-relaxed" style={{ color: DIM }}>
        선은 온보딩에서 답한 내용 그대로예요. 시세는 쓰지 않고 내 거래 기록만 셉니다.{" "}
        <Link
          href={RETAKE_HREF}
          className="underline underline-offset-2"
          style={{ color: "var(--pq-bronze)" }}
        >
          선 다시 정하기
        </Link>
      </p>
    </section>
  );
}

export default MyRulesPanel;
