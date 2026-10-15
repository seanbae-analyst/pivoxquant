"use client";

/**
 * <ResearchSummary /> — what the user's own scoring adds up to.
 *
 * Two tables of counts (no rate, no grade, no proportion bars — a bar of
 * "맞음 / 전체" is a rate picture and invites ranking sources; legal-kr-fintech
 * review 2026-10-15):
 *   1. 판단 × 결과 — each scored reason (맞음/틀림) against the user's own
 *      fills on that stock since the note (판 뒤 이익 / 손실 / 본전 / 아직 안 팖).
 *      "틀렸는데 이익" piling up is something the user sees for themselves;
 *      we never name it.
 *   2. 출처별 — 맞음 / 틀림 / 모름 per "어디서 알게 됐나".
 * Colour only marks the row (맞음 bronze dot, 틀림 ivory dot) — never
 * red/green; the numbers carry everything.
 */
import * as React from "react";
import { INFO_SOURCE_LABEL, INFO_SOURCE_ORDER, OUTCOME_LABEL, VERDICT_LABEL } from "@/lib/research";
import { Caption } from "@/components/ui/editorial";
import type { ResearchOutcome, ResearchOverviewResponse, ResearchVerdict } from "@/lib/types";

const LINE = "1px solid var(--pq-ivory-line)";
const VERDICT_COLOR: Record<ResearchVerdict, string> = {
  right: "var(--pq-bronze)",
  wrong: "rgba(var(--pq-ivory-rgb), 0.55)",
  unknown: "rgba(var(--pq-ivory-rgb), 0.12)",
};

export function ResearchSummary({ data }: { data: ResearchOverviewResponse }) {
  const { judgment, unknown, by_source: bySource, counts } = data;
  const scoredReasons =
    Object.values(judgment.right).reduce((a, b) => a + b, 0) +
    Object.values(judgment.wrong).reduce((a, b) => a + b, 0) +
    unknown;

  if (counts.scored === 0) {
    return (
      <section aria-label="채점 결과" data-testid="research-summary-empty">
        <Caption>
          아직 채점한 리서치가 없어요. 다시 볼 날 채점하면, 그때 본 이유가 맞았는지와 본인 체결 손익을
          여기서 나란히 보여 드려요.
        </Caption>
      </section>
    );
  }

  const cols: ResearchOutcome[] = ["gain", "loss", ...(judgment.right.flat + judgment.wrong.flat > 0 ? (["flat"] as const) : []), "open"];
  const sources = [...INFO_SOURCE_ORDER, "none" as const].filter((s) => {
    const c = bySource[s];
    return c && c.right + c.wrong + c.unknown > 0;
  });

  return (
    <section aria-label="채점 결과" data-testid="research-summary">
      <div className="text-pq-body font-semibold text-[var(--pq-ivory)]">
        채점한 이유 <span className="tabular-nums">{scoredReasons}</span>개
      </div>

      {/* 판단 × 결과 */}
      <div className="mt-3 overflow-hidden rounded-[var(--pq-radius-card)]" style={{ border: LINE }}>
        <table className="w-full table-fixed text-pq-body-sm tabular-nums" data-testid="research-judgment">
          <thead>
            <tr style={{ borderBottom: LINE }}>
              <th className="w-[30%] px-3 py-2 text-left font-normal text-[var(--pq-ivory-faint)]" scope="col">
                <span className="sr-only">이유</span>
              </th>
              {cols.map((c) => (
                <th key={c} className="px-2 py-2 text-right text-pq-caption font-normal text-[var(--pq-ivory-faint)]" scope="col">
                  {OUTCOME_LABEL[c]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["right", "wrong"] as const).map((v, i) => (
              <tr key={v} style={i === 0 ? { borderBottom: LINE } : undefined}>
                <th scope="row" className="px-3 py-2.5 text-left font-normal">
                  <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[var(--pq-ivory-strong)]">
                    <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: VERDICT_COLOR[v] }} />
                    이유 {VERDICT_LABEL[v]}
                  </span>
                </th>
                {cols.map((c) => (
                  <td
                    key={c}
                    className="px-2 py-2.5 text-right text-pq-body font-semibold"
                    style={{ color: judgment[v][c] > 0 ? "var(--pq-ivory)" : "var(--pq-ivory-faint)" }}
                  >
                    {judgment[v][c]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Caption className="mt-2">
        {unknown > 0 ? `모름 ${unknown}개는 빼고 셌어요. ` : ""}결과는 이 서비스에 기록된 본인 체결만 봐요 — 리서치를 쓴
        날 이후 그 종목을 판 기록의 손익 합계의 부호예요. 리서치와 무관하게 산 수량의 매도도 포함하고, 이유가 맞았다는
        증거는 아니에요.
      </Caption>

      {/* 출처별 */}
      {sources.length > 0 && (
        <div className="mt-6">
          <div className="text-pq-body-sm font-semibold text-[var(--pq-ivory)]">어디서 알게 됐나별로</div>
          <ul className="mt-2 list-none space-y-1 p-0" data-testid="research-by-source">
            {sources.map((s) => {
              const c = bySource[s];
              return (
                <li key={s} className="flex items-baseline justify-between gap-3 py-1 text-pq-body-sm" style={{ borderBottom: LINE }}>
                  <span className="text-[var(--pq-ivory-strong)]">{INFO_SOURCE_LABEL[s]}</span>
                  <span className="tabular-nums text-pq-caption text-[var(--pq-ivory-dim)]">
                    맞음 {c.right} · 틀림 {c.wrong} · 모름 {c.unknown}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}

export default ResearchSummary;
