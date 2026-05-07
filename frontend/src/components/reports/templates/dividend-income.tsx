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
  PdfTwoCol,
  PdfColTitle,
  PdfCard,
  PdfAllocList,
  PdfCallout,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
} from "../pdf-primitives";

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
  thisMonth: { value: string; delta: string };
  ytdIncome: { value: string; delta: string };
  yieldOnCost: { value: string; delta: string };
  runRate: { value: string; delta: string };
  payments: Payment[];
  totalReceived: string;
  avgYield: string;
  topContributors: { ticker: string; pct: number; amount: string; flat?: boolean }[];
  reinvestmentNote: string;
}

const DEFAULT: DividendIncomeData = {
  asOf: "April 2026",
  thisMonth: { value: "$1,842", delta: "+$214 vs last" },
  ytdIncome: { value: "$18,420", delta: "+12.8% YoY" },
  yieldOnCost: { value: "4.18%", delta: "portfolio avg" },
  runRate: { value: "$22,104", delta: "$1,842/mo" },
  payments: [
    { date: "Jun 03", ticker: "JEPI", name: "JPM Equity Premium", shares: "120", perShare: "$0.42", received: "$50.40", yield: "7.8%" },
    { date: "Jun 07", ticker: "SCHD", name: "Schwab Dividend", shares: "80", perShare: "$0.78", received: "$62.40", yield: "3.6%" },
    { date: "Jun 12", ticker: "KO", name: "Coca-Cola", shares: "200", perShare: "$0.485", received: "$97.00", yield: "3.0%" },
    { date: "Jun 14", ticker: "PG", name: "Procter & Gamble", shares: "60", perShare: "$1.0065", received: "$60.39", yield: "2.4%" },
    { date: "Jun 18", ticker: "JNJ", name: "Johnson & Johnson", shares: "75", perShare: "$1.24", received: "$93.00", yield: "3.1%" },
    { date: "Jun 22", ticker: "MSFT", name: "Microsoft", shares: "40", perShare: "$0.83", received: "$33.20", yield: "0.7%" },
    { date: "Jun 25", ticker: "VZ", name: "Verizon", shares: "300", perShare: "$0.665", received: "$199.50", yield: "6.4%" },
    { date: "Jun 28", ticker: "O", name: "Realty Income", shares: "450", perShare: "$0.2625", received: "$118.13", yield: "5.6%" },
  ],
  totalReceived: "$1,842.02",
  avgYield: "avg 4.1%",
  topContributors: [
    { ticker: "VZ", pct: 100, amount: "$199" },
    { ticker: "O", pct: 60, amount: "$118" },
    { ticker: "KO", pct: 48, amount: "$97" },
    { ticker: "JNJ", pct: 46, amount: "$93" },
    { ticker: "SCHD", pct: 32, amount: "$62", flat: true },
    { ticker: "PG", pct: 30, amount: "$60", flat: true },
  ],
  reinvestmentNote:
    "받은 $1,842, 어디에 다시 심을 것인가. SCHD 12주 추가 매입 검토. 또는 현금 보유 후 다음 달 합산.",
};

// 2026-05-06: compact on the single PdfPage so gov+disclaim atomic
// fits within one A4 sheet (was overflowing to a 2nd PDF sheet).
export function DividendIncome({ data = DEFAULT }: { data?: DividendIncomeData }) {
  return (
    <PdfPage compact>
      <PdfHeader tier="pro" title="DIVIDEND INCOME" meta={`${data.asOf} · DI-2026-04`} />
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

      <div style={{ marginTop: 24 }}>
        <PdfTwoCol>
          <div>
            <PdfColTitle>12-Month Income Trail</PdfColTitle>
            <PdfCard>
              <svg
                viewBox="0 0 600 160"
                preserveAspectRatio="none"
                style={{ width: "100%", height: 160 }}
              >
                <line x1="0" y1="40" x2="600" y2="40" stroke="#ececec" strokeWidth="1" />
                <line x1="0" y1="80" x2="600" y2="80" stroke="#ececec" strokeWidth="1" />
                <line x1="0" y1="120" x2="600" y2="120" stroke="#ececec" strokeWidth="1" />
                {[
                  [10, 92, 50], [60, 78, 64], [110, 86, 56], [160, 62, 80],
                  [210, 74, 68], [260, 50, 92], [310, 80, 62], [360, 68, 74],
                  [410, 42, 100], [460, 58, 84], [510, 48, 94],
                ].map(([x, y, h], i) => (
                  <rect key={i} x={x} y={y} width="36" height={h} fill="#0e0e0e" />
                ))}
                <rect x="560" y="32" width="36" height="110" fill="#c9963f" />
                <text x="14" y="156" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">JUL</text>
                <text x="164" y="156" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">OCT</text>
                <text x="314" y="156" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">JAN</text>
                <text x="464" y="156" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">APR</text>
                <text x="566" y="156" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">JUN</text>
              </svg>
              <div style={{ fontSize: 12, color: "var(--r-ink-3)", marginTop: 8 }}>
                12개월 평균 $1,535 / 이번 달 $1,842 ▲
              </div>
            </PdfCard>
          </div>
          <div>
            <PdfColTitle>Top Contributors · 누가 벌어다 줬나</PdfColTitle>
            <PdfAllocList
              items={data.topContributors.map((c) => ({
                name: <PdfTicker>{c.ticker}</PdfTicker>,
                pct: c.pct,
                pctDisplay: c.amount,
              }))}
            />
          </div>
        </PdfTwoCol>
      </div>

      <div style={{ marginTop: 18 }}>
        <PdfCallout label="Reinvestment · 다음 매입 후보">{data.reinvestmentNote}</PdfCallout>
      </div>

      <PdfGovBlock />
      <PdfPageFooter left="Dividend Income · Pro · pivoxquant.com" right={data.asOf} />
      <PdfDisclaimer cadence="monthly" />
    </PdfPage>
  );
}
