/**
 * Report 16 — Monthly Finance (Premium · 4 pages · Monthly)
 *
 * Source: /design_handoff_pdf_reports/reports/16_monthly_finance.html
 *
 * Page 1: Cover (eyebrow + title + 4-up cover meta).
 * Page 2: Executive Summary (5 dt/dd rows) + 4-up KPI + NAV vs S&P 500 chart
 *         + Monthly P&L bars chart.
 * Page 3: Income Statement table (8 line items) + Balance Sheet donut + 2-col asset/liab tables.
 * Page 4: Cash Flow table + Key Ratios 4-up + Liquidity Tiers table + governance + disclaimer.
 *
 * Compliance: Personal portfolio reporting. Internal use only. Not investment advice.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfGoldRule,
  PdfCoverEyebrow,
  PdfCoverTitle,
  PdfCoverSub,
  PdfCoverMetaGrid,
  PdfCoverFoot,
  PdfExecSum,
  PdfBadge,
  PdfKpiRow,
  PdfSectionTitle,
  PdfCard,
  PdfFlexBetween,
  PdfTable,
  PdfDonut,
  PdfTwoCol,
  PdfColTitle,
  PdfHeat,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";

interface IncomeRow {
  label: string;
  mtd: string;
  mtdTone?: "pos" | "neg";
  ytd: string;
  ytdTone?: "pos" | "neg";
  pctNav: string;
  pctNavTone?: "pos" | "neg";
}

export interface MonthlyFinanceData {
  doc: string;
  asOf: string;
  navEom: string;
  monthReturn: string;
  ytdReturn: string;
  issued: string;
  navEomKpi: { value: string; delta: string };
  netPnlMtd: { value: string; delta: string };
  alphaVsBench: { value: string; delta: string };
  sharpe: { value: string; delta: string };
  income: IncomeRow[];
  totalNetPnl: IncomeRow;
  bsAssets: { name: string; pct: number; color: string; pctDisplay: string }[];
  liabilities: { label: string; value: string; bold?: boolean }[];
  totalLiab: string;
  cashFlow: { label: string; mtd: string; mtdTone?: "pos" | "neg"; ytd: string; ytdTone?: "pos" | "neg" }[];
  netCashChange: { mtd: string; mtdTone: "pos" | "neg"; ytd: string; ytdTone: "pos" | "neg" };
  ratios: {
    equityRatio: string;
    yieldOnCost: string;
    turnover: string;
    taxDrag: string;
  };
  liquidityTiers: { tier: string; desc: string; amount: string; pctNav: string; dtc: string }[];
}

const DEFAULT: MonthlyFinanceData = {
  doc: "Apr 2026 · MF-2026-04 · 01/05",
  asOf: "Apr 30, 2026",
  navEom: "USD 1,242,150",
  monthReturn: "+4.0%",
  ytdReturn: "+14.2%",
  issued: "May 1, 2026",
  navEomKpi: { value: "USD 1,242k", delta: "+USD 53k MTD" },
  netPnlMtd: { value: "+USD 48k", delta: "+3.86% NAV" },
  alphaVsBench: { value: "+1.1%p", delta: "YTD +4.8%p" },
  sharpe: { value: "1.42", delta: "+0.08 vs prior" },
  income: [
    { label: "Realized Gains", mtd: "+USD 18,420", mtdTone: "pos", ytd: "+USD 72,840", ytdTone: "pos", pctNav: "+5.86%" },
    { label: "Unrealized Gains", mtd: "+USD 32,180", mtdTone: "pos", ytd: "+USD 98,420", ytdTone: "pos", pctNav: "+7.92%" },
    { label: "Dividends Received", mtd: "+USD 2,140", mtdTone: "pos", ytd: "+USD 8,720", ytdTone: "pos", pctNav: "+0.70%" },
    { label: "Interest Income", mtd: "+USD 320", mtdTone: "pos", ytd: "+USD 1,280", ytdTone: "pos", pctNav: "+0.10%" },
    { label: "Trading Costs", mtd: "−USD 280", mtdTone: "neg", ytd: "−USD 1,140", ytdTone: "neg", pctNav: "−0.09%" },
    { label: "FX Loss", mtd: "−USD 420", mtdTone: "neg", ytd: "−USD 2,180", ytdTone: "neg", pctNav: "−0.18%" },
    { label: "Tax Provision", mtd: "−USD 3,840", mtdTone: "neg", ytd: "−USD 14,820", ytdTone: "neg", pctNav: "−1.19%" },
  ],
  totalNetPnl: { label: "Net P&L", mtd: "+USD 48,520", mtdTone: "pos", ytd: "+USD 163,120", ytdTone: "pos", pctNav: "+13.13%", pctNavTone: "pos" },
  bsAssets: [
    { name: "US Equities", pct: 72, color: "#0e0e0e", pctDisplay: "USD 894k · 72%" },
    { name: "KR Equities", pct: 12, color: "#3a3a3a", pctDisplay: "USD 149k · 12%" },
    { name: "EU Equities", pct: 8, color: "#7a6c4a", pctDisplay: "USD 99k · 8%" },
    { name: "Bonds", pct: 2, color: "#c9963f", pctDisplay: "USD 25k · 2%" },
    { name: "Cash · USD/KRW", pct: 6, color: "#dcd5c2", pctDisplay: "USD 75k · 6%" },
  ],
  liabilities: [
    { label: "Margin Debt", value: "USD 0" },
    { label: "Tax Accrual", value: "USD 0" },
    { label: "Other Liabilities", value: "USD 0" },
    { label: "Owner's Equity (NAV)", value: "USD 1,242k", bold: true },
  ],
  totalLiab: "USD 1,242k",
  cashFlow: [
    { label: "Operating · 배당 + 이자", mtd: "+USD 2,460", mtdTone: "pos", ytd: "+USD 10,000", ytdTone: "pos" },
    { label: "Investing · 매입 − 매각", mtd: "−USD 28,400", mtdTone: "neg", ytd: "−USD 84,200", ytdTone: "neg" },
    { label: "Financing · 입출금", mtd: "+USD 5,000", mtdTone: "pos", ytd: "+USD 20,000", ytdTone: "pos" },
    { label: "Tax Paid", mtd: "−USD 3,840", mtdTone: "neg", ytd: "−USD 14,820", ytdTone: "neg" },
  ],
  netCashChange: { mtd: "−USD 24,780", mtdTone: "neg", ytd: "−USD 69,020", ytdTone: "neg" },
  ratios: {
    equityRatio: "98.8%",
    yieldOnCost: "2.1%",
    turnover: "42%",
    taxDrag: "−1.19%",
  },
  liquidityTiers: [
    { tier: "T1", desc: "현금 + MMF", amount: "USD 75k", pctNav: "6.0%", dtc: "0d" },
    { tier: "T2", desc: "대형주 + 유동 ETF", amount: "USD 988k", pctNav: "79.5%", dtc: "1–2d" },
    { tier: "T3", desc: "중소형주", amount: "USD 154k", pctNav: "12.4%", dtc: "3–5d" },
    { tier: "T4", desc: "채권 · 비유동", amount: "USD 25k", pctNav: "2.0%", dtc: "7–14d" },
  ],
};

export function MonthlyFinance({ data = DEFAULT }: { data?: MonthlyFinanceData }) {
  return (
    <>
      {/* PAGE 1 — COVER */}
      <PdfPage>
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta={data.doc} />

        <div style={{ marginTop: "26mm" }}>
          <PdfCoverEyebrow>Monthly Financial Report · Personal Portfolio</PdfCoverEyebrow>
          <PdfCoverTitle size={56}>
            April 2026
            <br />
            <span style={{ color: "var(--r-ink-3)", fontWeight: 400 }}>Monthly Finance Pack.</span>
          </PdfCoverTitle>
          <PdfCoverSub>
            NAV movement, P&amp;L, balance sheet, cash flow — run your portfolio like a company.
          </PdfCoverSub>
        </div>

        <div style={{ marginTop: "auto", paddingTop: "30mm" }}>
          <PdfCoverMetaGrid
            items={[
              { label: "NAV · EOM", value: data.navEom },
              { label: "Month Return", value: data.monthReturn },
              { label: "YTD Return", value: data.ytdReturn },
              { label: "Issued", value: data.issued },
            ]}
          />
        </div>

        <PdfCoverFoot />
      </PdfPage>

      {/* PAGE 2 — EXECUTIVE SUMMARY + NAV TREND */}
      <PdfPage>
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta="Apr 2026 · 02/05" />

        <PdfExecSum
          stamp={`As of ${data.asOf}`}
          rows={[
            { term: "Period Return", body: <><strong>+4.0% MTD · +14.2% YTD</strong> — vs benchmark (S&amp;P 500) +3.0% / +9.4%. <strong>Alpha +1.0%p / +4.8%p.</strong></> },
            { term: "NAV", body: <>USD 1,189k → <strong>USD 1,242k</strong> · 자본 유입 +USD 5k · 운용 손익 +USD 48k.</> },
            { term: "P&L Drivers", body: "반도체 +USD 22k · 소프트웨어 +USD 11k · 헬스케어 −USD 4k · FX 손실 −USD 0.4k." },
            { term: "Balance Sheet", body: "Equity 92% · Bonds 2% · Cash 6%. Margin debt 0. No outstanding liabilities." },
            { term: "Watch", body: <><PdfBadge tone="moderate">⚠</PdfBadge> USD 노출 88% — FX 헤지 검토. Tech 비중 42% — 한도 35% 초과.</> },
          ]}
        />

        <PdfKpiRow
          kpis={[
            { label: "NAV · EOM", value: data.navEomKpi.value, delta: data.navEomKpi.delta, deltaTone: "pos" },
            { label: "Net P&L · MTD", value: data.netPnlMtd.value, delta: data.netPnlMtd.delta, deltaTone: "pos" },
            { label: "Alpha vs S&P", value: data.alphaVsBench.value, delta: data.alphaVsBench.delta, deltaTone: "pos" },
            { label: "Sharpe · 12M", value: data.sharpe.value, delta: data.sharpe.delta, deltaTone: "pos" },
          ]}
        />

        <PdfSectionTitle variant="dry">NAV &amp; Benchmark · 12M trend (indexed to 100)</PdfSectionTitle>
        <PdfCard>
          <PdfFlexBetween>
            <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
              NAV vs S&amp;P 500 · last 12 months
            </div>
            <div style={{ display: "flex", gap: 14, fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)", }} className="font-mono" >
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#0e0e0e" }} />Portfolio NAV</span>
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#c0c0c0" }} />S&amp;P 500</span>
            </div>
          </PdfFlexBetween>
          <svg viewBox="0 0 600 160" preserveAspectRatio="none" style={{ width: "100%", height: 160, marginTop: 12 }}>
            <defs>
              <linearGradient id="mf-fade" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0e0e0e" stopOpacity=".18" />
                <stop offset="100%" stopColor="#0e0e0e" stopOpacity="0" />
              </linearGradient>
            </defs>
            <line x1="0" y1="40" x2="600" y2="40" stroke="#ececec" strokeWidth="1" />
            <line x1="0" y1="80" x2="600" y2="80" stroke="#ececec" strokeWidth="1" />
            <line x1="0" y1="120" x2="600" y2="120" stroke="#ececec" strokeWidth="1" />
            <path d="M0,100 L50,96 L100,90 L150,98 L200,86 L250,80 L300,84 L350,72 L400,66 L450,60 L500,58 L550,54 L600,48" stroke="#c0c0c0" strokeWidth="1.4" fill="none" strokeDasharray="3 3" />
            <path d="M0,108 L50,98 L100,88 L150,100 L200,82 L250,72 L300,80 L350,62 L400,52 L450,44 L500,40 L550,32 L600,24 L600,160 L0,160 Z" fill="url(#mf-fade)" />
            <path d="M0,108 L50,98 L100,88 L150,100 L200,82 L250,72 L300,80 L350,62 L400,52 L450,44 L500,40 L550,32 L600,24" stroke="#0e0e0e" strokeWidth="2" fill="none" />
            <circle cx="600" cy="24" r="3" fill="#0e0e0e" />
            <circle cx="600" cy="48" r="3" fill="#c0c0c0" />
          </svg>
        </PdfCard>

        <PdfSectionTitle variant="dry">Monthly Net P&amp;L · last 12 months ($k)</PdfSectionTitle>
        <PdfCard>
          <svg viewBox="0 0 600 120" preserveAspectRatio="none" style={{ width: "100%", height: 120 }}>
            <line x1="0" y1="60" x2="600" y2="60" stroke="#ececec" strokeWidth="1" />
            {[
              [6, 32, 28, "#0e0e0e"],
              [54, 60, 18, "#b1331f"],
              [102, 42, 18, "#0e0e0e"],
              [150, 22, 38, "#0e0e0e"],
              [198, 38, 22, "#0e0e0e"],
              [246, 60, 14, "#b1331f"],
              [294, 48, 12, "#0e0e0e"],
              [342, 28, 32, "#0e0e0e"],
              [390, 16, 44, "#0e0e0e"],
              [438, 34, 26, "#0e0e0e"],
              [486, 42, 18, "#0e0e0e"],
              [534, 20, 40, "#0e0e0e"],
            ].map(([x, y, h, f], i) => (
              <rect key={i} x={x} y={y} width={42} height={h} fill={f as string} opacity={(f as string) === "#b1331f" ? 0.85 : 1} />
            ))}
          </svg>
        </PdfCard>

        <PdfPageFooter left="Monthly Finance · Premium" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — INCOME STATEMENT
          2026-05-06 CEO 보고: V4 압축 (IS + BS 한 페이지) 시 297mm 초과로
          본문이 페이지 footer/disclaimer 와 visual overlap. "겹칠 것 같으면
          넘기라고." 지시대로 IS 와 BS 분리. */}
      <PdfPage>
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta="Apr 2026 · 03/05" />
        <PdfGoldRule />

        <PdfSectionTitle variant="dry">Income Statement · 손익계산서 (MTD &amp; YTD)</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Line Item</th>
              <th className="right">MTD</th>
              <th className="right">YTD</th>
              <th className="right">% NAV YTD</th>
            </tr>
          </thead>
          <tbody>
            {data.income.map((r) => (
              <tr key={r.label}>
                <td>{r.label.startsWith("Realized") || r.label.startsWith("Unrealized") || r.label.startsWith("Dividends") || r.label.startsWith("Interest") ? <strong>{r.label}</strong> : r.label}</td>
                <td className={`right ${r.mtdTone ?? ""}`}>{r.mtd}</td>
                <td className={`right ${r.ytdTone ?? ""}`}>{r.ytd}</td>
                <td className="right">{r.pctNav}</td>
              </tr>
            ))}
            <tr className="total">
              <td><strong>{data.totalNetPnl.label}</strong></td>
              <td className="right pos">{data.totalNetPnl.mtd}</td>
              <td className="right pos">{data.totalNetPnl.ytd}</td>
              <td className="right pos">{data.totalNetPnl.pctNav}</td>
            </tr>
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Monthly Finance · Premium" right="Page 03" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 4 — BALANCE SHEET (donut + 2-col Assets/Liab) — separated
          from IS so neither overlaps the page footer. */}
      <PdfPage>
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta="Apr 2026 · 04/05" />
        <PdfGoldRule />

        <div className="pq-pdf-section">
          <PdfSectionTitle variant="dry">Balance Sheet · 재무상태표 (as of Apr 30)</PdfSectionTitle>
          <PdfCard>
            <PdfDonut
              segments={data.bsAssets.map((a) => ({
                label: a.name,
                pct: a.pct,
                color: a.color,
                pctDisplay: a.pctDisplay,
              }))}
              centerLabel="USD 1.24M"
            />
          </PdfCard>

          <div style={{ marginTop: 24 }}>
            <PdfTwoCol>
              <div>
                <PdfColTitle>Total Assets</PdfColTitle>
                <PdfTable>
                  <tbody>
                    {data.bsAssets.map((a) => (
                      <tr key={a.name}>
                        <td>{a.name}</td>
                        <td className="right font-mono">{a.pctDisplay.split(" · ")[0]}</td>
                      </tr>
                    ))}
                    <tr className="total">
                      <td><strong>Total</strong></td>
                      <td className="right font-mono"><strong>USD 1,242k</strong></td>
                    </tr>
                  </tbody>
                </PdfTable>
              </div>
              <div>
                <PdfColTitle>Liabilities &amp; Equity</PdfColTitle>
                <PdfTable>
                  <tbody>
                    {data.liabilities.map((l) => (
                      <tr key={l.label}>
                        <td>{l.bold ? <strong>{l.label}</strong> : l.label}</td>
                        <td className="right font-mono">{l.bold ? <strong>{l.value}</strong> : l.value}</td>
                      </tr>
                    ))}
                    <tr className="total">
                      <td><strong>Total</strong></td>
                      <td className="right font-mono"><strong>{data.totalLiab}</strong></td>
                    </tr>
                  </tbody>
                </PdfTable>
              </div>
            </PdfTwoCol>
          </div>
        </div>

        <PdfPageFooter left="Monthly Finance · Premium" right="Page 05" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 5 — CASH FLOW + RATIOS + GOVERNANCE
          `compact` shrinks padding 18/16/22mm → 14/14/18mm to fit Cash
          Flow + Key Ratios + Liquidity Tiers + Gov + bilingual Disclaimer
          on a single sheet. */}
      <PdfPage compact>
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta="Apr 2026 · 05/05" />
        <PdfGoldRule />

        <PdfSectionTitle variant="dry">Cash Flow · 현금흐름표</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Activity</th>
              <th className="right">MTD</th>
              <th className="right">YTD</th>
            </tr>
          </thead>
          <tbody>
            {data.cashFlow.map((c) => (
              <tr key={c.label}>
                <td><strong>{c.label.split(" · ")[0]}</strong>{c.label.includes(" · ") && <> · {c.label.split(" · ")[1]}</>}</td>
                <td className={`right ${c.mtdTone ?? ""}`}>{c.mtd}</td>
                <td className={`right ${c.ytdTone ?? ""}`}>{c.ytd}</td>
              </tr>
            ))}
            <tr className="total">
              <td><strong>Net Cash Change</strong></td>
              <td className={`right ${data.netCashChange.mtdTone}`}>{data.netCashChange.mtd}</td>
              <td className={`right ${data.netCashChange.ytdTone}`}>{data.netCashChange.ytd}</td>
            </tr>
          </tbody>
        </PdfTable>

        <PdfSectionTitle variant="dry">Key Ratios · 주요 비율</PdfSectionTitle>
        <PdfKpiRow
          kpis={[
            { label: "Equity Ratio", value: data.ratios.equityRatio, delta: <PdfHeat tone="green">HEALTHY</PdfHeat> },
            { label: "Yield on Cost", value: data.ratios.yieldOnCost, delta: "divs / cost" },
            { label: "Turnover · YTD", value: data.ratios.turnover, delta: <>target ≤ 60% · <PdfHeat tone="green">OK</PdfHeat></> },
            { label: "Tax Drag · YTD", value: data.ratios.taxDrag, delta: "% NAV" },
          ]}
        />

        <PdfSectionTitle variant="dry">Liquidity Tiers · 유동성 등급 (days to cash)</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Tier</th>
              <th>Description</th>
              <th className="right">Amount</th>
              <th className="right">% NAV</th>
              <th className="right">DTC</th>
            </tr>
          </thead>
          <tbody>
            {data.liquidityTiers.map((t) => (
              <tr key={t.tier}>
                <td><strong>{t.tier}</strong></td>
                <td>{t.desc}</td>
                <td className="right">{t.amount}</td>
                <td className="right">{t.pctNav}</td>
                <td className="right">{t.dtc}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfGovBlock />
        <PdfPageFooter left="Monthly Finance · Premium · Internal" right="Page 05" />
        <PdfDisclaimer cadence="monthly" />
      </PdfPage>
    </>
  );
}
