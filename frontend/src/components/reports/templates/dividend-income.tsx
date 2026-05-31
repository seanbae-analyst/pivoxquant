/**
 * Report 09 — Dividend Income (Pro · 1 page · Monthly)
 *
 * Source: /design_handoff_pdf_reports/reports/09_dividend_income.html
 *
 * One-page cash-received tracker. KPI row (4-up: this month / YTD / yield-on-cost / run rate)
 * → payments table → 12-month income trail bar chart + top contributors alloc bars
 * → reinvestment callout. Pro tier with gold rule + governance + disclaimer.
 *
 * Compliance: Income reporting only. POSITIVE delta tone for receipts; no buy/sell/hold.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfGoldRule,
  PdfEyebrow,
  PdfCoverTitle,
  PdfKpiRow,
  PdfSectionTitle,
  PdfTable,
  PdfTicker,
  PdfColTitle,
  PdfAllocList,
  PdfCallout,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

interface Payment {
  date: string;
  ticker: string;
  name: string;
  shares: string;
  perShare: string;
  received: string;
  yield: string;
}

export interface DividendIncomeData {
  asOf: string;
  /** Report id shown in the page header (a DI-prefixed tag). Optional —
   *  omitted rather than hardcoded when the backend does not supply it. */
  reportTag?: string;
  thisMonth: { value: string; delta: string };
  ytdIncome: { value: string; delta: string };
  yieldOnCost: { value: string; delta: string };
  runRate: { value: string; delta: string };
  payments: Payment[];
  totalReceived: string;
  avgYield: string;
  topContributors: { ticker: string; name: string; pct: number; amount: string; flat?: boolean }[];
  reinvestmentNote: string;
}


// 2026-05-06 (v24): Strategy B Option 2 — disclaim split into own PdfPage.
// Body PdfPage no longer crowds gov+disclaim onto one sheet; chromium
// no longer pushes a ghost disclosure-only page.
export function DividendIncome({ data }: { data?: DividendIncomeData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="dividend_income" reason="no_positions" />;
  }
  return (
    <>
    <PdfPage>
      <PdfHeader tier="pro" title="DIVIDEND INCOME" meta={`${data.asOf}${data.reportTag ? ` · ${data.reportTag}` : ""} · 01/02`} />
      <PdfGoldRule />


      <PdfEyebrow>Dividend Income · Monthly</PdfEyebrow>
      <PdfCoverTitle size={42}>
        Cash, <em>arrived</em>—
        <br />
        every dollar that landed this month.
      </PdfCoverTitle>

      <div style={{ marginTop: 24 }}>
        <PdfKpiRow
          kpis={[
            { label: "Received this Month", value: data.thisMonth.value, delta: data.thisMonth.delta, deltaTone: "pos" },
            { label: "YTD Income", value: data.ytdIncome.value, delta: data.ytdIncome.delta, deltaTone: "pos" },
            { label: "Yield on Cost", value: data.yieldOnCost.value, delta: data.yieldOnCost.delta },
            { label: "Run Rate (12m)", value: data.runRate.value, delta: data.runRate.delta, deltaTone: "pos" },
          ]}
        />
      </div>

      <PdfSectionTitle variant="sm">This Month&apos;s Payments · 입금 내역</PdfSectionTitle>
      <PdfTable>
        <thead>
          <tr>
            <th>Date</th>
            <th>Holding</th>
            <th className="right">Shares</th>
            <th className="right">Per Share</th>
            <th className="right">Received</th>
            <th className="right">Yield</th>
          </tr>
        </thead>
        <tbody>
          {data.payments.map((p) => (
            <tr key={p.date + p.ticker}>
              <td>{p.date}</td>
              <td>
                <PdfTicker>{p.ticker}</PdfTicker>
                {p.name}
              </td>
              <td className="right">{p.shares}</td>
              <td className="right">{p.perShare}</td>
              <td className="right pos">{p.received}</td>
              <td className="right">{p.yield}</td>
            </tr>
          ))}
          <tr className="total">
            <td colSpan={4}>Total · {data.payments.length} holdings</td>
            <td className="right pos">{data.totalReceived}</td>
            <td className="right">{data.avgYield}</td>
          </tr>
        </tbody>
      </PdfTable>

      {/* 12-Month Income Trail bar chart omitted: no per-month income series
          is wired into DividendIncomeData. Fixed SVG bar heights + the
          "평균 / 이번 달" line would be fabricated figures (CEO 2026-05-31).
          Carry-over: wire backend monthly income series → render real bars.
          Top Contributors (real data.topContributors) is retained. */}
      <div style={{ marginTop: 24 }}>
        <PdfColTitle>Top Contributors · 누가 벌어다 줬나</PdfColTitle>
        <PdfAllocList
          items={data.topContributors.map((c) => ({
            name: (
              <>
                <PdfTicker>{c.ticker}</PdfTicker>{" "}
                <span style={{ color: "var(--r-ink-3)" }}>{c.name}</span>
              </>
            ),
            pct: c.pct,
            pctDisplay: c.amount,
          }))}
        />
      </div>

      <div style={{ marginTop: 18 }}>
        <PdfCallout label="Reinvestment · 다음 매입 후보">{data.reinvestmentNote}</PdfCallout>
      </div>

      <PdfGovBlock />
      <PdfPageFooter left="Dividend Income · Pro · pivoxquant.com" right={data.asOf} />
      <PdfDisclaimerMini />
    </PdfPage>

    <PdfPage>
      <PdfHeader tier="pro" title="DIVIDEND INCOME" meta={`${data.asOf}${data.reportTag ? ` · ${data.reportTag}` : ""} · 02/02`} />
      <PdfGoldRule />
      <PdfDisclaimer cadence="monthly" />
    </PdfPage>
    </>
  );
}
