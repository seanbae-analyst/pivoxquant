/**
 * Report 06 — Quarterly Self Report (Pro · 2 pages · Quarterly)
 *
 * Source: /design_handoff_pdf_reports/reports/06_quarterly_self_report.html
 *
 * Page 1: Cover headline + 4-up KPI row + decision quality table
 *         (decision / date / thesis / outcome / process / verdict).
 * Page 2: Alpha attribution alloc bars + bias audit checklist + 3 mistake cards
 *         + next-quarter promise callout + sign row + governance + disclaimer.
 *
 * Compliance: Verdict labels are decision-quality classifications (SKILL/LUCK/
 * DISCIPLINE/PROCESS+), not signal labels. No buy/sell/hold language.
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
  PdfCheckList,
  PdfCard,
  PdfCallout,
  PdfSignRow,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

export interface QuarterlySelfReportData {
  quarter: string; // "Q1 2026 · QSR-2026-04"
  intro: string;
  kpis: {
    quarterReturn: { value: string; bench: string };
    alpha: { value: string; sharpe: string };
    hitRate: { value: string; target: string };
    process: { value: string; prev: string };
  };
  decisions: {
    ticker: string;
    name: string;
    action: string;
    date: string;
    thesis: string;
    outcome: string;
    outcomeTone: "pos" | "neg";
    process: string;
    verdict: string;
    verdictTone: "pos" | "neg" | "warn";
  }[];
  totalsRow: {
    decisionsCount: string;
    thesisCount: string;
    pnl: string;
    avgGrade: string;
    breakdown: string;
  };
  attribution: { name: string; pct: number; pctDisplay: string; tone: "pos" | "neg" | "neutral"; flat?: boolean }[];
  biasAudit: { name: string; question: string; score: string; checked: boolean }[];
  mistakes: { num: string; tag: string; body: string }[];
  promise: string;
}


const TONE_STYLE: Record<"pos" | "neg" | "warn" | "neutral", string | undefined> = {
  pos: "var(--r-pos)",
  neg: "var(--r-neg)",
  warn: "var(--r-warn)",
  neutral: undefined,
};

export function QuarterlySelfReport({ data }: { data?: QuarterlySelfReportData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="quarterly_self_report" reason="insufficient_history" />;
  }
  return (
    <>
      {/* ═══════ PAGE 1 ═══════ */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="QUARTERLY SELF REPORT"
          meta={`${data.quarter} · 01/03`}
        />
        <PdfGoldRule />


        <PdfEyebrow>Quarterly Self Report</PdfEyebrow>
        <PdfCoverTitle size={42}>
          Quarter close—<em>decision quality</em>,<br />
          not the headline return.
        </PdfCoverTitle>
        <p
          style={{
            color: "var(--r-ink-3)",
            marginTop: 12,
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
          }}
        className="font-serif" >
          {data.intro}
        </p>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            kpis={[
              {
                label: "Quarter Return",
                value: data.kpis.quarterReturn.value,
                delta: data.kpis.quarterReturn.bench,
                deltaTone: "pos",
              },
              {
                label: "Alpha (gross)",
                value: data.kpis.alpha.value,
                delta: data.kpis.alpha.sharpe,
              },
              {
                label: "Decision Hit Rate",
                value: data.kpis.hitRate.value,
                delta: data.kpis.hitRate.target,
              },
              {
                label: "Process Score",
                value: data.kpis.process.value,
                delta: data.kpis.process.prev,
                deltaTone: "warn",
              },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Decision Quality · 결정의 분해</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Decision</th>
              <th>Date</th>
              <th>Thesis 사전 기록</th>
              <th className="right">Outcome</th>
              <th className="right">Process</th>
              <th className="right">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {data.decisions.map((d, i) => (
              <tr key={i}>
                <td>
                  <PdfTicker>{d.ticker}</PdfTicker>{" "}
                  <span style={{ color: "var(--r-ink-3)" }}>{d.name}</span>{" "}
                  <strong>{d.action}</strong>
                </td>
                <td>{d.date}</td>
                <td>{d.thesis}</td>
                <td className={`right ${d.outcomeTone}`}>{d.outcome}</td>
                <td className="right">{d.process}</td>
                <td className="right" style={{ color: TONE_STYLE[d.verdictTone] }}>
                  {d.verdict}
                </td>
              </tr>
            ))}
            <tr className="total">
              <td colSpan={2}>
                <strong>{data.totalsRow.decisionsCount}</strong>
              </td>
              <td>{data.totalsRow.thesisCount}</td>
              <td className="right">{data.totalsRow.pnl}</td>
              <td className="right">{data.totalsRow.avgGrade}</td>
              <td className="right">{data.totalsRow.breakdown}</td>
            </tr>
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Quarterly Self Report · Pro" right="Page 01" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* ═══════ PAGE 2 ═══════ */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="QUARTERLY SELF REPORT"
          meta={`${data.quarter} · 02/03`}
        />
        <PdfGoldRule />

        <PdfSectionTitle variant="sm">Alpha Attribution · 어디서 알파가 왔나</PdfSectionTitle>

        {data.attribution.map((a, i) => {
          const pctClamped = Math.max(0, Math.min(100, a.pct));
          return (
            <div key={i} className="pq-pdf-alloc-row">
              <div><strong>{a.name}</strong></div>
              <div className={`pq-pdf-alloc-bar${a.flat ? " flat" : ""}`}>
                <i style={{ width: `${pctClamped}%` }} />
              </div>
              <div
                className="pq-pdf-alloc-pct"
                style={{ color: TONE_STYLE[a.tone] }}
              >
                {a.pctDisplay}
              </div>
            </div>
          );
        })}

        <div style={{ marginTop: 18 }}>
          <PdfTwoCol>
            <div>
              <PdfSectionTitle variant="sm">Bias Audit · 편향 점검</PdfSectionTitle>
              <PdfCheckList
                items={data.biasAudit.map((b) => ({
                  checked: b.checked,
                  body: (
                    <>
                      <strong>{b.name}</strong> — {b.question}
                    </>
                  ),
                  meta: b.score,
                }))}
              />
            </div>
            <div>
              <PdfSectionTitle variant="sm">Mistakes · 분기 실수 3개</PdfSectionTitle>
              {data.mistakes.map((m, i) => (
                <PdfCard key={i}>
                  <div className="pq-pdf-kpi-lbl">
                    {m.num} · {m.tag}
                  </div>
                  <p
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      lineHeight: 1.55,
                      marginTop: 6,
                    }}
                  >
                    {m.body}
                  </p>
                </PdfCard>
              ))}
            </div>
          </PdfTwoCol>
        </div>

        <div style={{ marginTop: 18 }}>
          <PdfCallout label="Next Quarter · One Promise">{data.promise}</PdfCallout>
        </div>

        <PdfSignRow
          left="투자자 서명 · _____________"
          right="날짜 · _____________"
        />

        <PdfGovBlock />

        <PdfPageFooter
          left="Quarterly Self Report · Pro · Not investment advice"
          right="Page 02"
        />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* ═══════ PAGE 3 — DISCLAIMER (atomic disclaim-only sheet) ═══════ */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="QUARTERLY SELF REPORT"
          meta={`${data.quarter} · 03/03`}
        />
        <PdfGoldRule />
        <PdfDisclaimer cadence="quarterly" />
      </PdfPage>
    </>
  );
}
