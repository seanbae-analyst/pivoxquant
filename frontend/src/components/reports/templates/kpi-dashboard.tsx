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
  PdfBadge,
  PdfSectionTitle,
  PdfTable,
  PdfHeat,
  PdfThreeCol,
  PdfCard,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

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
  /** Period label for the cover headline (e.g. a month name). Optional —
   *  when absent the cover omits the period rather than showing a
   *  hardcoded month. */
  coverMonth?: string;
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


export function KpiDashboard({ data }: { data?: KpiDashboardData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="kpi_dashboard" reason="no_positions" />;
  }
  return (
    <>
      {/* PAGE 1 — COVER (light, matches other Premium covers per CEO 2026-04-27) */}
      <PdfPage>
        <PdfHeader tier="premium" title="KPI DASHBOARD · IC PACK" meta={data.doc} />


        <div style={{ marginTop: "30mm" }}>
          <PdfCoverEyebrow>Investment Committee Pack · Monthly</PdfCoverEyebrow>
          <PdfCoverTitle size={64}>
            {data.coverMonth ? <>{data.coverMonth} </> : null}
            <em>KPI Dashboard.</em>
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
        <PdfHeader tier="premium" title="KPI DASHBOARD" meta={`${data.doc} · 02/04`} />

        {/* Executive Summary narrative is not yet computed by the backend
            (no `exec_rows` wired into KpiDashboardData). Per CEO 2026-05-31
            "있는 데이터로만" — omit rather than render a fabricated narrative.
            Carry-over: wire backend exec_rows → KpiDashboardData. */}

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
        <PdfHeader tier="premium" title="KPI DASHBOARD" meta={`${data.doc} · 03/04`} />
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
              <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
                {c.priority}
              </div>
              <h3 style={{ fontSize: "var(--pq-text-body)", margin: "6px 0", fontWeight: 600 }}>{c.title}</h3>
              <p style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)", lineHeight: 1.5 }}>{c.body}</p>
              <div style={{ marginTop: 10 }}>
                <PdfBadge tone={c.badge.tone}>{c.badge.label}</PdfBadge>
              </div>
            </PdfCard>
          ))}
        </PdfThreeCol>

        {/* 12-Month KPI Trend chart omitted: no per-month series data is
            wired into KpiDashboardData. Fixed SVG path coordinates would be a
            fabricated trend. Carry-over: wire backend monthly NAV/benchmark/
            Sharpe series → render a real chart. */}

        <PdfGovBlock />
        <PdfPageFooter left="KPI Dashboard · Premium · IC Pack" right="Page 03" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 4 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="premium" title="KPI DASHBOARD" meta={`${data.doc} · 04/04`} />
        <PdfGoldRule />
        <PdfDisclaimer cadence="monthly" />
      </PdfPage>
    </>
  );
}
