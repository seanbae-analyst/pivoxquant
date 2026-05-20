/**
 * Report 01 — Weekly Memo (Free · 1 page)
 *
 * Source: /design_handoff_pdf_reports/reports/01_weekly_memo.html
 *
 * The simplest entry point. Cover headline + 3-up KPI row, two-column
 * body (this week's three checks + 5-day trajectory chart), single
 * decision callout, memo-to-self notes.
 *
 * Compliance: POSITIVE / NEGATIVE / NEUTRAL labels only. No buy/sell/hold.
 * Disclaimer rendered automatically at the bottom.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfEyebrow,
  PdfCoverTitle,
  PdfKpiRow,
  PdfTwoCol,
  PdfColTitle,
  PdfCheckList,
  PdfCard,
  PdfCallout,
  PdfNotes,
  PdfPageFooter,
  PdfDisclaimerMini,
  PdfSectionTitle,
} from "../pdf-primitives";
import { WEEKLY_MEMO_WHEN_SHORT } from "@/lib/cfo/memo-schedule";

export interface WeeklyMemoData {
  asOf: string;            // "2026-04-26"
  weekTag: string;         // "WK-2026-23"
  portfolioReturn: string; // "+2.4%"
  benchmarkReturn: string; // "vs S&P +1.1%"
  portfolioValue: string;  // "$1,242,150"
  portfolioDelta: string;  // "▲ $29,310"
  ytdReturn: string;       // "+14.2%"
  ytdDetail: string;       // "Sharpe 0.87"
  threeChecks: { body: string; meta: string; checked: boolean }[];
  /** 5-day return path. Each value is a daily total return %, e.g. 0.4 = +0.4% */
  trajectory: { portfolio: number[]; benchmark: number[] };
  decision: string;
  memoToSelf: string;
}

const DEFAULT_DATA: WeeklyMemoData = {
  asOf: "2026-04-26",
  weekTag: "WK-2026-17",
  portfolioReturn: "+2.4%",
  benchmarkReturn: "vs S&P +1.1%",
  portfolioValue: "$1,242,150",
  portfolioDelta: "▲ $29,310",
  ytdReturn: "+14.2%",
  ytdDetail: "Sharpe 0.87",
  threeChecks: [
    {
      body: "반도체 비중 조정 — NVDA (NVIDIA) 일부 익절, AVGO (Broadcom) 비중 유지",
      meta: "+1.84%",
      checked: true,
    },
    {
      body: "헬스케어 신규 진입 — UNH (UnitedHealth) 신규 진입, 첫 비중 1.5%",
      meta: "+0.62%",
      checked: true,
    },
    {
      body: "FX 노출 점검 — USD 단일 노출 88%, 헤지 검토",
      meta: "−0.21%",
      checked: false,
    },
  ],
  trajectory: {
    portfolio: [0, 0.3, 0.8, 1.5, 2.4],
    benchmark: [0, 0.1, 0.4, 0.7, 1.1],
  },
  decision:
    "이번 주 단 하나의 결정: 반도체 비중 −0.95%p, 헬스케어 +1.5%p로 조정. " +
    "변동성 구간에서 단일 섹터 노출을 누그러뜨리는 의도.",
  memoToSelf:
    "다음 주 점검: (1) UNH (UnitedHealth) 진입 후 reaction 모니터, (2) FX 헤지 비중 결정, " +
    "(3) 다음 분기 실적 시즌 진입 전 cash buffer 점검.",
};

/** Build an SVG path "M0,80 L150,70 …" from a series of percentage returns.
 *  Returns are rebased to a 120px-tall band — top = best of both series, bottom = worst. */
function pathFromReturns(values: number[], all: number[], width = 600, height = 120): string {
  if (values.length === 0) return "";
  const min = Math.min(...all);
  const max = Math.max(...all);
  const range = max - min || 1;
  const step = width / (values.length - 1 || 1);
  return values
    .map((v, i) => {
      const x = i * step;
      // invert because SVG y grows downward; pad 10% top/bottom
      const y = height * 0.95 - ((v - min) / range) * (height * 0.85);
      return `${i === 0 ? "M" : "L"}${x.toFixed(0)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function WeeklyMemo({ data = DEFAULT_DATA }: { data?: WeeklyMemoData }) {
  const allReturns = [...data.trajectory.portfolio, ...data.trajectory.benchmark];
  const portPath = pathFromReturns(data.trajectory.portfolio, allReturns);
  const benchPath = pathFromReturns(data.trajectory.benchmark, allReturns);
  const portFillPath = `${portPath} L600,120 L0,120 Z`;

  return (
    <PdfPage>
      <PdfHeader tier="free" title="WEEKLY MEMO" meta={`${data.asOf} · ${data.weekTag}`} />

      <PdfEyebrow>{`Weekly Memo · ${WEEKLY_MEMO_WHEN_SHORT}`}</PdfEyebrow>
      <PdfCoverTitle size={42}>
        This week, <em>one page</em>—<br />
        be the <em>CFO</em> of your portfolio.
      </PdfCoverTitle>
      <p
        style={{
          color: "var(--r-ink-3)",
          marginTop: 12,
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.55,
        }}
      className="font-serif" >
        Three signals that mattered, one decision for next week. The rest is noise.
      </p>

      <div style={{ marginTop: 24 }}>
        <PdfKpiRow
          cols={3}
          kpis={[
            {
              label: "This Week",
              value: data.portfolioReturn,
              delta: data.benchmarkReturn,
              deltaTone: "pos",
            },
            {
              label: "Portfolio Value",
              value: data.portfolioValue,
              delta: data.portfolioDelta,
            },
            {
              label: "YTD",
              value: data.ytdReturn,
              delta: data.ytdDetail,
              deltaTone: "pos",
            },
          ]}
        />
      </div>

      <PdfTwoCol>
        <div>
          <PdfColTitle>This Week · 세 가지</PdfColTitle>
          <PdfCheckList
            items={data.threeChecks.map((c) => ({
              checked: c.checked,
              body: c.body,
              meta: c.meta,
            }))}
          />
        </div>
        <div>
          <PdfColTitle>5-Day Trajectory</PdfColTitle>
          <PdfCard>
            <svg
              className="pq-pdf-chart"
              viewBox="0 0 600 120"
              preserveAspectRatio="none"
            >
              <line className="pq-pdf-grid-line" x1="0" y1="60" x2="600" y2="60" />
              <path className="pq-pdf-line-port-fill" fill="#0e0e0e" d={portFillPath} />
              <path className="pq-pdf-line-port" d={portPath} />
              <path className="pq-pdf-line-bench" d={benchPath} />
            </svg>
            <div className="pq-pdf-chart-legend">
              <span>
                <span
                  className="pq-pdf-legend-dot"
                  style={{ background: "#0e0e0e" }}
                />
                Portfolio
              </span>
              <span>
                <span
                  className="pq-pdf-legend-dot"
                  style={{ background: "#c0c0c0" }}
                />
                S&amp;P 500
              </span>
            </div>
          </PdfCard>
        </div>
      </PdfTwoCol>

      <div style={{ marginTop: 18 }}>
        <PdfCallout flat label="Next Week · The One Decision">
          {data.decision}
        </PdfCallout>
      </div>

      <div style={{ marginTop: 18 }}>
        <PdfSectionTitle variant="sm">Memo to Self</PdfSectionTitle>
        <PdfNotes>{data.memoToSelf}</PdfNotes>
      </div>

      <PdfPageFooter
        left="For information only · pivoxquant.com"
        right={`Weekly Memo · ${data.weekTag}`}
      />

      <PdfDisclaimerMini />
    </PdfPage>
  );
}
