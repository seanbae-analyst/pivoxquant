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
import { EmptyState } from "../empty-state";

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


export function CapitalAllocation({ data }: { data?: CapitalAllocationData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="capital_allocation" reason="no_positions" />;
  }
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
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta={`${data.doc} · 02/05`} />
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
              <div style={{ textAlign: "right", fontSize: "var(--pq-text-eyebrow)", color: "var(--r-pos)" }} className="font-mono" >
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
              <div style={{ textAlign: "right", fontSize: "var(--pq-text-eyebrow)" }} className="font-mono" >
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
              { label: "Cash Build", value: data.cashBuild, delta: "kept dry" },
              { label: "Avg Deploy Lag", value: data.avgLag, delta: "target ≤ 7d", deltaTone: "warn" },
            ]}
          />
        </div>

        <PdfPageFooter left="Capital Allocation · Premium" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — DEPLOYMENT QUALITY */}
      <PdfPage>
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta={`${data.doc} · 03/05`} />
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
                <h3 style={{ fontSize: "var(--pq-text-quote)", fontWeight: 500 }} className="font-serif" >{data.bestDollar.name}</h3>
                <p style={{ color: "var(--r-ink-3)", marginTop: 8, fontSize: "var(--pq-text-eyebrow)", lineHeight: 1.6 }}>
                  {data.bestDollar.body}
                </p>
              </PdfCard>
            </div>
            <div>
              <PdfColTitle>Worst Dollar · 가장 못 일한 돈</PdfColTitle>
              <PdfCard>
                <h3 style={{ fontSize: "var(--pq-text-quote)", fontWeight: 500 }} className="font-serif" >{data.worstDollar.name}</h3>
                <p style={{ color: "var(--r-ink-3)", marginTop: 8, fontSize: "var(--pq-text-eyebrow)", lineHeight: 1.6 }}>
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
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta={`${data.doc} · 04/05`} />
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
        <PdfHeader tier="premium" title="CAPITAL ALLOCATION" meta={`${data.doc} · 05/05`} />
        <PdfGoldRule />
        <PdfDisclaimer cadence="quarterly" withBacktest />
      </PdfPage>
    </>
  );
}
