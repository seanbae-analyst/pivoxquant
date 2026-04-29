/**
 * Report 05 — Risk Board (Pro · 2 pages · Weekly)
 *
 * Source: /design_handoff_pdf_reports/reports/05_risk_board.html
 *
 * Page 1: Executive Summary (dl/dt/dd) + 4-up KPI row + Risk Limits
 *         (gauge bars with cap markers + status badges).
 * Page 2: Stress test waterfall + scenario table + correlation gauge +
 *         observed actions checklist + governance + disclaimer.
 *
 * Compliance: All risk metrics are observation labels (BREACH / OVER / OK).
 * No buy/sell/hold language. Pro tier requires GovBlock — included on page 2.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfGoldRule,
  PdfKpiRow,
  PdfSectionTitle,
  PdfHeat,
  PdfBadge,
  PdfLimitList,
  PdfWaterfall,
  PdfTable,
  PdfTwoCol,
  PdfCard,
  PdfCheckList,
  PdfGauge,
  PdfExecSum,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
} from "../pdf-primitives";

export interface RiskBoardData {
  weekTag: string; // "Week of Apr 26, 2026 · RB-2026-W17"
  asOfStamp: string; // "As of Apr 26, 2026 · 18:00 KST"
  // KPI row
  var95: { value: string; nav: string; tone: "green" | "amber" | "red" };
  beta: { value: string; band: string; tone: "green" | "amber" | "red" };
  maxDD: { value: string; limit: string; tone: "green" | "amber" | "red" };
  sharpe: { value: string; vsPrior: string; tone: "green" | "amber" | "red" };
  // Stress
  pairwiseCorr: { value: string; gauge: number; verdict: string };
}

const DEFAULT: RiskBoardData = {
  weekTag: "Week of Apr 26, 2026 · RB-2026-W17",
  asOfStamp: "As of Apr 26, 2026 · 18:00 KST",
  var95: { value: "−$18.2k", nav: "−1.46% NAV", tone: "amber" },
  beta: { value: "1.18", band: "target 0.9–1.1", tone: "amber" },
  maxDD: { value: "−9.8%", limit: "limit −12%", tone: "green" },
  sharpe: { value: "1.42", vsPrior: "+0.08 vs prior", tone: "green" },
  pairwiseCorr: {
    value: "0.62",
    gauge: 62,
    verdict: "Tech 비중 과다로 분산 효과 약화. 스트레스 시 단일 섹터처럼 움직임. 비테크 자산 5%p 추가 또는 헤지 검토.",
  },
};

export function RiskBoard({ data = DEFAULT }: { data?: RiskBoardData }) {
  return (
    <>
      {/* ═══════ PAGE 1 — EXECUTIVE SUMMARY + LIMITS ═══════ */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="RISK BOARD · WEEKLY"
          meta={`${data.weekTag} · 01/02`}
        />

        <PdfExecSum
          stamp={data.asOfStamp}
          rows={[
            {
              term: "Status",
              body: (
                <>
                  <PdfBadge tone="moderate">⚠ AMBER</PdfBadge>{" "}
                  &nbsp;2개 한도 초과 (FX exposure, Single sector).{" "}
                  <strong>즉시 조치 1건</strong>, 다음 리밸런스 조정 1건.
                </>
              ),
            },
            {
              term: "Headline Risk",
              body: (
                <>
                  <strong>섹터 집중</strong> — Tech 단일 섹터 NAV의 42% (한도 35%).
                  반도체 묶음이 전체 VaR의 38% 기여.
                </>
              ),
            },
            {
              term: "Stress Worst",
              body: (
                <>
                  <strong>2008 Replay 시 −$498k (−40% NAV).</strong> 5개 시나리오 중 1개
                  SEVERE, 1개 HIGH, 3개 MODERATE.
                </>
              ),
            },
            {
              term: "This Week",
              body: (
                <>
                  VaR(95%) <strong>−$18.2k</strong> (−1.46% NAV) · Beta vs S&amp;P{" "}
                  <strong>1.18</strong> (band 0.9–1.1 초과) · MaxDD YTD <strong>−9.8%</strong>{" "}
                  (limit −12%).
                </>
              ),
            },
            {
              term: "Action P1",
              body: "다음 리밸런스 시 Tech 섹터 −7%p 축소 → 한도 복귀. 단일 종목 12% → 8% 단계적 축소.",
            },
          ]}
        />

        <PdfKpiRow
          kpis={[
            {
              label: "VaR · 95% 1d",
              value: data.var95.value,
              delta: (
                <>
                  {data.var95.nav} ·{" "}
                  <PdfHeat tone={data.var95.tone}>{data.var95.tone.toUpperCase()}</PdfHeat>
                </>
              ),
              deltaTone: "neg",
            },
            {
              label: "Beta vs S&P",
              value: data.beta.value,
              delta: (
                <>
                  {data.beta.band} · <PdfHeat tone={data.beta.tone}>OVER</PdfHeat>
                </>
              ),
              deltaTone: "warn",
            },
            {
              label: "Max Drawdown YTD",
              value: data.maxDD.value,
              delta: (
                <>
                  {data.maxDD.limit} · <PdfHeat tone={data.maxDD.tone}>OK</PdfHeat>
                </>
              ),
            },
            {
              label: "Sharpe · 12M",
              value: data.sharpe.value,
              delta: (
                <>
                  {data.sharpe.vsPrior} · <PdfHeat tone={data.sharpe.tone}>OK</PdfHeat>
                </>
              ),
              deltaTone: "pos",
            },
          ]}
        />

        <PdfSectionTitle variant="dry">
          Risk Limits <small>한도 점검 · vs cap</small>
        </PdfSectionTitle>

        <PdfLimitList
          items={[
            {
              name: "Sector concentration",
              detail: "Tech",
              fillPct: 84,
              capPct: 70,
              valueLabel: "42% / 35%",
              fillState: "breach",
              status: <PdfBadge tone="severe">BREACH</PdfBadge>,
            },
            {
              name: "FX exposure",
              detail: "USD single",
              fillPct: 88,
              capPct: 75,
              valueLabel: "88% / 75%",
              fillState: "warn",
              status: <PdfBadge tone="moderate">OVER</PdfBadge>,
            },
            {
              name: "Top 3 concentration",
              detail: "Top 3 names",
              fillPct: 62,
              capPct: 70,
              valueLabel: "62% / 70%",
              status: <PdfBadge tone="low">OK</PdfBadge>,
            },
            {
              name: "Leverage",
              detail: "gross / NAV",
              fillPct: 50,
              capPct: 60,
              valueLabel: "1.00× / 1.20×",
              status: <PdfBadge tone="low">OK</PdfBadge>,
            },
            {
              name: "Crypto exposure",
              detail: "direct + ETF",
              fillPct: 30,
              capPct: 100,
              valueLabel: "3% / 10%",
              status: <PdfBadge tone="low">OK</PdfBadge>,
            },
          ]}
        />

        <PdfPageFooter
          left="Risk Board · Pro · Internal use only"
          right="Page 01"
        />
        <PdfDisclaimer cadence="weekly" />
      </PdfPage>

      {/* ═══════ PAGE 2 — STRESS TESTS + ACTIONS ═══════ */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="RISK BOARD · WEEKLY"
          meta={`${data.weekTag} · 02/02`}
        />
        <PdfGoldRule />

        <PdfSectionTitle variant="dry">
          Stress Test Impact <small>P&amp;L 충격 · 5 scenarios</small>
        </PdfSectionTitle>

        <PdfCard>
          <PdfWaterfall
            items={[
              {
                label: "2008 Replay",
                detail: "−40% equity, +200bp credit",
                leftPct: 0,
                widthPct: 90,
                axisPct: 90,
                value: "−$498k",
                valueTone: "neg",
              },
              {
                label: "2022 Tech Crash",
                detail: "QQQ −33% / 12mo",
                leftPct: 32,
                widthPct: 58,
                axisPct: 90,
                value: "−$324k",
                valueTone: "neg",
              },
              {
                label: "Geopolitical Shock",
                detail: "Oil +50%, VIX > 40",
                leftPct: 55,
                widthPct: 35,
                axisPct: 90,
                value: "−$186k",
                valueTone: "neg",
              },
              {
                label: "USD −10%",
                detail: "DXY 104 → 94",
                leftPct: 70,
                widthPct: 20,
                axisPct: 90,
                value: "−$108k",
                valueTone: "neg",
              },
              {
                label: "Rates +100bp",
                detail: "10Y 4.2 → 5.2",
                leftPct: 77,
                widthPct: 13,
                axisPct: 90,
                value: "−$72k",
                valueTone: "neg",
              },
            ]}
          />
        </PdfCard>

        <div style={{ marginTop: 12 }}>
          <PdfTable>
            <thead>
              <tr>
                <th>Scenario</th>
                <th className="right">P&amp;L</th>
                <th className="right">% NAV</th>
                <th className="right">NAV After</th>
                <th className="right">Recovery</th>
                <th className="right">Verdict</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>2008 Replay</strong></td>
                <td className="right neg">−$498k</td>
                <td className="right neg">−40.1%</td>
                <td className="right">$744k</td>
                <td className="right">~36 mo</td>
                <td className="right"><PdfBadge tone="severe">SEVERE</PdfBadge></td>
              </tr>
              <tr>
                <td><strong>2022 Tech Crash</strong></td>
                <td className="right neg">−$324k</td>
                <td className="right neg">−26.1%</td>
                <td className="right">$918k</td>
                <td className="right">~18 mo</td>
                <td className="right"><PdfBadge tone="high">HIGH</PdfBadge></td>
              </tr>
              <tr>
                <td><strong>Geopolitical</strong></td>
                <td className="right neg">−$186k</td>
                <td className="right neg">−15.0%</td>
                <td className="right">$1,056k</td>
                <td className="right">~9 mo</td>
                <td className="right"><PdfBadge tone="moderate">MODERATE</PdfBadge></td>
              </tr>
              <tr>
                <td><strong>USD −10%</strong></td>
                <td className="right neg">−$108k</td>
                <td className="right neg">−8.7%</td>
                <td className="right">$1,134k</td>
                <td className="right">~6 mo</td>
                <td className="right"><PdfBadge tone="moderate">MODERATE</PdfBadge></td>
              </tr>
              <tr>
                <td><strong>Rates +100bp</strong></td>
                <td className="right neg">−$72k</td>
                <td className="right neg">−5.8%</td>
                <td className="right">$1,170k</td>
                <td className="right">~4 mo</td>
                <td className="right"><PdfBadge tone="moderate">MODERATE</PdfBadge></td>
              </tr>
            </tbody>
          </PdfTable>
        </div>

        <div style={{ marginTop: 18 }}>
          <PdfTwoCol>
            <PdfCard>
              <div
                className="pq-pdf-kpi-lbl"
                style={{ marginBottom: 8 }}
              >
                AVG PAIRWISE CORR
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: 10,
                  margin: "8px 0",
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontSize: 36,
                    fontWeight: 500,
                    lineHeight: 1,
                  }}
                >
                  {data.pairwiseCorr.value}
                </div>
                <PdfBadge tone="moderate">CONCENTRATED</PdfBadge>
              </div>
              <PdfGauge
                fillPct={data.pairwiseCorr.gauge}
                scaleLeft="0.0 diversified"
                scaleRight="1.0 concentrated"
              />
              <p
                style={{
                  fontSize: 11,
                  color: "var(--r-ink-3)",
                  lineHeight: 1.5,
                  marginTop: 10,
                }}
              >
                {data.pairwiseCorr.verdict}
              </p>
            </PdfCard>

            <PdfCard>
              <div className="pq-pdf-kpi-lbl" style={{ marginBottom: 8 }}>
                REBALANCE NOTES · OBSERVED
              </div>
              <PdfCheckList
                items={[
                  {
                    body: <><strong>P1</strong> · Tech 섹터 −7%p · 한도 복귀</>,
                    meta: "By May 5",
                  },
                  {
                    body: <><strong>P2</strong> · FX 헤지 USD 25% 추가</>,
                    meta: "By May 10",
                  },
                  {
                    body: <><strong>P2</strong> · 금/장기채 +3%p · 테일 헤지</>,
                    meta: "By May 10",
                  },
                  {
                    body: <><strong>P3</strong> · 단일 종목 12% → 8% 단계 익절</>,
                    meta: "By May 31",
                  },
                ]}
              />
            </PdfCard>
          </PdfTwoCol>
        </div>

        <PdfGovBlock />

        <PdfPageFooter
          left="Risk Board · Pro · Internal"
          right="Page 02"
        />
        <PdfDisclaimer cadence="weekly" />
      </PdfPage>
    </>
  );
}
