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

const DEFAULT: YearEndLetterData = {
  doc: "FY 2026 · DOC PQ-YE-00214",
  author: "홍길동",
  account: "PQ-A-00214",
  year: "FY 2026",
  issued: "Dec 31, 2026",
  pullquote: "\"운으로 번 돈은 운으로 잃는다. 실력으로 번 돈만 남긴다.\" — If this year were one sentence.",
  fyReturn: { value: "+18.4%", delta: "vs S&P +11.2%" },
  alpha: { value: "+7.2%", delta: "Sharpe 1.04" },
  maxDd: { value: "−9.8%", delta: "Aug 12 – Sep 04" },
  aumGrowth: { value: "$1.24M", delta: "+$192k" },
  decisions: [
    { when: "Feb '26", decision: "NVDA · NVIDIA +5%", thesis: "DC capex 사이클 베팅", outcome: "+22.4%", outcomeTone: "pos", verdict: "RIGHT", verdictTone: "pos" },
    { when: "Apr '26", decision: "BND · Vanguard Total Bond 비중 +8%", thesis: "금리 피크아웃 대비", outcome: "+1.0%", outcomeTone: "pos", verdict: "RIGHT", verdictTone: "pos" },
    { when: "Jun '26", decision: "META · Meta Platforms 신규", thesis: "광고 회복 + AI 모멘텀", outcome: "−4.2%", outcomeTone: "neg", verdict: "EARLY", verdictTone: "neg" },
    { when: "Aug '26", decision: "PYPL · PayPal 청산", thesis: "competitive moat 약화", outcome: "+6.8% (회피)", outcomeTone: "pos", verdict: "RIGHT", verdictTone: "pos" },
    { when: "Oct '26", decision: "GLD · SPDR Gold Trust +3%", thesis: "매크로 헤지", outcome: "+7.5%", outcomeTone: "pos", verdict: "RIGHT", verdictTone: "pos" },
    { when: "Nov '26", decision: "TSLA · Tesla 보류", thesis: "밸류에이션 부담", outcome: "+18% (놓침)", outcomeTone: "neg", verdict: "WRONG", verdictTone: "warn" },
  ],
  hitRate: "68%",
  hitRateNote: "17 of 25 decisions ended up right.",
  decisionEv: "+1.42%",
  decisionEvNote: "avg alpha per decision (vs do-nothing)",
  lessons: [
    { num: "Lesson 01", title: "시간이 옳다", body: "시장이 옳은 게 아니라 시간이 옳다. 좋은 thesis도 6개월 일찍 진입하면 18%씩 깎인다." },
    { num: "Lesson 02", title: "메모 없는 매입은 도박", body: "가설 없이 들어간 자리는 빠질 때 변호할 근거도 없다. 25건 중 7건이 무메모, 그 7건의 평균 결과 −3.2%." },
    { num: "Lesson 03", title: "현금은 포지션이다", body: "현금 0%로 가득 채운 분기에 −9.8% MaxDD 발생. 다음 해는 5% 이하로 떨어지지 않는 룰." },
  ],
  costliestMistake: "TSLA (Tesla) 보류 — 가설은 옳았지만 사이즈가 제로였다. +18% 못 잡은 게 올해 가장 비싼 한 줄.",
  promises: [
    { title: "Promise 1", body: "신규 진입 전 가설 메모 100%. 메모 없으면 매입 자동 차단", tag: "Rule 01" },
    { title: "Promise 2", body: "현금 비중 5% 이하 진입 금지. dry powder 룰", tag: "Rule 02" },
    { title: "Promise 3", body: "단일 섹터 35% 한도 strict — 위반 시 다음 영업일 정상화", tag: "Rule 03" },
    { title: "Promise 4", body: "월간 의사결정 ≤ 5건. 분기 ≤ 12건. 양보다 질", tag: "Rule 04" },
    { title: "Promise 5", body: "FX 단일 노출 75% 이하 — USD 88% 상태 즉시 헤지", tag: "Rule 05" },
  ],
  returnTarget: { value: "+12%", delta: "benchmark + 4%" },
  ddLimit: { value: "−12%", delta: "hard stop" },
  decisionsCap: { value: "≤ 30", delta: "quality > quantity" },
  letterBody:
    "내년의 나에게 — 올해 +18.4%는 운과 실력이 반반. NVDA (NVIDIA)가 상상을 넘어선 게 컸다. 그런데 진짜 배운 건 TSLA (Tesla) 보류 한 줄이다. 가설이 옳아도 사이즈가 0이면 결과는 0. 내년엔 thesis만으로 부족하다, 사이즈도 같이 결정하자.",
};

