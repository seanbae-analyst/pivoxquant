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
  PdfKpiRow,
  PdfSectionTitle,
  PdfCard,
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
import { EmptyState } from "../empty-state";

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
  /** Period label for the cover headline (a month name). Optional —
   *  omitted rather than hardcoded when the backend does not supply it. */
  coverMonth?: string;
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


export function MonthlyFinance({ data }: { data?: MonthlyFinanceData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="monthly_finance" reason="no_trades" />;
  }
  return (
    <>
      {/* PAGE 1 — COVER */}
      <PdfPage>
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta={data.doc} />


        <div style={{ marginTop: "26mm" }}>
          <PdfCoverEyebrow>Monthly Financial Report · Personal Portfolio</PdfCoverEyebrow>
          <PdfCoverTitle size={56}>
            {data.coverMonth ? <>{data.coverMonth}<br /></> : null}
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
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta={`${data.doc} · 02/05`} />

        {/* Executive Summary narrative is not computed by the backend for this
            report — omit rather than render a fabricated narrative (CEO
            2026-05-31 "있는 데이터로만"). Carry-over: backend exec-summary wire. */}

        <PdfKpiRow
          kpis={[
            { label: "NAV · EOM", value: data.navEomKpi.value, delta: data.navEomKpi.delta, deltaTone: "pos" },
            { label: "Net P&L · MTD", value: data.netPnlMtd.value, delta: data.netPnlMtd.delta, deltaTone: "pos" },
            { label: "Alpha vs S&P", value: data.alphaVsBench.value, delta: data.alphaVsBench.delta, deltaTone: "pos" },
            { label: "Sharpe · 12M", value: data.sharpe.value, delta: data.sharpe.delta, deltaTone: "pos" },
          ]}
        />

        {/* 12-month NAV-vs-benchmark trend and Monthly Net P&L bar charts
            omitted: no per-month series data is wired into MonthlyFinanceData.
            Fixed SVG coordinates would be a fabricated trend (CEO 2026-05-31).
            Carry-over: wire backend monthly NAV/benchmark + P&L series. */}

        <PdfPageFooter left="Monthly Finance · Premium" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — INCOME STATEMENT
          2026-05-06 CEO 보고: V4 압축 (IS + BS 한 페이지) 시 297mm 초과로
          본문이 페이지 footer/disclaimer 와 visual overlap. "겹칠 것 같으면
          넘기라고." 지시대로 IS 와 BS 분리. */}
      <PdfPage>
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta={`${data.doc} · 03/05`} />
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
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta={`${data.doc} · 04/05`} />
        <PdfGoldRule />

        <div className="pq-pdf-section">
          <PdfSectionTitle variant="dry">Balance Sheet · 재무상태표{data.asOf ? ` (as of ${data.asOf})` : ""}</PdfSectionTitle>
          <PdfCard>
            <PdfDonut
              segments={data.bsAssets.map((a) => ({
                label: a.name,
                pct: a.pct,
                color: a.color,
                pctDisplay: a.pctDisplay,
              }))}
              centerLabel={data.navEom}
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
                      <td className="right font-mono"><strong>{data.navEom}</strong></td>
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
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta={`${data.doc} · 05/05`} />
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
