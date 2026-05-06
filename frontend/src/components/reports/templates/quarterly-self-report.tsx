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

const DEFAULT: QuarterlySelfReportData = {
  quarter: "Q1 2026 · QSR-2026-04",
  intro:
    "A quarterly cut that separates luck from skill — and asks whether next quarter can repeat it.",
  kpis: {
    quarterReturn: { value: "+5.8%", bench: "vs S&P +3.2%" },
    alpha: { value: "+2.6%", sharpe: "Sharpe 0.94" },
    hitRate: { value: "62%", target: "target ≥ 55%" },
    process: { value: "7.2 / 10", prev: "prev 6.8" },
  },
  decisions: [
    { ticker: "PLTR", action: "비중 +3.5%p", date: "9/18", thesis: "✓ 9/12 메모", outcome: "+35.0%", outcomeTone: "pos", process: "A", verdict: "SKILL", verdictTone: "pos" },
    { ticker: "NVDA", action: "일부 익절", date: "8/04", thesis: "✓ 한도 초과", outcome: "−8.4% (기회)", outcomeTone: "neg", process: "A", verdict: "DISCIPLINE", verdictTone: "warn" },
    { ticker: "TSLA", action: "단기 모멘텀 매수", date: "7/22", thesis: "✗ 사전 기록 없음", outcome: "+9.2%", outcomeTone: "pos", process: "D", verdict: "LUCK", verdictTone: "neg" },
    { ticker: "META", action: "비중 −2%p", date: "8/19", thesis: "△ 부분", outcome: "−4.1%", outcomeTone: "neg", process: "B", verdict: "PROCESS+", verdictTone: "warn" },
    { ticker: "SMH", action: "신규 진입", date: "9/30", thesis: "✓ DD 체크리스트", outcome: "+6.8%", outcomeTone: "pos", process: "A", verdict: "SKILL", verdictTone: "pos" },
  ],
  totalsRow: {
    decisionsCount: "Q3 총 18개 의사결정",
    thesisCount: "사전 기록 11/18 · 61%",
    pnl: "+5.8%",
    avgGrade: "평균 B+",
    breakdown: "SKILL 7 · LUCK 4 · 기타 7",
  },
  attribution: [
    { name: "Stock Selection", pct: 78, pctDisplay: "+1.94%p", tone: "pos" },
    { name: "Sector Tilt", pct: 42, pctDisplay: "+0.62%p", tone: "pos" },
    { name: "Timing", pct: 18, pctDisplay: "−0.18%p", tone: "neg", flat: true },
    { name: "Cash Drag", pct: 8, pctDisplay: "−0.12%p", tone: "neg", flat: true },
    { name: "FX", pct: 14, pctDisplay: "+0.34%p", tone: "neutral", flat: true },
  ],
  biasAudit: [
    { name: "Confirmation", question: "반대 의견 적극 탐색했는가", score: "7/9", checked: true },
    { name: "Anchoring", question: "진입가에 매여 있지 않았는가", score: "6/9", checked: true },
    { name: "Recency", question: "최근 사건에 과반응하지 않았는가", score: "4/9", checked: false },
    { name: "Loss Aversion", question: "손절 룰 지켰는가", score: "8/9", checked: true },
    { name: "Overconfidence", question: "베이스 시나리오 확률 보정", score: "5/9", checked: false },
  ],
  mistakes: [
    {
      num: "01",
      tag: "Recency Bias",
      body: "단기 모멘텀 추종 매수, 가설 메모 없음. 결과 +9.2%지만 운에 가까움. 7월 단일 종목 매수는 순전히 단기 모멘텀 추종. 기록 없음, 가설 없음.",
    },
    {
      num: "02",
      tag: "Anchoring",
      body: "평단 집착으로 청산 시점 +2주 지연. 기회비용 −4.1%.",
    },
    {
      num: "03",
      tag: "Position Size",
      body: "신규 진입 평균 사이즈 1.8%로 다소 보수적. 다음 분기 2.5%로 확대 검토.",
    },
  ],
  promise:
    "다음 분기 단 하나의 약속 — 모든 신규 진입 전 가설 메모 작성, 예외 없음.",
};

const TONE_STYLE: Record<"pos" | "neg" | "warn" | "neutral", string | undefined> = {
  pos: "var(--r-pos)",
  neg: "var(--r-neg)",
  warn: "var(--r-warn)",
  neutral: undefined,
};

export function QuarterlySelfReport({ data = DEFAULT }: { data?: QuarterlySelfReportData }) {
  return (
    <>
      {/* ═══════ PAGE 1 ═══════ */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="QUARTERLY SELF REPORT"
          meta={`${data.quarter} · 01/02`}
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
            fontSize: 13,
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
                  <PdfTicker>{d.ticker}</PdfTicker>
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

      {/* ═══════ PAGE 2 ═══════
          2026-05-06 Strategy B: compact so body+gov+disclaim atomic fits one A4 sheet
          (prevents disclosure-only ghost page push by chromium print engine). */}
      <PdfPage compact>
        <PdfHeader
          tier="pro"
          title="QUARTERLY SELF REPORT"
          meta={`${data.quarter} · 02/02`}
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
                      fontSize: 12,
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
        <PdfDisclaimer cadence="quarterly" />
      </PdfPage>
    </>
  );
}
