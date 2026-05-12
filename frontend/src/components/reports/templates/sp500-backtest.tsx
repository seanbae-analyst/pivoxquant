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
  PdfTwoCol,
  PdfColTitle,
  PdfAllocList,
  PdfCheckList,
  PdfCallout,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
  PdfFlexBetween,
} from "../pdf-primitives";

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

const DEFAULT: Sp500BacktestData = {
  asOf: "Apr 26, 2026 · BT-2026-04",
  cagr: { value: "+12.8%", delta: "vs S&P +9.2%" },
  sharpe: { value: "0.84", delta: "vs 0.52" },
  maxDd: { value: "−28.4%", delta: "2008-11" },
  hitRate: { value: "58%", delta: "monthly" },
  strategyDef:
    "Quality + Momentum 조합: S&P 500 유니버스에서 (1) ROIC top quintile, (2) Net debt/EBITDA < 2.5×, (3) 12-1 모멘텀 top quartile 교집합. 동일 비중 30종목, 월 1회 리밸런스. 베어 시장 시 현금 30% 룰.",
  annual: [
    { year: "2022", strategy: "−14.2%", strategyTone: "neg", benchmark: "−18.1%", benchmarkTone: "neg", excess: "+3.9%", excessTone: "pos", maxDd: "−22.4%" },
    { year: "2023", strategy: "+28.4%", strategyTone: "pos", benchmark: "+24.2%", benchmarkTone: "pos", excess: "+4.2%", excessTone: "pos", maxDd: "−9.8%" },
    { year: "2024", strategy: "+19.6%", strategyTone: "pos", benchmark: "+23.1%", benchmarkTone: "pos", excess: "−3.5%", excessTone: "neg", maxDd: "−7.2%" },
    { year: "2025", strategy: "+15.2%", strategyTone: "pos", benchmark: "+11.8%", benchmarkTone: "pos", excess: "+3.4%", excessTone: "pos", maxDd: "−11.4%" },
    { year: "2026 YTD", strategy: "+8.1%", strategyTone: "pos", benchmark: "+5.4%", benchmarkTone: "pos", excess: "+2.7%", excessTone: "pos", maxDd: "−5.8%" },
  ],
  totals: { strategy: "+1,184% (CAGR 12.8%)", benchmark: "+574% (CAGR 9.2%)", excess: "+3.6%/yr", maxDd: "−28.4%" },
  riskMetrics: [
    { name: "Volatility (ann.)", pct: 62, value: "15.2%" },
    { name: "Sortino", pct: 78, value: "1.18", tone: "pos" },
    { name: "Calmar", pct: 48, value: "0.45" },
    { name: "Beta vs S&P", pct: 88, value: "0.92", flat: true },
    { name: "Tracking Error", pct: 32, value: "5.8%", flat: true },
    { name: "Information Ratio", pct: 72, value: "0.62", tone: "pos" },
  ],
  stress: [
    { period: "2008-09 → 2009-03", event: "GFC", strategy: "−28.4%", benchmark: "−42.1%", verdict: "RESILIENT", verdictTone: "pos" },
    { period: "2020-02 → 2020-04", event: "COVID", strategy: "−18.2%", benchmark: "−24.8%", verdict: "RESILIENT", verdictTone: "pos" },
    { period: "2022-01 → 2022-10", event: "Rates + Tech", strategy: "−22.4%", benchmark: "−25.4%", verdict: "INLINE", verdictTone: "neutral" },
    { period: "2017", event: "Low-vol bull", strategy: "+14.2%", benchmark: "+21.8%", verdict: "UNDERPERF", verdictTone: "neg" },
  ],
  caveats: [
    { title: "Survivorship", body: "보정했지만 완전하지 않음. 실제 결과 −0.5%p 가능.", tag: "DATA" },
    { title: "Costs", body: "5bp 가정. 슬리피지·세금 추가 시 −1.0%p.", tag: "EXEC" },
    { title: "Regime", body: "저금리·미국 주도장 편향. 다음 20년 반복 보장 없음.", tag: "REGIME" },
  ],
  verdict:
    "알파 +3.6%/yr, Sharpe 0.84, MaxDD −28%. 지수 압도가 아닌 \"지지 않으면서 약간 이긴다\". 베어 시장 룰이 핵심 기여, 제거 시 알파 +1.2%로 축소.",
};