export function YearEndLetter({ data = DEFAULT }: { data?: YearEndLetterData }) {
  return (
    <>
      {/* PAGE 1 — COVER */}
      <PdfPage>
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta={data.doc} />

        <div style={{ marginTop: "30mm" }}>
          <PdfCoverEyebrow>Annual Letter · To the CFO of My Portfolio</PdfCoverEyebrow>
          <PdfCoverTitle>
            FY 2026
            <br />
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
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta="FY2026 · 02/06" />
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

        <div style={{ marginTop: 12 }}>
          <PdfColTitle>12-Month NAV</PdfColTitle>
          <PdfCard>
            <svg viewBox="0 0 600 160" preserveAspectRatio="none" style={{ width: "100%", height: 160 }}>
              <defs>
                <linearGradient id="ye-fade" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0e0e0e" stopOpacity=".18" />
                  <stop offset="100%" stopColor="#0e0e0e" stopOpacity="0" />
                </linearGradient>
              </defs>
              <line x1="0" y1="40" x2="600" y2="40" stroke="#ececec" strokeWidth="1" />
              <line x1="0" y1="80" x2="600" y2="80" stroke="#ececec" strokeWidth="1" />
              <line x1="0" y1="120" x2="600" y2="120" stroke="#ececec" strokeWidth="1" />
              <path d="M0,130 L50,120 L100,124 L150,110 L200,98 L250,108 L300,84 L350,90 L400,72 L450,62 L500,50 L550,42 L600,30 L600,160 L0,160 Z" fill="url(#ye-fade)" />
              <path d="M0,130 L50,120 L100,124 L150,110 L200,98 L250,108 L300,84 L350,90 L400,72 L450,62 L500,50 L550,42 L600,30" stroke="#0e0e0e" strokeWidth="2" fill="none" />
              <path d="M0,132 L50,128 L100,124 L150,118 L200,114 L250,118 L300,108 L350,110 L400,98 L450,90 L500,82 L550,74 L600,66" stroke="#c0c0c0" strokeWidth="1.4" fill="none" strokeDasharray="3 3" />
              <text x="0" y="158" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">JAN</text>
              <text x="150" y="158" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">APR</text>
              <text x="300" y="158" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">JUL</text>
              <text x="450" y="158" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">OCT</text>
              <text x="580" y="158" fontFamily="var(--font-mono)" fontSize="8" fill="#8a8a8a">DEC</text>
            </svg>
            <div style={{ display: "flex", gap: 14, marginTop: 8, fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)", }} className="font-mono" >
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#0e0e0e" }} />Portfolio</span>
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#c0c0c0" }} />S&amp;P 500</span>
            </div>
          </PdfCard>
        </div>

        <PdfPageFooter left="Year-End Letter · Premium" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — DECISIONS REVIEW */}
      <PdfPage>
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta="FY2026 · 03/06" />

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
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta="FY2026 · 04/06" />

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
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta="FY2026 · 05/06" />

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
        <PdfHeader tier="premium" title="YEAR-END LETTER" meta="FY2026 · 06/06" />
        <PdfGoldRule />
        <PdfDisclaimer cadence="annual" withBacktest />
      </PdfPage>
    </>
  );
}
