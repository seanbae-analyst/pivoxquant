/**
 * Report 17 — KPI Dashboard (Premium · 3 pages · Monthly)
 *
 * Source: /design_handoff_pdf_reports/reports/17_kpi_dashboard.html
 *
 * Page 1: **DARK IC-PACK COVER** — the only dark cover in the 18-report system.
 *         Black background (#0e0e0e), gold accent + white type.
 *         IC eyebrow + IC title + sub + 4-up marquee at bottom + IC foot.
 * Page 2: Executive Summary + 12-row Performance Scorecard table (KPI vs target with heat tags).
 * Page 3: Decisions Log table + 3-up Decisions This Period cards + 12M KPI Trend chart
 *         + governance + disclaimer.
 *
 * Compliance: IC pack — internal use only. Decisions table uses BUY/SELL labels
 * as historical decision log entries (not current advice). Outcomes are factual.
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
  PdfSectionTitle,
  PdfTable,
  PdfHeat,
  PdfThreeCol,
  PdfCard,
  PdfFlexBetween,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";

interface ScoreRow {
  kpi: string;
  mtd: string;
  ytd: string;
  m12: string;
  target: string;
  status: { tone: "green" | "amber" | "red"; label: string };
}
interface DecisionRow {
  date: string;
  decision: string;
  thesis: string;
  size: string;
  result: string;
  resultTone?: "pos" | "neg";
  verdict: { tone: "low" | "moderate" | "severe" | "high" | "neutral" | "info"; label: string };
}
interface DecisionCard {
  priority: string;
  title: string;
  body: string;
  badge: { tone: "severe" | "moderate" | "info"; label: string };
}

export interface KpiDashboardData {
  doc: string;
  navEom: string;
  navEomDelta: string;
  ytdReturn: string;
  ytdDelta: string;
  sharpe: string;
  sharpeDelta: string;
  status: string;
  statusDelta: string;
  issued: string;
  scorecard: ScoreRow[];
  decisions: DecisionRow[];
  decisionCards: DecisionCard[];
}

const DEFAULT: KpiDashboardData = {
  doc: "Apr 2026 · KPI-2026-04 · 01/04",
  navEom: "$1,242k",
  navEomDelta: "+$50.7k MTD",
  ytdReturn: "+14.2%",
  ytdDelta: "vs S&P +9.4% · α +4.8%p",
  sharpe: "1.42",
  sharpeDelta: "+0.08 vs prior",
  status: "AMBER",
  statusDelta: "2 limits over · 1 P1 action",
  issued: "Issued · May 1, 2026",
  scorecard: [
    { kpi: "Total Return", mtd: "+4.2%", ytd: "+14.2%", m12: "+22.8%", target: "+12% / yr", status: { tone: "green", label: "ABOVE" } },
    { kpi: "Alpha vs S&P", mtd: "+1.1%p", ytd: "+4.8%p", m12: "+3.6%p", target: "≥ 2%p / yr", status: { tone: "green", label: "ABOVE" } },
    { kpi: "Sharpe Ratio", mtd: "—", ytd: "—", m12: "1.42", target: "≥ 1.20", status: { tone: "green", label: "ABOVE" } },
    { kpi: "Max Drawdown", mtd: "−2.1%", ytd: "−9.8%", m12: "−14.2%", target: "≥ −12% / yr", status: { tone: "green", label: "OK" } },
    { kpi: "Beta vs S&P", mtd: "1.18", ytd: "1.14", m12: "1.12", target: "0.9–1.1 band", status: { tone: "amber", label: "OVER" } },
    { kpi: "Sector Concentration", mtd: "42% Tech", ytd: "—", m12: "38% avg", target: "≤ 35% any", status: { tone: "red", label: "BREACH" } },
    { kpi: "FX Single Exposure", mtd: "88% USD", ytd: "—", m12: "85% avg", target: "≤ 75% any", status: { tone: "amber", label: "OVER" } },
    { kpi: "Turnover", mtd: "3.8%", ytd: "42%", m12: "58%", target: "≤ 60% / yr", status: { tone: "green", label: "OK" } },
    { kpi: "Trading Cost", mtd: "−0.02%", ytd: "−0.09%", m12: "−0.14%", target: "≤ −0.20% / yr", status: { tone: "green", label: "OK" } },
    { kpi: "Tax Drag", mtd: "−0.31%", ytd: "−1.19%", m12: "−1.62%", target: "≤ −2.0% / yr", status: { tone: "green", label: "OK" } },
    { kpi: "Decision Quality", mtd: "75%", ytd: "88%", m12: "86%", target: "100% memo", status: { tone: "amber", label: "BELOW" } },
    { kpi: "Process Integrity", mtd: "96/100", ytd: "94/100", m12: "93/100", target: "≥ 90/100", status: { tone: "green", label: "OK" } },
  ],
  decisions: [
    { date: "Feb 12", decision: "ENTRY · NVDA", thesis: "AI capex 가속 + 가격 결정력", size: "+2.5%p", result: "+22%", resultTone: "pos", verdict: { tone: "low", label: "WORKED" } },
    { date: "Feb 28", decision: "TRIM · DIS (50%)", thesis: "스트리밍 비용 + 가이던스 하향", size: "−1.2%p", result: "avoided −8%", resultTone: "pos", verdict: { tone: "low", label: "WORKED" } },
    { date: "Mar 18", decision: "ENTRY · UNH", thesis: "낙폭 과대 + 펀더 견고", size: "+1.5%p", result: "−6%", resultTone: "neg", verdict: { tone: "moderate", label: "WATCH" } },
    { date: "Apr 4", decision: "HEDGE · USD 15%", thesis: "FX 단일 노출 92% 위험", size: "notional 15%", result: "+0.3%p net", verdict: { tone: "low", label: "WORKED" } },
    { date: "Apr 22", decision: "ENTRY · 미들캡 모멘텀", thesis: "메모 누락", size: "+0.8%p", result: "+4%", resultTone: "pos", verdict: { tone: "moderate", label: "RULE BREACH" } },
  ],
  decisionCards: [
    { priority: "P1 · By May 5", title: "Tech 섹터 −7%p", body: "한도 35% 복귀. NVDA 12% → 8%, AVGO 9% → 7%. 자본은 헬스케어 + Cash 보강.", badge: { tone: "severe", label: "BREACH 해소" } },
    { priority: "P2 · By May 10", title: "FX 헤지 USD 25%", body: "USD 단일 노출 88% → 65% 효과. 헤지 비용 연 ~0.4% 감수. 원달러 −5% 시 NAV 보호 +$28k.", badge: { tone: "moderate", label: "OVER 해소" } },
    { priority: "P3 · By May 31", title: "DD 메모 100% 룰화", body: "신규 진입 전 가설 메모 의무화. 4월 75%에서 100%로. 메모 없는 매입 자동 알림.", badge: { tone: "info", label: "PROCESS" } },
  ],
};

export function KpiDashboard({ data = DEFAULT }: { data?: KpiDashboardData }) {
  return (
    <>
      {/* PAGE 1 — COVER (light, matches other Premium covers per CEO 2026-04-27) */}
      <PdfPage>
        <PdfHeader tier="premium" title="KPI DASHBOARD · IC PACK" meta={data.doc} />

        <div style={{ marginTop: "30mm" }}>
          <PdfCoverEyebrow>Investment Committee Pack · Monthly</PdfCoverEyebrow>
          <PdfCoverTitle size={64}>
            April 2026 <em>KPI Dashboard.</em>
          </PdfCoverTitle>
          <PdfCoverSub>
            A single source of truth for the portfolio. One page, every metric that matters —
            return, risk, efficiency, decision quality. One decision this month, with its rationale.
          </PdfCoverSub>
        </div>

        <div style={{ marginTop: "auto", paddingTop: "30mm" }}>
          <PdfCoverMetaGrid
            items={[
              { label: "NAV · EOM", value: data.navEom },
              { label: "Return · YTD", value: data.ytdReturn },
              { label: "Sharpe · 12M", value: data.sharpe },
              { label: "Status", value: data.status },
            ]}
          />
        </div>

        <PdfCoverFoot left={data.issued} />
      </PdfPage>

      {/* PAGE 2 — EXECUTIVE SUMMARY + SCORECARD */}
      <PdfPage>
        <PdfHeader tier="premium" title="KPI DASHBOARD" meta="Apr 2026 · 02/04" />

        <PdfExecSum
          stamp="As of Apr 30, 2026 · 23:59 UTC"
          rows={[
            { term: "Period Return", body: <><strong>+4.2% MTD · +14.2% YTD</strong> — vs S&amp;P 500 +3.1% / +9.4%. <strong>Alpha +1.1%p / +4.8%p YTD.</strong></> },
            { term: "Risk Status", body: <><PdfBadge tone="moderate">⚠ AMBER</PdfBadge> VaR(95%) <strong>−$18.2k</strong> (−1.46% NAV). MaxDD YTD −9.8% (limit −12%, OK). Beta 1.18 (band 0.9–1.1, over). Sector Tech 42% (cap 35%, breach).</> },
            { term: "Operations", body: "Turnover 42% (cap 60%) · Trading cost −0.09% NAV YTD · Tax drag −1.19% NAV YTD · Process integrity 96/100." },
            { term: "Decision Quality", body: "신규 진입 4건 중 3건 가설 메모 완료 (목표 100%). 평균 보유 기간 168일 (목표 ≥ 90일, OK). 룰 위반 0건." },
            { term: "Committee Decision", body: <><strong>이번 달 단 하나의 결정 — 다음 리밸런스에 Tech 섹터 −7%p, FX 헤지 USD 25% 추가.</strong> P1 by May 5, P2 by May 10.</> },
          ]}
        />

        <PdfSectionTitle variant="dry">Performance Scorecard · vs targets (MoM)</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>KPI</th>
              <th className="right">MTD</th>
              <th className="right">YTD</th>
              <th className="right">12M</th>
              <th className="right">Target</th>
              <th className="right">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.scorecard.map((s) => (
              <tr key={s.kpi}>
                <td><strong>{s.kpi}</strong></td>
                <td className="right">{s.mtd}</td>
                <td className="right">{s.ytd}</td>
                <td className="right">{s.m12}</td>
                <td className="right">{s.target}</td>
                <td className="right">
                  <PdfHeat tone={s.status.tone}>{s.status.label}</PdfHeat>
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="KPI Dashboard · Premium · IC Pack" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — DECISIONS + GOVERNANCE */}
      <PdfPage>
        <PdfHeader tier="premium" title="KPI DASHBOARD" meta="Apr 2026 · 03/04" />
        <PdfGoldRule />

        <PdfSectionTitle variant="dry">Decisions Log · 이번 분기 결정과 결과</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Date</th>
              <th>Decision</th>
              <th>Thesis</th>
              <th className="right">Size</th>
              <th className="right">Result</th>
              <th className="right">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {data.decisions.map((d) => (
              <tr key={d.date + d.decision}>
                <td>{d.date}</td>
                <td><strong>{d.decision}</strong></td>
                <td>{d.thesis}</td>
                <td className="right">{d.size}</td>
                <td className={`right ${d.resultTone ?? ""}`}>{d.result}</td>
                <td className="right"><PdfBadge tone={d.verdict.tone}>{d.verdict.label}</PdfBadge></td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfSectionTitle variant="dry">Decisions This Period · 이번 달 의사결정 요약</PdfSectionTitle>
        <PdfThreeCol>
          {data.decisionCards.map((c) => (
            <PdfCard key={c.title}>
              <div style={{ fontSize: 9, letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
                {c.priority}
              </div>
              <h3 style={{ fontSize: 14, margin: "6px 0", fontWeight: 600 }}>{c.title}</h3>
              <p style={{ fontSize: 11, color: "var(--r-ink-3)", lineHeight: 1.5 }}>{c.body}</p>
              <div style={{ marginTop: 10 }}>
                <PdfBadge tone={c.badge.tone}>{c.badge.label}</PdfBadge>
              </div>
            </PdfCard>
          ))}
        </PdfThreeCol>

        <PdfSectionTitle variant="dry">12-Month KPI Trend · indexed to 100</PdfSectionTitle>
        <PdfCard>
          <svg viewBox="0 0 600 160" preserveAspectRatio="none" style={{ width: "100%", height: 160 }}>
            <line x1="0" y1="40" x2="600" y2="40" stroke="#ececec" strokeWidth="1" />
            <line x1="0" y1="80" x2="600" y2="80" stroke="#ececec" strokeWidth="1" />
            <line x1="0" y1="120" x2="600" y2="120" stroke="#ececec" strokeWidth="1" />
            <path d="M0,108 L50,98 L100,88 L150,100 L200,82 L250,72 L300,80 L350,62 L400,52 L450,44 L500,40 L550,32 L600,24" stroke="#0e0e0e" strokeWidth="2" fill="none" />
            <path d="M0,100 L50,96 L100,90 L150,98 L200,86 L250,80 L300,84 L350,72 L400,66 L450,60 L500,58 L550,54 L600,48" stroke="#c0c0c0" strokeWidth="1.4" fill="none" strokeDasharray="3 3" />
            <path d="M0,90 L50,88 L100,86 L150,82 L200,80 L250,78 L300,76 L350,72 L400,68 L450,66 L500,62 L550,58 L600,52" stroke="#c9963f" strokeWidth="1.6" fill="none" strokeDasharray="2 3" />
          </svg>
          <PdfFlexBetween style={{ marginTop: 8, fontSize: 10, }} className="font-mono" >
            <div style={{ display: "flex", gap: 18 }}>
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#0e0e0e" }} />Portfolio NAV</span>
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#c0c0c0" }} />S&amp;P 500</span>
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#c9963f" }} />Sharpe (12M rolling)</span>
            </div>
            <span />
          </PdfFlexBetween>
        </PdfCard>

        <PdfGovBlock />
        <PdfPageFooter left="KPI Dashboard · Premium · IC Pack" right="Page 03" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 4 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="premium" title="KPI DASHBOARD" meta="Apr 2026 · 04/04" />
        <PdfGoldRule />
        <PdfDisclaimer cadence="monthly" />
      </PdfPage>
    </>
  );
}
