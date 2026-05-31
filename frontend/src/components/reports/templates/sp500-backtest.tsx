/**
 * Report 11 — S&P 500 Backtest (Pro · 2 pages · On-demand)
 *
 * Source: /design_handoff_pdf_reports/reports/11_sp500_backtest.html
 *
 * Page 1: 4-up KPI (CAGR / Sharpe / MaxDD / Hit Rate) + Strategy Definition card
 *         + 20Y Equity Curve + Annual Returns table.
 * Page 2: Risk Metrics alloc bars + Drawdown Distribution chart + Stress Periods table
 *         + Caveats checklist + Verdict callout + governance + disclaimer.
 *
 * Compliance: Backtest disclaimer required (withBacktest: true). Past performance
 * does NOT guarantee future returns. POSITIVE/NEGATIVE/NEUTRAL labels only.
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
  PdfCard,
  PdfTable,
  PdfAllocList,
  PdfCheckList,
  PdfCallout,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

interface AnnualRow {
  year: string;
  strategy: string;
  strategyTone: "pos" | "neg";
  benchmark: string;
  benchmarkTone: "pos" | "neg";
  excess: string;
  excessTone: "pos" | "neg";
  maxDd: string;
}
interface StressRow {
  period: string;
  event: string;
  strategy: string;
  benchmark: string;
  verdict: string;
  verdictTone: "pos" | "neg" | "neutral";
}

export interface Sp500BacktestData {
  asOf: string;
  cagr: { value: string; delta: string };
  sharpe: { value: string; delta: string };
  maxDd: { value: string; delta: string };
  hitRate: { value: string; delta: string };
  strategyDef: string;
  annual: AnnualRow[];
  totals: { strategy: string; benchmark: string; excess: string; maxDd: string };
  riskMetrics: { name: string; pct: number; value: string; flat?: boolean; tone?: "pos" }[];
  stress: StressRow[];
  caveats: { title: string; body: string; tag: string }[];
  verdict: string;
}


export function Sp500Backtest({ data }: { data?: Sp500BacktestData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="sp500_backtest" reason="insufficient_history" />;
  }
  return (
    <>
      {/* PAGE 1 */}
      <PdfPage>
        <PdfHeader tier="pro" title="S&P 500 BACKTEST" meta={`${data.asOf} · 01/03`} />
        <PdfGoldRule />


        <PdfEyebrow>Strategy Backtest · S&amp;P 500 Universe</PdfEyebrow>
        <PdfCoverTitle size={42}>
          <em>Quality + Momentum</em>—
          <br />
          twenty years, honestly backtested.
        </PdfCoverTitle>
        <p style={{ color: "var(--r-ink-3)", fontSize: "var(--pq-text-body)", lineHeight: 1.55, marginTop: 12 }}>
          5bp costs · monthly rebalance · survivorship-bias adjusted · no look-ahead · in-sample / out-of-sample split.
        </p>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            kpis={[
              { label: "CAGR", value: data.cagr.value, delta: data.cagr.delta, deltaTone: "pos" },
              { label: "Sharpe", value: data.sharpe.value, delta: data.sharpe.delta },
              { label: "Max DD", value: data.maxDd.value, delta: data.maxDd.delta, deltaTone: "neg" },
              { label: "Hit Rate", value: data.hitRate.value, delta: data.hitRate.delta },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Strategy Definition · 전략 정의</PdfSectionTitle>
        <PdfCard>
          <p style={{ fontSize: "var(--pq-text-body)", lineHeight: 1.7, color: "var(--r-ink-2)", }} className="font-serif" >
            {data.strategyDef}
          </p>
        </PdfCard>

        {/* Equity Curve chart omitted: no cumulative-return series is wired
            into Sp500BacktestData. Fixed SVG path coordinates + the static
            "2006-01 → 2026-04" range would be a fabricated curve (CEO
            2026-05-31). Carry-over: wire backend equity-curve series. */}

        {/* 2026-05-05 V5 layout: wrap header + table together so the
            orphan-header pattern (header on p1, table on p2) cannot
            occur. .pq-pdf-section gets break-inside: avoid in print. */}
        <div className="pq-pdf-section">
          <PdfSectionTitle variant="sm">Annual Returns · 연간</PdfSectionTitle>
          <PdfTable>
            <thead>
              <tr>
                <th>Year</th>
                <th className="right">Strategy</th>
                <th className="right">S&amp;P 500</th>
                <th className="right">Excess</th>
                <th className="right">Max DD</th>
              </tr>
            </thead>
            <tbody>
              {data.annual.map((a) => (
                <tr key={a.year}>
                  <td>{a.year}</td>
                  <td className={`right ${a.strategyTone}`}>{a.strategy}</td>
                  <td className={`right ${a.benchmarkTone}`}>{a.benchmark}</td>
                  <td className={`right ${a.excessTone}`}>{a.excess}</td>
                  <td className="right">{a.maxDd}</td>
                </tr>
              ))}
              <tr className="total">
                <td><strong>20Y</strong></td>
                <td className="right">{data.totals.strategy}</td>
                <td className="right">{data.totals.benchmark}</td>
                <td className="right">{data.totals.excess}</td>
                <td className="right">{data.totals.maxDd}</td>
              </tr>
            </tbody>
          </PdfTable>
        </div>

        <PdfPageFooter left="S&P 500 Backtest · Pro" right="Page 01" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 2 — Risk Metrics + Stress Periods
          2026-05-06: split former PAGE 2 (Risk + Stress + Caveats +
          Verdict + Gov + Disclaim) into two logical PdfPages so the
          final page anchors gov+disclaim properly with `margin-top:
          auto` instead of overflowing to a near-empty 3rd sheet. */}
      <PdfPage>
        <PdfHeader tier="pro" title="S&P 500 BACKTEST" meta={`${data.asOf} · 02/03`} />
        <PdfGoldRule />

        <PdfSectionTitle variant="sm">Risk Metrics · 위험 지표</PdfSectionTitle>
        {/* Drawdown Distribution chart + DD-frequency/recovery narrative omitted:
            neither the histogram series nor the DD statistics are wired into
            Sp500BacktestData. Fixed SVG bars + a frequency/recovery narrative
            would be fabricated figures (CEO 2026-05-31). Carry-over: wire backend DD
            distribution + recovery stats. Risk Metrics (real data) retained. */}
        <PdfAllocList
          items={data.riskMetrics.map((r) => ({
            name: <strong>{r.name}</strong>,
            pct: r.pct,
            pctDisplay: <span style={{ color: r.tone === "pos" ? "var(--r-pos)" : undefined }}>{r.value}</span>,
          }))}
        />

        <PdfSectionTitle variant="sm">Stress Periods · 약점 구간</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Period</th>
              <th>Event</th>
              <th className="right">Strategy</th>
              <th className="right">S&amp;P 500</th>
              <th className="right">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {data.stress.map((s) => (
              <tr key={s.period}>
                <td>{s.period}</td>
                <td>{s.event}</td>
                <td className="right neg">{s.strategy}</td>
                <td className="right neg">{s.benchmark}</td>
                <td className="right" style={{ color: s.verdictTone === "pos" ? "var(--r-pos)" : s.verdictTone === "neg" ? "var(--r-neg)" : undefined }}>
                  {s.verdict}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="S&P 500 Backtest · Pro · Past performance ≠ future results" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — Caveats + Verdict + Gov + Full Disclaim */}
      <PdfPage>
        <PdfHeader tier="pro" title="S&P 500 BACKTEST" meta={`${data.asOf} · 03/03`} />
        <PdfGoldRule />

        <PdfSectionTitle variant="sm">Caveats · 정직하게 말하면</PdfSectionTitle>
        <PdfCheckList
          items={data.caveats.map((c) => ({
            checked: false,
            body: <><strong>{c.title}</strong> — {c.body}</>,
            meta: c.tag,
          }))}
        />

        <div style={{ marginTop: 18 }}>
          <PdfCallout flat label="Verdict">{data.verdict}</PdfCallout>
        </div>

        <PdfGovBlock />
        <PdfPageFooter left="S&P 500 Backtest · Pro · Past performance ≠ future results" right="Page 03" />
        <PdfDisclaimer cadence="ondemand" withBacktest />
      </PdfPage>
    </>
  );
}
