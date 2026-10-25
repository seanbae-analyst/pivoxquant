/**
 * MyRulesPanel — 「내 규칙」 on /mirror (2026-10-14).
 *
 * The onboarding answers, read back as plain lines, with where the user's own
 * record sits against each — from `rules` in GET /api/mirror-home
 * (services/profile/my_rules.py).
 *
 * Two states:
 *  - Not adopted (`confirmed: false`) — "온보딩 때 말한 나". The onboarding
 *    question asked how the user USUALLY trades; that is a self-description,
 *    not a rule. The lines and counts are shown without 선 안/밖, with one
 *    explicit choice: adopt them as my lines (POST /api/profile/rules/confirm)
 *    or change them (the existing five-question retake).
 *  - Adopted — "내 규칙": each line gets a 선 안 / 선 밖 status.
 *
 * Every threshold is the user's bucket, never ours, and each line is crossed
 * in one direction only (more trades, sooner sells, fewer names).
 *
 * Legal / product posture: a fact against the user's own number — never a
 * score, grade, streak or "지키세요". "선 밖" is bronze, not the carmine
 * alarm hue: crossing your own line is information, not an alert. The −10%
 * answer is shown but not counted (no prices are read). No italic.
 */
import * as React from "react";
import Link from "next/link";
import { mutate } from "swr";

import { API } from "@/lib/endpoints";
import { confirmMyRules } from "@/lib/hooks";
import type { MirrorHomeResponse, MyRuleItem, MyRuleMonth, MyRuleStatus } from "@/lib/types";

const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";
const RETAKE_HREF = "/onboarding?retake=1";
const LINE_STROKE = "1px dashed rgba(var(--pq-ivory-rgb), 0.45)";

const STATUS_LABEL: Record<MyRuleStatus, string> = {
  within: "선 안",
  outside: "선 밖",
  no_data: "기록 없음",
  no_line: "선 없음",
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
function MonthBars({
  months,
  ceiling,
  adopted,
}: {
  months: MyRuleMonth[];
  ceiling: number | null;
  /** Adopted lines are "정해 둔 선" and months past them "선 밖"; before
   *  that the line is only "답한 선" and no month is called outside. */
  adopted: boolean;
}) {
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
          {adopted ? "정해 둔 선" : "답한 선"} {ceiling}번
        </div>
      )}
      <figcaption className="sr-only">
        월별 매수·매도 횟수
        <ul>
          {months.map((m) => (
            <li key={m.month}>
              {monthLabel(m)} {m.count}번{adopted && m.over ? " (선 밖)" : ""}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}

function RuleRow({ rule, adopted }: { rule: MyRuleItem; adopted: boolean }) {
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
        {adopted && <StatusChip status={rule.status} />}
      </div>
      <p className="mt-1 text-[14px] leading-snug" style={{ color: "var(--pq-ivory)" }}>
        {rule.line}
      </p>
      <p className="mt-1 text-[12.5px] leading-relaxed" style={{ color: DIM }}>
        {rule.observed}
      </p>
      {rule.id === "frequency" && rule.months && (
        <MonthBars months={rule.months} ceiling={rule.ceiling ?? null} adopted={adopted} />
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

/** "이 답을 내 선으로 삼기" — the one explicit act that turns answers into rules. */
function AdoptActions() {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const adopt = async () => {
    setBusy(true);
    setError(null);
    try {
      await confirmMyRules();
      await mutate(API.mirror.home);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={adopt}
          disabled={busy}
          className="px-4 py-2 text-[13px] font-semibold disabled:opacity-60"
          style={{
            borderRadius: "var(--pq-radius-cta)",
            backgroundColor: "var(--pq-bronze)",
            color: "var(--pq-ink)",
          }}
        >
          {busy ? "저장하는 중…" : "이 답을 내 선으로 삼기"}
        </button>
        <Link
          href={RETAKE_HREF}
          className="text-[12.5px] underline underline-offset-2"
          style={{ color: "var(--pq-bronze)" }}
        >
          답 고치기
        </Link>
      </div>
      {error && (
        <p className="mt-2 text-[12px]" role="alert" style={{ color: DIM }}>
          {error}
        </p>
      )}
    </div>
  );
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

  if (!rules.available) {
    return (
      <section {...frame} aria-label="내 규칙" data-testid="my-rules-panel">
        <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
          내 규칙
        </div>
        <p className="mt-2 text-[13px] leading-relaxed" style={{ color: DIM }}>
          온보딩 다섯 문항에 답하면, 그 답을 내 선으로 삼을 수 있어요. 그다음부터 거래가 그 선
          안에 있는지 내 기록만으로 세어 보여드려요.
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

  const adopted = rules.confirmed;
  return (
    <section
      {...frame}
      aria-label={adopted ? "내 규칙" : "온보딩 때 말한 나"}
      data-testid="my-rules-panel"
      data-adopted={adopted ? "true" : "false"}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
          {adopted ? "내 규칙" : "온보딩 때 말한 나"}
        </div>
        {adopted && rules.confirmed_on && (
          <span className="text-[11px] tabular-nums" style={{ color: DIM }}>
            {rules.confirmed_on}부터
          </span>
        )}
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed" style={{ color: DIM }}>
        {adopted
          ? summaryLine(rules.counted, rules.outside)
          : "온보딩에서 평소 이렇게 한다고 답했어요. 이 답을 내 선으로 삼으면 그때부터 선 안·밖을 세고, 이번 달 체결이 선을 넘으면 체결 알림에 한 줄을 붙여 드려요."}
      </p>
      {!adopted && <AdoptActions />}
      <ul className="mt-3" style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
        {rules.items.map((rule) => (
          <RuleRow key={rule.id} rule={rule} adopted={adopted} />
        ))}
      </ul>
      {adopted && (
        <p className="mt-3 text-[11.5px] leading-relaxed" style={{ color: DIM }}>
          선은 온보딩에서 답한 내용 그대로예요. 시세는 쓰지 않고 내 거래 기록만 셉니다. 답을
          바꾸면 새 선을 다시 확정해요.{" "}
          <Link
            href={RETAKE_HREF}
            className="pq-hit underline underline-offset-2"
            style={{ color: "var(--pq-bronze)" }}
          >
            선 다시 정하기
          </Link>
        </p>
      )}
    </section>
  );
}

export default MyRulesPanel;
