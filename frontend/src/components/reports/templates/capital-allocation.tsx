/**
 * Report 13 — Capital Allocation (Premium · 4 pages · Quarterly)
 *
 * Source: /design_handoff_pdf_reports/reports/13_capital_allocation.html
 *
 * Page 1: Cover with eyebrow + cover title (where should the next dollar go?)
 *         + 4-up cover meta grid (Period / Total Capital / Q2 Inflows / Net Deployed) + cover foot.
 * Page 2: Sources & Uses two-column alloc + 3-up KPI (Deploy Ratio / Cash Build / Avg Lag).
 * Page 3: Deployment Quality table + Best/Worst Dollar two-card layout.
 * Page 4: Pullquote + Q3 Allocation Plan checklist (5 items) + CFO's Memo notes
 *         + Sign Row + governance + disclaimer.
 *
 * Compliance: Backtest disclaimer required (withBacktest: true — uses IRR projections).
 * No buy/sell/hold language. "Best Dollar" / "Worst Dollar" are factual P&L attribution.
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
  PdfEyebrow,
  PdfSectionTitle,
  PdfTwoCol,
  PdfColTitle,
  PdfAllocList,
  PdfKpiRow,
  PdfTable,
  PdfCard,
  PdfPullquote,
  PdfCheckList,
  PdfNotes,
  PdfSignRow,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";

export interface CapitalAllocationData {
  doc: string;
  period: string;
  totalCapital: string;
  inflows: string;
  netDeployed: string;
  sources: { label: string; pct: number; amount: string; flat?: boolean }[];
  totalSources: string;
  uses: { label: string; pct: number; amount: string; flat?: boolean }[];
  totalUses: string;
  deployRatio: string;
  cashBuild: string;
  avgLag: string;
  decisions: { name: string; when: string; deployed: string; current: string; ret: string; retTone: "pos" | "neg" | "neutral"; irr: string; irrTone: "pos" | "neg" | "warn" }[];
  totals: { deployed: string; current: string; ret: string; irr: string };
  bestDollar: { name: string; body: string };
  worstDollar: { name: string; body: string };
  pullquote: string;
  plans: { title: string; body: string; priority: string }[];
  cfoMemo: string;
}

const DEFAULT: CapitalAllocationData = {
  doc: "FY2026 Q2 · DOC PQ-CA-00214",
  period: "2026 Q2",
  totalCapital: "$1,242,150",
  inflows: "+$48,200",
  netDeployed: "$32,800",
  sources: [
    { label: "월급 저축", pct: 62, amount: "$24,000" },
    { label: "배당 수입", pct: 38, amount: "$5,520" },
    { label: "매각 차익 (PYPL)", pct: 74, amount: "$18,680", flat: true },
    { label: "기타 (보너스)", pct: 14, amount: "$0", flat: true },
  ],
  totalSources: "$48,200",
  uses: [
    { label: "신규 매입 (NVDA, META)", pct: 78, amount: "$22,400" },
    { label: "기존 종목 추가", pct: 42, amount: "$10,400" },
    { label: "현금 적립", pct: 58, amount: "$15,400", flat: true },
    { label: "세금 / 수수료", pct: 0, amount: "$0", flat: true },
  ],
  totalUses: "$48,200",
  deployRatio: "68%",
  cashBuild: "$15.4k",
  avgLag: "11 days",
  decisions: [
    { name: "NVDA +5%", when: "Apr 12", deployed: "$12,400", current: "$15,180", ret: "+22.4%", retTone: "pos", irr: "+118%", irrTone: "pos" },
    { name: "META 신규", when: "May 02", deployed: "$10,000", current: "$9,580", ret: "−4.2%", retTone: "neg", irr: "−18%", irrTone: "neg" },
    { name: "SCHD 적립", when: "매월", deployed: "$6,000", current: "$6,260", ret: "+4.3%", retTone: "pos", irr: "+22%", irrTone: "pos" },
    { name: "BND 비중 +8%", when: "Apr 28", deployed: "$4,400", current: "$4,444", ret: "+1.0%", retTone: "pos", irr: "+5.5%", irrTone: "pos" },
    { name: "현금 적립", when: "—", deployed: "$15,400", current: "$15,478", ret: "+0.5%", retTone: "neutral", irr: "+5.0% (MM)", irrTone: "warn" },
  ],
  totals: { deployed: "$48,200", current: "$50,942", ret: "+5.7%", irr: "+24%" },
  bestDollar: { name: "NVDA · +22.4%", body: "$12,400 → $15,180. 분기 deployed 자본의 26%가 알파의 64%를 만들었다. Concentration의 양면." },
  worstDollar: { name: "META · −4.2%", body: "타이밍 문제. Thesis는 유효, 6개월 더 기다릴 가치 있음. 추가 매입 보류." },
  pullquote:
    "Capital allocation is the CEO's most important job. 그리고 당신이 그 CEO다.",
  plans: [
    { title: "Plan 1", body: "월급 저축 30% 자동 매입 (SCHD + VOO)", priority: "P1" },
    { title: "Plan 2", body: "현금 $15k 중 $10k는 Q3 내 deploy, $5k는 dry powder 유지", priority: "P1" },
    { title: "Plan 3", body: "Tech 비중 단계적 −5%p (Q3 말까지)", priority: "P2" },
    { title: "Plan 4", body: "신규 매입 후보: HD, ASML, COST 중 1개", priority: "P2" },
    { title: "Plan 5", body: "Deploy lag 7일 이내로 단축 (자동화 룰)", priority: "P3" },
  ],
  cfoMemo: "이번 분기 자본 배분에 대한 자유 서술…",
};

export function CapitalAllocation({ data = DEFAULT }: { data?: CapitalAllocationData }) {
  return (
    <>
      {/* PAGE 1 — COVER */}
      <PdfPage>
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta={data.doc} />

        <div style={{ marginTop: "30mm" }}>
          <PdfCoverEyebrow>Quarterly Review · The CFO&apos;s Question</PdfCoverEyebrow>
          <PdfCoverTitle>
            Where should the<br />
            <em>next dollar</em> go?
          </PdfCoverTitle>
          <PdfCoverSub>
            Where capital went this quarter, and where it should go next. Capital is the ultimate scoreboard.
          </PdfCoverSub>
        </div>

        <div style={{ marginTop: "auto", paddingTop: "30mm" }}>
          <PdfCoverMetaGrid
            items={[
              { label: "Period", value: data.period },
              { label: "Total Capital", value: data.totalCapital },
              { label: "Q2 Inflows", value: data.inflows },
              { label: "Net Deployed", value: data.netDeployed },
            ]}
          />
        </div>

        <PdfCoverFoot />
      </PdfPage>

      {/* PAGE 2 — SOURCES & USES */}
      <PdfPage>
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta="FY26 Q2 · 02/05" />
        <PdfGoldRule />

        <PdfEyebrow>01 — Sources &amp; Uses</PdfEyebrow>
        <PdfSectionTitle>Where the money came from. Where it went.</PdfSectionTitle>

        <PdfTwoCol>
          <div>
            <PdfColTitle>Sources · 들어온 돈</PdfColTitle>
            <PdfAllocList
              items={data.sources.map((s) => ({
                name: s.label,
                pct: s.pct,
                pctDisplay: s.amount,
              }))}
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "30mm 1fr 18mm",
                alignItems: "center",
                gap: 12,
                paddingTop: 12,
                borderTop: "1.5px solid #111",
                marginTop: 12,
              }}
            >
              <strong>Total Sources</strong>
              <div />
              <div style={{ textAlign: "right", fontSize: 11, color: "var(--r-pos)" }} className="font-mono" >
                <strong>{data.totalSources}</strong>
              </div>
            </div>
          </div>
          <div>
            <PdfColTitle>Uses · 나간 돈</PdfColTitle>
            <PdfAllocList
              items={data.uses.map((u) => ({
                name: u.label,
                pct: u.pct,
                pctDisplay: u.amount,
              }))}
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "30mm 1fr 18mm",
                alignItems: "center",
                gap: 12,
                paddingTop: 12,
                borderTop: "1.5px solid #111",
                marginTop: 12,
              }}
            >
              <strong>Total Uses</strong>
              <div />
              <div style={{ textAlign: "right", fontSize: 11 }} className="font-mono" >
                <strong>{data.totalUses}</strong>
              </div>
            </div>
          </div>
        </PdfTwoCol>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            cols={3}
            kpis={[
              { label: "Deploy Ratio", value: data.deployRatio, delta: "deployed / sources" },
              { label: "Cash Build", value: data.cashBuild, delta: "32% kept dry" },
              { label: "Avg Deploy Lag", value: data.avgLag, delta: "target ≤ 7d", deltaTone: "warn" },
            ]}
          />
        </div>

        <PdfPageFooter left="Capital Allocation · Premium" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — DEPLOYMENT QUALITY */}
      <PdfPage>
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta="FY26 Q2 · 03/05" />
        <PdfGoldRule />

        <PdfEyebrow>02 — Deployment Quality</PdfEyebrow>
        <PdfSectionTitle>매 달러는 얼마나 잘 일했는가.</PdfSectionTitle>

        <PdfTable>
          <thead>
            <tr>
              <th>Decision</th>
              <th>When</th>
              <th className="right">Deployed</th>
              <th className="right">Current</th>
              <th className="right">Return</th>
              <th className="right">IRR</th>
            </tr>
          </thead>
          <tbody>
            {data.decisions.map((d) => (
              <tr key={d.name}>
                <td><strong>{d.name}</strong></td>
                <td>{d.when}</td>
                <td className="right">{d.deployed}</td>
                <td className="right">{d.current}</td>
                <td className={`right ${d.retTone === "neutral" ? "" : d.retTone}`}>{d.ret}</td>
                <td className="right" style={{ color: d.irrTone === "warn" ? "var(--r-warn)" : d.irrTone === "pos" ? "var(--r-pos)" : "var(--r-neg)" }}>
                  {d.irr}
                </td>
              </tr>
            ))}
            <tr className="total">
              <td colSpan={2}>Net Deployed</td>
              <td className="right">{data.totals.deployed}</td>
              <td className="right">{data.totals.current}</td>
              <td className="right pos"><strong>{data.totals.ret}</strong></td>
              <td className="right pos"><strong>{data.totals.irr}</strong></td>
            </tr>
          </tbody>
        </PdfTable>

        <div style={{ marginTop: 24 }}>
          <PdfTwoCol>
            <div>
              <PdfColTitle>Best Dollar · 가장 잘 일한 돈</PdfColTitle>
              <PdfCard>
                <h3 style={{ fontSize: 24, fontWeight: 500 }} className="font-serif" >{data.bestDollar.name}</h3>
                <p style={{ color: "var(--r-ink-3)", marginTop: 8, fontSize: 12, lineHeight: 1.6 }}>
                  {data.bestDollar.body}
                </p>
              </PdfCard>
            </div>
            <div>
              <PdfColTitle>Worst Dollar · 가장 못 일한 돈</PdfColTitle>
              <PdfCard>
                <h3 style={{ fontSize: 24, fontWeight: 500 }} className="font-serif" >{data.worstDollar.name}</h3>
                <p style={{ color: "var(--r-ink-3)", marginTop: 8, fontSize: 12, lineHeight: 1.6 }}>
                  {data.worstDollar.body}
                </p>
              </PdfCard>
            </div>
          </PdfTwoCol>
        </div>

        <PdfPageFooter left="Capital Allocation · Premium" right="Page 03" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 4 — NEXT QUARTER PLAN
          2026-05-06 Strategy B Option 2: explicit disclaim-only PdfPage so
          chromium print engine never pushes the disclaimer onto a ghost sheet. */}
      <PdfPage>
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta="FY26 Q2 · 04/05" />
        <PdfGoldRule />

        <PdfPullquote>{data.pullquote}</PdfPullquote>

        <PdfEyebrow>03 — Next Quarter Plan</PdfEyebrow>
        <PdfSectionTitle>Q3 Allocation Plan · 다음 분기 계획</PdfSectionTitle>

        <PdfCheckList
          items={data.plans.map((p) => ({
            checked: false,
            body: <><strong>{p.title}</strong> — {p.body}</>,
            meta: p.priority,
          }))}
        />

        <PdfSectionTitle variant="sm">CFO&apos;s Memo</PdfSectionTitle>
        <PdfNotes tall>{data.cfoMemo}</PdfNotes>

        <PdfSignRow left="Approved · CFO of My Portfolio" right="Date" />

        <PdfGovBlock />
        <PdfPageFooter left="Capital Allocation · Premium · Personal" right="Page 04" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 5 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta="FY26 Q2 · 05/05" />
        <PdfGoldRule />
        <PdfDisclaimer cadence="quarterly" withBacktest />
      </PdfPage>
    </>
  );
}
