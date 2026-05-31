/**
 * Report 04 — Earnings Pre-Brief (Pro · 2 pages · Per-event)
 *
 * Source: /design_handoff_pdf_reports/reports/04_earnings_prebrief.html
 *
 * COMPLIANCE FIX (CEO 2026-04-27):
 *   The original HTML mock contains "BUY · 0.82" on the Quant Score card.
 *   That label is forbidden under the Korean Capital Markets Act when used
 *   without an investment-adviser license. This React port reclassifies it
 *   to **POSITIVE / NEGATIVE / NEUTRAL** as required by CLAUDE.md and the
 *   Template Hardcoding Guard (tests/test_no_hardcoded_samples.py).
 *
 *   Original:  BUY  · 0.82
 *   Replaced:  POSITIVE · 0.82
 *
 * Page 1: Cover + Consensus vs Whisper table + Implied Move + Quant Signal
 * Page 2: Scenario playbook + watch checklist + governance block
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfEyebrow,
  PdfCoverTitle,
  PdfTwoCol,
  PdfColTitle,
  PdfCard,
  PdfTable,
  PdfCheckList,
  PdfGoldRule,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
  PdfTicker,
} from "../pdf-primitives";
import { displayTicker, normalizeTicker } from "@/lib/format";
import { DEFAULT_GOVERNANCE } from "@/lib/reports/disclaimer";
import { EmptyState } from "../empty-state";

export type SignalLabel = "POSITIVE" | "NEGATIVE" | "NEUTRAL";

export interface EarningsPrebriefData {
  ticker: string;
  companyName: string;
  fiscalLabel: string;     // "Q1 2026 · FY 2026"
  /** Report id shown in the page header (an EP-prefixed tag). Optional —
   *  omitted rather than hardcoded when the backend does not supply it. */
  reportTag?: string;
  reportingDate: string;   // "Earnings Date · After Market Close"
  position: string;        // "120 sh · 9.95% weight"
  consensus: ConsensusRow[];
  impliedMovePct: string;  // "±7.8%"
  impliedMoveDetail: string;
  quantScore: number;      // 0..1
  /** Compliance: must be POSITIVE / NEGATIVE / NEUTRAL — never BUY/SELL/HOLD */
  quantLabel: SignalLabel;
  factorBreakdown: string; // "Momentum 0.91 · Quality 0.88 · Value 0.42 · Sentiment 0.79"
  scenarios: ScenarioRow[];
  watchChecklist: string[];
}

interface ConsensusRow {
  metric: string;
  consensus: string;
  whisper: string;
  lastQ: string;
  lastQTone?: "pos" | "neg";
  surprise: string;
  surpriseTone?: "pos" | "neg";
}
interface ScenarioRow {
  case: "Bull Case" | "Base Case" | "Bear Case";
  caseDetail: string;
  trigger: string;
  action: string;
  posDelta: string;
  posDeltaTone?: "pos" | "neg";
  stop: string;
}


const SIGNAL_TONE: Record<SignalLabel, string> = {
  POSITIVE: "var(--r-pos)",
  NEGATIVE: "var(--r-neg)",
  NEUTRAL: "var(--r-ink-3)",
};

