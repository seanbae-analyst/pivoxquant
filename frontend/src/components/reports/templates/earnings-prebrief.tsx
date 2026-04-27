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
  PdfTicker,
} from "../pdf-primitives";
import { DEFAULT_GOVERNANCE } from "@/lib/reports/disclaimer";

export type SignalLabel = "POSITIVE" | "NEGATIVE" | "NEUTRAL";

export interface EarningsPrebriefData {
  ticker: string;
  companyName: string;
  fiscalLabel: string;     // "Q1 2026 · FY 2026"
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

const DEFAULT: EarningsPrebriefData = {
  ticker: "PLTR",
  companyName: "Palantir Technologies",
  fiscalLabel: "Q1 2026 · FY 2026 Earnings",
  reportingDate: "Earnings Date · After Market Close",
  position: "120 sh · 9.95% weight",
  consensus: [
    { metric: "Revenue", consensus: "$32.5B", whisper: "$33.8B", lastQ: "+18%", lastQTone: "pos", surprise: "+4.2% (8/8)", surpriseTone: "pos" },
    { metric: "EPS (GAAP)", consensus: "$5.12", whisper: "$5.40", lastQ: "+24%", lastQTone: "pos", surprise: "+6.1% (8/8)", surpriseTone: "pos" },
    { metric: "Gross Margin", consensus: "74.8%", whisper: "75.5%", lastQ: "+220bps", lastQTone: "pos", surprise: "Beat 7/8", surpriseTone: "pos" },
    { metric: "Data Center Rev", consensus: "$26.1B", whisper: "$27.4B", lastQ: "+38%", lastQTone: "pos", surprise: "Beat 8/8", surpriseTone: "pos" },
    { metric: "FCF", consensus: "$14.2B", whisper: "$15.0B", lastQ: "+42%", lastQTone: "pos", surprise: "—" },
  ],
  impliedMovePct: "±7.8%",
  impliedMoveDetail: "8주 IV: 52% · 평균 EPS Day 변동: 6.4%",
  quantScore: 0.82,
  quantLabel: "POSITIVE",
  factorBreakdown: "Momentum 0.91 · Quality 0.88 · Value 0.42 · Sentiment 0.79",
  scenarios: [
    {
      case: "Bull Case",
      caseDetail: "EPS & DC beat >5%",
      trigger: "EPS > $5.40 AND DC > $27.4B",
      action: "Hold · trim 0.5% on +10% spike",
      posDelta: "−0.5%",
      posDeltaTone: "pos",
      stop: "$1,180",
    },
    {
      case: "Base Case",
      caseDetail: "In-line",
      trigger: "EPS $5.10–5.40, guide ≥ cons",
      action: "Hold · re-evaluate after CC",
      posDelta: "0.0%",
      stop: "$1,080",
    },
    {
      case: "Bear Case",
      caseDetail: "Miss or weak guide",
      trigger: "EPS < $5.10 OR guide < cons",
      action: "Trim 1.5% · review hypothesis",
      posDelta: "−1.5%",
      posDeltaTone: "neg",
      stop: "$960",
    },
  ],
  watchChecklist: [
    "DC growth rate (sustain >35% YoY)",
    "Gross margin trajectory (compression risk)",
    "FY guide vs street consensus",
    "AI infrastructure capex commentary",
    "Customer concentration update",
  ],
};

const SIGNAL_TONE: Record<SignalLabel, string> = {
  POSITIVE: "var(--r-pos)",
  NEGATIVE: "var(--r-neg)",
  NEUTRAL: "var(--r-ink-3)",
};

export function EarningsPrebrief({ data = DEFAULT }: { data?: EarningsPrebriefData }) {
  return (
    <>
      {/* ───── PAGE 1 — BRIEF ───── */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="EARNINGS PRE-BRIEF"
          meta={`${data.ticker} · 01 / 02`}
        />
        <PdfGoldRule />

        <PdfEyebrow>Pre-Earnings Brief · For Growth / Quant Personas</PdfEyebrow>
        <PdfCoverTitle size={48}>
          {data.companyName}
          <em
            style={{
              fontSize: 32,
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
                fontFamily: "var(--font-serif)",
                fontSize: 22,
              }}
            >
              {data.reportingDate}
            </div>
          </div>
          <div style={{ height: 40, width: 1, background: "var(--r-rule)" }} />
          <div>
            <div className="pq-pdf-kpi-lbl">Position</div>
            <div
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 22,
              }}
            >
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
                    fontFamily: "var(--font-serif)",
                    fontSize: 36,
                  }}
                >
                  {data.impliedMovePct}
                </div>
                <div
                  style={{
                    fontSize: 10,
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
                    fontFamily: "var(--font-serif)",
                    fontSize: 36,
                    color: SIGNAL_TONE[data.quantLabel],
                  }}
                  data-pq-signal-label={data.quantLabel}
                >
                  {data.quantLabel} · {data.quantScore.toFixed(2)}
                </div>
                <div
                  style={{
                    fontSize: 10,
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
        <PdfDisclaimer cadence="event" />
      </PdfPage>

      {/* ───── PAGE 2 — PLAYBOOK ───── */}
      <PdfPage>
        <PdfHeader
          tier="pro"
          title="EARNINGS PRE-BRIEF"
          meta={`${data.ticker} · 02 / 02`}
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
                    style={{ fontSize: 10, color: "var(--r-ink-3)" }}
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