export function Sp500Backtest({ data = DEFAULT }: { data?: Sp500BacktestData }) {
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

        <PdfSectionTitle variant="sm">Equity Curve · 20Y</PdfSectionTitle>
        <PdfCard>
          <PdfFlexBetween>
            <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
              Cumulative Return · 2006-01 → 2026-04
            </div>
            <div style={{ display: "flex", gap: 14, fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)", }} className="font-mono" >
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#0e0e0e" }} />Strategy</span>
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#c0c0c0" }} />S&amp;P 500 TR</span>
            </div>
          </PdfFlexBetween>
          <svg viewBox="0 0 600 160" preserveAspectRatio="none" style={{ width: "100%", height: 160, marginTop: 12 }}>
            <defs>
              <linearGradient id="bt-fade" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#0e0e0e" stopOpacity=".18" />
                <stop offset="1" stopColor="#0e0e0e" stopOpacity="0" />
              </linearGradient>
            </defs>
            <line x1="0" y1="40" x2="600" y2="40" stroke="#ececec" strokeWidth="1" />
            <line x1="0" y1="80" x2="600" y2="80" stroke="#ececec" strokeWidth="1" />
            <line x1="0" y1="120" x2="600" y2="120" stroke="#ececec" strokeWidth="1" />
            <path d="M0,140 L40,134 L80,142 L120,150 L160,128 L200,108 L240,90 L280,98 L320,72 L360,84 L400,58 L440,48 L480,32 L520,42 L560,18 L600,10 L600,160 L0,160 Z" fill="url(#bt-fade)" opacity=".5" />
            <path d="M0,140 L40,134 L80,142 L120,150 L160,128 L200,108 L240,90 L280,98 L320,72 L360,84 L400,58 L440,48 L480,32 L520,42 L560,18 L600,10" stroke="#0e0e0e" strokeWidth="2" fill="none" />
            <path d="M0,140 L40,138 L80,146 L120,148 L160,134 L200,120 L240,108 L280,116 L320,98 L360,108 L400,88 L440,78 L480,64 L520,72 L560,52 L600,42" stroke="#c0c0c0" strokeWidth="1.4" fill="none" strokeDasharray="3 3" />
          </svg>
        </PdfCard>

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
        <PdfTwoCol>
          <div>
            <PdfAllocList
              items={data.riskMetrics.map((r) => ({
                name: <strong>{r.name}</strong>,
                pct: r.pct,
                pctDisplay: <span style={{ color: r.tone === "pos" ? "var(--r-pos)" : undefined }}>{r.value}</span>,
              }))}
            />
          </div>
          <div>
            <PdfColTitle>Drawdown Distribution</PdfColTitle>
            <PdfCard>
              <svg viewBox="0 0 300 120" preserveAspectRatio="none" style={{ width: "100%", height: 120 }}>
                {[
                  [10, 18], [40, 34], [70, 58], [100, 72], [130, 48],
                  [160, 32], [190, 20], [220, 12], [250, 6],
                ].map(([x, h], i) => (
                  <rect key={i} x={x} y="0" width="20" height={h} fill="#0e0e0e" />
                ))}
                <text x="20" y="115" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">−5</text>
                <text x="80" y="115" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">−15</text>
                <text x="140" y="115" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">−25</text>
                <text x="200" y="115" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">−35</text>
                <text x="260" y="115" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">−45%</text>
              </svg>
              <div style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)", marginTop: 8 }}>
                DD &gt; −15% 빈도: 24개월. 회복 평균 8.4개월. 최장 회복 18개월 (2008).
              </div>
            </PdfCard>
          </div>
        </PdfTwoCol>

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
