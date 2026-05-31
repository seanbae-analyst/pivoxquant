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
  PdfTable,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

/** A single observed cost or tax line item from the backend ledger. */
interface LedgerRow {
  label: string;
  amount: string;
  detail?: string;
}

export interface MonthlyFinanceData {
  doc: string;
  /** Period label for the cover headline (a month name). Optional —
   *  omitted rather than hardcoded when the backend does not supply it. */
  coverMonth?: string;
  asOf: string;
  issued: string;
  // ── KPI row — only metrics services/artifacts/monthly_finance_service.py
  //    actually computes: NAV (cash + market value), cash, liquidity ratio,
  //    cash runway. P&L / NAV return / alpha / Sharpe are NOT computed by the
  //    backend for this report, so those cards were removed rather than
  //    fabricated (CEO 2026-05-31 "있는 데이터로만"). Each KPI is optional so a
  //    user missing one metric elides that card instead of throwing.
  navEom: string;
  navEomKpi?: { value: string; delta: string };
  cashKpi?: { value: string; delta: string };
  liquidityKpi?: { value: string; delta: string };
  runwayKpi?: { value: string; delta: string };
  // ── Cost / Tax ledgers — observed estimates the backend computes. Arrays
  //    are `.map()`ed so an empty ledger renders cleanly (no fabricated rows).
  costRows: LedgerRow[];
  taxRows: LedgerRow[];
  // NOTE (option-b): the former Income Statement, Balance Sheet, Cash Flow,
  // Key Ratios and Liquidity Tiers surfaces were removed. The backend produces
  // a personal cash/cost/tax statement, NOT a corporate-style P&L / balance
  // sheet / cash-flow statement, so those fields had no real source. Carry-over:
  // if the backend ever computes per-month P&L / BS / CF series, restore them.
}


export function MonthlyFinance({ data }: { data?: MonthlyFinanceData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="monthly_finance" reason="no_trades" />;
  }
  // KPI cards are built only from metrics the backend actually computes; each
  // is elided when its source is missing (no fabricated placeholder values).
  const kpis = [
    data.navEomKpi
      ? { label: "NAV · EOM", value: data.navEomKpi.value, delta: data.navEomKpi.delta }
      : null,
    data.cashKpi
      ? { label: "Cash", value: data.cashKpi.value, delta: data.cashKpi.delta }
      : null,
    data.liquidityKpi
      ? { label: "Liquidity Ratio", value: data.liquidityKpi.value, delta: data.liquidityKpi.delta }
      : null,
    data.runwayKpi
      ? { label: "Runway · months", value: data.runwayKpi.value, delta: data.runwayKpi.delta }
      : null,
  ].filter((k): k is NonNullable<typeof k> => k !== null);

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
            Cash, runway, commissions and estimated tax drag — a descriptive
            snapshot of your own numbers.
          </PdfCoverSub>
        </div>

        <div style={{ marginTop: "auto", paddingTop: "30mm" }}>
          <PdfCoverMetaGrid
            items={[
              { label: "NAV · EOM", value: data.navEom },
              { label: "As of", value: data.asOf || "—" },
              { label: "Issued", value: data.issued },
            ]}
          />
        </div>

        <PdfCoverFoot />
      </PdfPage>

      {/* PAGE 2 — CASH KPIs + COST / TAX LEDGER
          Income Statement, Balance Sheet, Cash Flow, Key Ratios and Liquidity
          Tiers surfaces were removed (option-b, CEO 2026-05-31 "있는 데이터로만"):
          the backend computes a personal cash/cost/tax statement, not a
          corporate P&L / balance sheet / cash-flow statement, so those had no
          real source. The KPI row + observed cost/tax ledgers below are wired
          from data_json via _monthly_finance_preview_shape. */}
      <PdfPage compact>
        <PdfHeader tier="premium" title="MONTHLY FINANCE" meta={`${data.doc} · 02/02`} />
        <PdfGoldRule />

        {kpis.length > 0 ? <PdfKpiRow kpis={kpis} /> : null}

        <PdfSectionTitle variant="dry">Cost Ledger · 수수료·세금 추정 (estimates)</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Item</th>
              <th>Detail</th>
              <th className="right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {data.costRows.map((r) => (
              <tr key={r.label}>
                <td><strong>{r.label}</strong></td>
                <td>{r.detail ?? ""}</td>
                <td className="right font-mono">{r.amount}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfSectionTitle variant="dry">Tax Drag · 세금 추정 (estimates)</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Item</th>
              <th>Detail</th>
              <th className="right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {data.taxRows.map((r) => (
              <tr key={r.label}>
                <td><strong>{r.label}</strong></td>
                <td>{r.detail ?? ""}</td>
                <td className="right font-mono">{r.amount}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfGovBlock />
        <PdfPageFooter left="Monthly Finance · Premium · Internal" right="Page 02" />
        <PdfDisclaimer cadence="monthly" />
      </PdfPage>
    </>
  );
}
