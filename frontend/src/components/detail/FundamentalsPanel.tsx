"use client";

/**
 * Zone2 ANALYTICS — Fundamentals.
 *
 * Collapses the former two cards (Valuation / Liquidity) into ONE dense
 * StatRow grid (Bloomberg-terminal density). All 8 metrics preserved:
 * P/E · EPS · Market cap · Beta · Avg volume · Profit margin · Revenue
 * growth · Debt/Equity. Two columns on desktop, one on mobile.
 *
 * KRW-aware market cap via fmtMcap; tone colours (margin / rev growth)
 * follow KR convention (carmine positive / indigo negative).
 */

import { StatRow } from "@/components/ui/editorial";
import { SectionHeading, EmptyNote } from "./shared";
import type { SignalDetail } from "./types";
import { fmtMcap } from "./types";

function num(v: number | null | undefined): boolean {
  return v != null && Number.isFinite(v);
}

export function FundamentalsPanel({
  signal,
  mcap,
  krw,
  loading = false,
}: {
  signal: SignalDetail | undefined;
  mcap: number | null;
  krw: boolean;
  loading?: boolean;
}) {
  const s = signal?.snapshot;
  // KR tickers: KIS license serves PER/EPS/PBR/시총 but not margin / rev
  // growth / D-E. The backend flags this so we can explain the three "—"
  // rows below as license-bounded (not a transient error / not broken).
  const limited = !!s?.fundamentals_limited;
  // If the snapshot is entirely empty (e.g. KR low-data ticker) collapse the
  // section to a single restrained note rather than a wall of em-dashes.
  const anyData =
    !!s &&
    (num(s.pe_ratio) ||
      num(s.eps) ||
      num(mcap) ||
      num(s.beta) ||
      num(s.avg_volume) ||
      num(s.profit_margin) ||
      num(s.revenue_growth) ||
      num(s.debt_equity));

  return (
    <section>
      <div className="mb-5">
        <SectionHeading eyebrow="Fundamentals" title="Key ratios & valuation" />
      </div>

      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 md:p-6 rounded-sm">
        {loading && !anyData ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-10 gap-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-5 rounded-sm animate-pulse bg-[rgba(255,255,255,0.04)]" />
            ))}
          </div>
        ) : !anyData ? (
          <EmptyNote>
            Financials pending next filing — snapshot refreshes after EDGAR/DART
            publish.
          </EmptyNote>
        ) : (
          <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-10">
            {/* Column 1 — Valuation · Earnings */}
            <div>
              <StatRow
                label="P/E ratio"
                value={num(s?.pe_ratio) ? Number(s!.pe_ratio).toFixed(1) : "—"}
              />
              <StatRow
                label="EPS (ttm)"
                value={num(s?.eps) ? Number(s!.eps).toFixed(2) : "—"}
              />
              <StatRow label="Market cap" value={fmtMcap(mcap, krw)} />
              <StatRow
                label="Beta (vs S&P 500)"
                value={num(s?.beta) ? Number(s!.beta).toFixed(2) : "—"}
              />
            </div>
            {/* Column 2 — Liquidity · Quality */}
            <div>
              <StatRow
                label="Avg volume (3mo)"
                value={
                  num(s?.avg_volume)
                    ? (s!.avg_volume as number).toLocaleString()
                    : "—"
                }
              />
              <StatRow
                label="Profit margin"
                value={
                  num(s?.profit_margin)
                    ? `${(Number(s!.profit_margin) * 100).toFixed(1)}%`
                    : "—"
                }
                tone={
                  num(s?.profit_margin)
                    ? (s!.profit_margin as number) > 0
                      ? "pos"
                      : "neg"
                    : "neu"
                }
              />
              <StatRow
                label="Revenue growth (YoY)"
                value={
                  num(s?.revenue_growth)
                    ? `${(Number(s!.revenue_growth) * 100).toFixed(1)}%`
                    : "—"
                }
                tone={
                  num(s?.revenue_growth)
                    ? (s!.revenue_growth as number) > 0
                      ? "pos"
                      : "neg"
                    : "neu"
                }
              />
              <StatRow
                label="Debt / Equity"
                value={num(s?.debt_equity) ? Number(s!.debt_equity).toFixed(2) : "—"}
              />
            </div>
          </div>
          {limited && (
            <p
              className="mt-5 pt-4 border-t border-[var(--pq-ivory-line)] text-pq-caption"
              style={{ color: "rgba(245,240,232,0.5)", lineHeight: 1.5 }}
            >
              수익성·매출 성장·부채비율은 데이터 제공사(KIS) 라이선스 범위 밖이라
              표시되지 않습니다 — 오류가 아닙니다.
              <span className="block" style={{ opacity: 0.7, marginTop: 2 }}>
                Profit margin, revenue growth &amp; debt-to-equity fall outside the
                KIS data license — not an error.
              </span>
            </p>
          )}
          </>
        )}
      </div>
    </section>
  );
}
