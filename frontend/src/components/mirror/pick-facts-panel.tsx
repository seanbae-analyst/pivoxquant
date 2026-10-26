"use client";

/**
 * PickFactsPanel — 「내가 고른 회사들」 on /mirror (2026-10-25).
 *
 * GET /api/pick-facts: for each stock the user first bought in the last year,
 * the latest annual numbers that were already filed BEFORE the buy day (SEC
 * companyfacts · DART 주요계정) — and three counts: net loss, revenue down on
 * the year before, liabilities over equity. A price-free factor fingerprint of
 * the user's own picks (services/pick_facts).
 *
 * Legal / product posture: counts and names only — no score, grade, verdict,
 * "좋은 회사", rate or advice. Numbers filed after the buy are never used, and
 * the card says so. No market data. No italic. The disclaimer is mounted by
 * (dashboard)/layout.
 */
import * as React from "react";

import { usePickFacts } from "@/lib/hooks";
import type { PickFactsResponse } from "@/lib/types";

const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";
const NAMES_SHOWN = 4;

const ROWS: { key: keyof PickFactsResponse["counts"]; label: string }[] = [
  { key: "net_loss", label: "순손실이었던 곳" },
  { key: "revenue_down", label: "매출이 전년보다 줄었던 곳" },
  { key: "liabilities_over_equity", label: "부채가 자본보다 많았던 곳" },
];

function names(data: PickFactsResponse, key: keyof PickFactsResponse["counts"]): string {
  const hit = data.picks.filter((p) => p[key]).map((p) => p.name || p.ticker.replace(/\.(KS|KQ|KRX)$/i, ""));
  if (hit.length === 0) return "";
  const shown = hit.slice(0, NAMES_SHOWN).join(", ");
  return hit.length > NAMES_SHOWN ? `${shown} 외 ${hit.length - NAMES_SHOWN}곳` : shown;
}

export function PickFactsView({ data, bordered = true }: { data: PickFactsResponse; bordered?: boolean }) {
  if (data.picked === 0) return null;
  const notes: string[] = [];
  if (data.pending > 0) notes.push(`${data.pending}곳은 숫자를 받는 중이에요.`);
  if (data.no_facts > 0) notes.push(`${data.no_facts}곳은 산 날 전에 공시된 연간 숫자를 찾지 못했어요.`);
  return (
    <section
      className={bordered ? "rounded-[var(--pq-radius-card)] p-4" : undefined}
      style={bordered ? { border: "1px solid var(--pq-ivory-line)" } : undefined}
      aria-label="내가 고른 회사들"
      data-testid="pick-facts"
    >
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
          내가 고른 회사들
        </div>
        <span className="text-[12px]" style={{ color: DIM }}>
          최근 1년 처음 산 {data.picked}종목
        </span>
      </div>

      {data.with_facts > 0 ? (
        <ul className="mt-3 list-none space-y-2.5 p-0">
          {ROWS.map((r) => (
            <li key={r.key} data-testid={`pick-facts-${r.key}`}>
              <div className="flex items-baseline justify-between gap-3 text-[13.5px]" style={{ color: "var(--pq-ivory)" }}>
                <span className="[word-break:keep-all]">{r.label}</span>
                <span className="shrink-0 tabular-nums">
                  {data.counts[r.key]}
                  <span style={{ color: DIM }}> / {data.with_facts}곳</span>
                </span>
              </div>
              {data.counts[r.key] > 0 && (
                <p className="mt-0.5 text-[12px] [word-break:keep-all]" style={{ color: DIM }}>
                  {names(data, r.key)}
                </p>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-[13px] leading-relaxed" style={{ color: DIM }}>
          아직 셀 수 있는 숫자가 없어요.
        </p>
      )}

      <p className="mt-3 text-[12px] leading-relaxed [word-break:keep-all]" style={{ color: DIM }}>
        산 날보다 먼저 공시된 가장 최근 연간 보고의 숫자예요. 산 뒤에 나온 숫자는 쓰지 않아요.
        {notes.length > 0 && ` ${notes.join(" ")}`}
        {data.sources.length > 0 && ` 출처: ${data.sources.join(" · ")}.`}
      </p>
    </section>
  );
}

export function PickFactsPanel({ bordered = true }: { bordered?: boolean }) {
  const { data } = usePickFacts();
  if (!data || !data.ok) return null;
  return <PickFactsView data={data} bordered={bordered} />;
}

export default PickFactsPanel;
