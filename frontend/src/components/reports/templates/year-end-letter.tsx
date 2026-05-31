/**
 * Report 18 — Year-End Letter (Premium · 5 pages · Annual)
 *
 * Source: /design_handoff_pdf_reports/reports/18_year_end_letter.html
 *
 * Page 1: Cover (eyebrow + title + 4-up cover meta — Author / Account / Year / Issued).
 * Page 2: Pullquote (one-sentence year recap) + Year at a Glance 4-up KPI + 12M NAV chart.
 * Page 3: Decisions table (6 historical decisions with verdict) + 2-up Hit Rate / Decision EV cards.
 * Page 4: 3 Lessons cards + Costliest Mistake callout.
 * Page 5: To Next Year's Me checklist (5 promises) + 3-up targets + Letter notes
 *         + sign row + governance + disclaimer.
 *
 * Compliance: Annual personal letter. Decision verdicts (RIGHT/EARLY/WRONG) are
 * retrospective — not buy/sell/hold guidance. POSITIVE / NEGATIVE / NEUTRAL only.
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
  PdfPullquote,
  PdfEyebrow,
  PdfSectionTitle,
  PdfKpiRow,
  PdfColTitle,
  PdfCard,
  PdfTable,
  PdfTwoCol,
  PdfCheckList,
  PdfCallout,
  PdfNotes,
  PdfSignRow,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

interface DecisionRow {
  when: string;
  decision: string;
  thesis: string;
  outcome: string;
  outcomeTone: "pos" | "neg";
  verdict: string;
  verdictTone: "pos" | "neg" | "warn";
}

export interface YearEndLetterData {
  doc: string;
  author: string;
  account: string;
  year: string;
  issued: string;
  pullquote: string;
  fyReturn: { value: string; delta: string };
  alpha: { value: string; delta: string };
  maxDd: { value: string; delta: string };
  aumGrowth: { value: string; delta: string };
  decisions: DecisionRow[];
  hitRate: string;
  hitRateNote: string;
  decisionEv: string;
  decisionEvNote: string;
  lessons: { num: string; title: string; body: string }[];
  costliestMistake: string;
  promises: { title: string; body: string; tag: string }[];
  returnTarget: { value: string; delta: string };
  ddLimit: { value: string; delta: string };
  decisionsCap: { value: string; delta: string };
  letterBody: string;
}


export function YearEndLetter({ data }: { data?: YearEndLetterData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="year_end_letter" reason="insufficient_history" />;
  }
  return (
    <>
      {/* PAGE 1 — COVER */}
      <PdfPage>
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta={data.doc} />


        <div style={{ marginTop: "30mm" }}>
          <PdfCoverEyebrow>Annual Letter · To the CFO of My Portfolio</PdfCoverEyebrow>
          <PdfCoverTitle>
            {data.year ? <>{data.year}<br /></> : null}
            <em>Year-End Letter.</em>
          </PdfCoverTitle>
          <PdfCoverSub>
            A year of decisions, lessons, and promises — every call made, every lesson learned, and the contract sent to next year&rsquo;s self.
          </PdfCoverSub>
        </div>

        <div style={{ marginTop: "auto", paddingTop: "30mm" }}>
          <PdfCoverMetaGrid
            items={[
              { label: "Author", value: data.author },
              { label: "Account", value: data.account },
              { label: "Year", value: data.year },
              { label: "Issued", value: data.issued },
            ]}
          />
        </div>

        <PdfCoverFoot />
      </PdfPage>

      {/* PAGE 2 — PULLQUOTE + YEAR AT A GLANCE */}
      <PdfPage>
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta={`${data.doc} · 02/06`} />
        <PdfGoldRule />

        <PdfEyebrow>Opening</PdfEyebrow>
        <PdfPullquote>{data.pullquote}</PdfPullquote>

        <PdfSectionTitle>Year at a Glance · 한눈에</PdfSectionTitle>
        <PdfKpiRow
          kpis={[
            { label: "FY Return", value: data.fyReturn.value, delta: data.fyReturn.delta, deltaTone: "pos" },
            { label: "Alpha", value: data.alpha.value, delta: data.alpha.delta },
            { label: "Max Drawdown", value: data.maxDd.value, delta: data.maxDd.delta, deltaTone: "neg" },
            { label: "AUM Growth", value: data.aumGrowth.value, delta: data.aumGrowth.delta, deltaTone: "pos" },
          ]}
        />

        {/* 12-Month NAV chart omitted: no per-month NAV series is wired into
            YearEndLetterData. Fixed SVG coordinates would be a fabricated
            trend (CEO 2026-05-31). Carry-over: wire backend annual NAV series. */}

        <PdfPageFooter left="Year-End Letter · Premium" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — DECISIONS REVIEW */}
      <PdfPage>
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta={`${data.doc} · 03/06`} />

        <PdfEyebrow>01 — Decisions, Reviewed</PdfEyebrow>
        <PdfSectionTitle>Decisions · 올해 내린 결정들</PdfSectionTitle>

        <PdfTable>
          <thead>
            <tr>
              <th>When</th>
              <th>Decision</th>
              <th>Thesis</th>
              <th className="right">Outcome</th>
              <th className="right">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {data.decisions.map((d) => (
              <tr key={d.when + d.decision}>
                <td>{d.when}</td>
                <td><strong>{d.decision}</strong></td>
                <td>{d.thesis}</td>
                <td className={`right ${d.outcomeTone}`}>{d.outcome}</td>
                <td className="right" style={{ color: d.verdictTone === "pos" ? "var(--r-pos)" : d.verdictTone === "neg" ? "var(--r-neg)" : "var(--r-warn)" }}>
                  {d.verdict}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <div style={{ marginTop: 24 }}>
          <PdfTwoCol>
            <div>
              <PdfColTitle>Hit Rate</PdfColTitle>
              <PdfCard>
                <div style={{ fontSize: "var(--pq-text-hero-num)", fontWeight: 500 }} className="font-serif" >{data.hitRate}</div>
                <div style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)", marginTop: 8 }}>{data.hitRateNote}</div>
              </PdfCard>
            </div>
            <div>
              <PdfColTitle>Decision EV</PdfColTitle>
              <PdfCard>
                <div style={{ fontSize: "var(--pq-text-hero-num)", fontWeight: 500, color: "var(--r-pos)" }} className="font-serif" >{data.decisionEv}</div>
                <div style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)", marginTop: 8 }}>{data.decisionEvNote}</div>
              </PdfCard>
            </div>
          </PdfTwoCol>
        </div>

        <PdfPageFooter left="Year-End Letter · Premium" right="Page 03" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 4 — LESSONS */}
      <PdfPage>
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta={`${data.doc} · 04/06`} />

        <PdfEyebrow>02 — Lessons Learned</PdfEyebrow>
        <PdfSectionTitle>3 Lessons · 값비싼 교훈 세 가지</PdfSectionTitle>

        {data.lessons.map((l) => (
          <PdfCard key={l.num}>
            <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
              {l.num}
            </div>
            <h3 style={{ fontSize: "var(--pq-text-quote)", margin: "6px 0", fontWeight: 500 }} className="font-serif" >
              {l.title}
            </h3>
            <p style={{ color: "var(--r-ink-3)", marginTop: 8, lineHeight: 1.65 }}>{l.body}</p>
          </PdfCard>
        ))}

        <div style={{ marginTop: 18 }}>
          <PdfCallout label="The Costliest Mistake">{data.costliestMistake}</PdfCallout>
        </div>

        <PdfPageFooter left="Year-End Letter · Premium" right="Page 04" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 5 — NEXT YEAR + SIGN */}
      <PdfPage>
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta={`${data.doc} · 05/06`} />

        <PdfEyebrow>03 — Promises for Next Year</PdfEyebrow>
        <PdfSectionTitle>To Next Year&apos;s Me · 내년의 나에게</PdfSectionTitle>

        <PdfCheckList
          items={data.promises.map((p) => ({
            checked: false,
            body: <><strong>{p.title}</strong> — {p.body}</>,
            meta: p.tag,
          }))}
        />

        <PdfSectionTitle variant="sm">Targets for Next FY · 내년의 숫자 약속</PdfSectionTitle>
        <PdfKpiRow
          cols={3}
          kpis={[
            { label: "Return Target", value: data.returnTarget.value, delta: data.returnTarget.delta },
            { label: "Max Drawdown Limit", value: data.ddLimit.value, delta: data.ddLimit.delta },
            { label: "Decisions Cap", value: data.decisionsCap.value, delta: data.decisionsCap.delta },
          ]}
        />

        <PdfSectionTitle variant="sm">The Letter · 내가 내게 보내는 편지</PdfSectionTitle>
        <PdfNotes tall>{data.letterBody}</PdfNotes>

        <PdfSignRow left="Signed · Investor" right="Date" />

        <PdfGovBlock />
        <PdfPageFooter left="Year-End Letter · Premium · Personal" right="Page 05" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 6 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta={`${data.doc} · 06/06`} />
        <PdfGoldRule />
        <PdfDisclaimer cadence="annual" withBacktest />
      </PdfPage>
    </>
  );
}