export function EarningsPrebrief({ data }: { data?: EarningsPrebriefData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="earnings_prebrief" reason="not_in_portfolio" />;
  }
  return (
    <>
      {/* ───── PAGE 1 — BRIEF ───── */}
      <PdfPage>
        {/* PR #212 follow-up — company name first in the header caption,
            ticker code retained as the secondary identifier. */}
        <PdfHeader
          tier="pro"
          title="EARNINGS PRE-BRIEF"
          meta={`${displayTicker(data.ticker, data.companyName)} · ${normalizeTicker(data.ticker)}${data.reportTag ? ` · ${data.reportTag}` : ""} · 01/02`}
        />
        <PdfGoldRule />

        <PdfEyebrow>Pre-Earnings Brief · For Growth / Quant Personas</PdfEyebrow>
        <PdfCoverTitle size={48}>
          {data.companyName}
          <em
            style={{
              fontSize: "var(--pq-text-h3)",
              display: "block",
              marginTop: 6,
            }}
          >
            {data.fiscalLabel}
          </em>
        </PdfCoverTitle>

        <div
          style={{
            display: "flex",
            gap: 24,
            alignItems: "center",
            marginTop: 18,
          }}
        >
          <div>
            <div className="pq-pdf-kpi-lbl">Reporting</div>
            <div
              style={{
                fontSize: "var(--pq-text-quote)",
              }}
            className="font-serif" >
              {data.reportingDate}
            </div>
          </div>
          <div style={{ height: 40, width: 1, background: "var(--r-rule)" }} />
          <div>
            <div className="pq-pdf-kpi-lbl">Position</div>
            <div
              style={{
                fontSize: "var(--pq-text-quote)",
              }}
            className="font-serif" >
              {data.position}
            </div>
          </div>
        </div>

        <h2
          className="pq-pdf-section-title sm"
          style={{ marginTop: 24 }}
        >
          Consensus vs Whisper · 시장이 기대하는 수치
        </h2>
        <PdfTable>
          <thead>
            <tr>
              <th>Metric</th>
              <th className="right">Consensus</th>
              <th className="right">Whisper</th>
              <th className="right">Last Q (YoY)</th>
              <th className="right">Surprise History</th>
            </tr>
          </thead>
          <tbody>
            {data.consensus.map((row, i) => (
              <tr key={i}>
                <td>{row.metric}</td>
                <td className="right">{row.consensus}</td>
                <td className="right">{row.whisper}</td>
                <td className={`right${row.lastQTone ? ` ${row.lastQTone}` : ""}`}>
                  {row.lastQ}
                </td>
                <td className={`right${row.surpriseTone ? ` ${row.surpriseTone}` : ""}`}>
                  {row.surprise}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <div style={{ marginTop: 24 }}>
          <PdfTwoCol>
            <div>
              <PdfColTitle>Implied Move (Options)</PdfColTitle>
              <PdfCard>
                <div className="pq-pdf-kpi-lbl">Straddle Implied</div>
                <div
                  style={{
                    fontSize: "var(--pq-text-pdf-hero)",
                  }}
                className="font-serif" >
                  {data.impliedMovePct}
                </div>
                <div
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "var(--r-ink-3)",
                    marginTop: 8,
                  }}
                >
                  {data.impliedMoveDetail}
                </div>
              </PdfCard>
            </div>
            <div>
              <PdfColTitle>Quant Signal</PdfColTitle>
              <PdfCard>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                  }}
                >
                  <div className="pq-pdf-kpi-lbl">PivoxQuant Score</div>
                  <PdfTicker>{data.ticker}</PdfTicker>
                </div>
                {/* COMPLIANCE: POSITIVE / NEGATIVE / NEUTRAL — NOT BUY/SELL/HOLD.
                    Original mock said "BUY · 0.82"; reclassified for legal safety. */}
                <div
                  style={{
                    fontSize: "var(--pq-text-pdf-hero)",
                    color: SIGNAL_TONE[data.quantLabel],
                  }}
                  data-pq-signal-label={data.quantLabel}
                className="font-serif" >
                  {data.quantLabel} · {data.quantScore.toFixed(2)}
                </div>
                <div
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "var(--r-ink-3)",
                    marginTop: 8,
                  }}
                >
                  {data.factorBreakdown}
                </div>
              </PdfCard>
            </div>
          </PdfTwoCol>
        </div>

        <PdfPageFooter
          left="PivoxQuant · Confidential · Pro Tier"
          right={`Earnings Pre-Brief · 01 / 02`}
        />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* ───── PAGE 2 — PLAYBOOK ───── */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="EARNINGS PRE-BRIEF"
          meta={`${displayTicker(data.ticker, data.companyName)} · ${normalizeTicker(data.ticker)}${data.reportTag ? ` · ${data.reportTag}` : ""} · 02/02`}
        />

        <PdfEyebrow>02 — Scenario Playbook</PdfEyebrow>
        <h2 className="pq-pdf-section-title">If → Then. 시나리오별 대응.</h2>

        <PdfTable>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Trigger</th>
              <th>Action</th>
              <th className="right">Position Δ</th>
              <th className="right">Stop</th>
            </tr>
          </thead>
          <tbody>
            {data.scenarios.map((s, i) => (
              <tr key={i}>
                <td>
                  <strong>{s.case}</strong>
                  <div
                    style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)" }}
                  >
                    {s.caseDetail}
                  </div>
                </td>
                <td>{s.trigger}</td>
                <td>{s.action}</td>
                <td className={`right${s.posDeltaTone ? ` ${s.posDeltaTone}` : ""}`}>
                  {s.posDelta}
                </td>
                <td className="right">{s.stop}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <div style={{ marginTop: 24 }}>
          <PdfColTitle>Watch · 발표 후 확인할 것</PdfColTitle>
          <PdfCheckList
            items={data.watchChecklist.map((body) => ({
              checked: false,
              body,
              meta: "OBSERVE",
            }))}
          />
        </div>

        <PdfGovBlock meta={DEFAULT_GOVERNANCE} />

        <PdfPageFooter
          left="PivoxQuant · Confidential · Pro Tier"
          right={`Earnings Pre-Brief · 02 / 02`}
        />
        <PdfDisclaimer cadence="event" />
      </PdfPage>
    </>
  );
}
