/**
 * Report 12 — Portfolio Segment (Pro · 2 pages · Monthly)
 *
 * Source: /design_handoff_pdf_reports/reports/12_portfolio_segment.html
 *
 * Page 1: 4-up KPI (NAV / Holdings / Avg Position / Active Share) + Sector alloc
 *         + Geography alloc + FX exposure card.
 * Page 2: Factor exposure table + Top 5 + Bottom 3 holdings table + CFO's Note callout
 *         + governance + disclaimer.
 *
 * Compliance: Decomposition only. No buy/sell/hold language. Tech limit breach
 * shown as factual ("42% / 35% lim") not as recommendation to sell.
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
  PdfAllocList,
  PdfTwoCol,
  PdfColTitle,
  PdfCard,
  PdfFlexBetween,
  PdfDivider,
  PdfTable,
  PdfTicker,
  PdfCallout,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

interface FactorRow {
  factor: string;
  exposure: string;
  vsBenchmark: string;
  vsBenchTone: "pos" | "neg" | "neutral";
  mtdContrib: string;
  mtdTone: "pos" | "neg" | "neutral";
  ytdContrib: string;
  ytdTone: "pos" | "neg" | "neutral";
}
interface HoldingRow {
  ticker: string;
  name: string;
  weight: string;
  mtd: string;
  mtdTone: "pos" | "neg";
  ytd: string;
  ytdTone: "pos" | "neg";
  contrib: string;
  contribTone: "pos" | "neg";
  bottom?: boolean;
}

export interface PortfolioSegmentData {
  asOf: string;
  nav: { value: string; delta: string };
  holdings: { value: string; delta: string };
  avgPos: { value: string; delta: string };
  activeShare: { value: string; delta: string };
  sectors: { name: string; pct: number; pctDisplay?: string; tone?: "neg"; flat?: boolean }[];
  geography: { name: string; pct: number; pctDisplay?: string; flat?: boolean }[];
  fx: { ccy: string; pct: string }[];
  fxNote: string;
  factors: FactorRow[];
  topBottom: HoldingRow[];
  cfoNote: string;
}


export function PortfolioSegment({ data }: { data?: PortfolioSegmentData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="portfolio_segment" reason="no_positions" />;
  }
  return (
    <>
      {/* PAGE 1 */}
      <PdfPage>
        <PdfHeader tier="pro" title="PORTFOLIO SEGMENT" meta={`${data.asOf} · 01/03`} />
        <PdfGoldRule />


        <PdfEyebrow>Portfolio Segment · Monthly</PdfEyebrow>
        <PdfCoverTitle size={32}>
          <em>Decomposed</em>—sector, factor, region.
        </PdfCoverTitle>

        <div style={{ marginTop: 12 }}>
          <PdfKpiRow
            kpis={[
              { label: "NAV", value: data.nav.value, delta: data.nav.delta, deltaTone: "pos" },
              { label: "Holdings", value: data.holdings.value, delta: data.holdings.delta },
              { label: "Avg Position", value: data.avgPos.value, delta: data.avgPos.delta },
              { label: "Active Share", value: data.activeShare.value, delta: data.activeShare.delta },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Sector · 섹터 분해</PdfSectionTitle>
        <PdfAllocList
          items={data.sectors.map((s) => ({
            name: <strong>{s.name}</strong>,
            pct: s.pct,
            pctDisplay: (
              <span style={{ color: s.tone === "neg" ? "var(--r-neg)" : undefined }}>
                {s.pctDisplay ?? `${s.pct}%`}
              </span>
            ),
          }))}
        />

        <PdfSectionTitle variant="sm">Geography · 지역</PdfSectionTitle>
        <PdfTwoCol>
          <div>
            <PdfAllocList
              items={data.geography.map((g) => ({
                name: <strong>{g.name}</strong>,
                pct: g.pct,
                pctDisplay: g.pctDisplay,
              }))}
            />
          </div>
          <div>
            <PdfColTitle>FX Exposure</PdfColTitle>
            <PdfCard>
              {data.fx.map((f, i) => (
                <PdfFlexBetween key={f.ccy} style={i < data.fx.length - 1 ? { marginBottom: 12 } : undefined}>
                  <div style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)" }} className="font-mono" >{f.ccy}</div>
                  <div style={{ fontSize: "var(--pq-text-quote)", fontWeight: 500 }} className="font-serif" >{f.pct}</div>
                </PdfFlexBetween>
              ))}
              <PdfDivider />
              <div style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)" }}>{data.fxNote}</div>
            </PdfCard>
          </div>
        </PdfTwoCol>

        <PdfPageFooter left="Portfolio Segment · Pro" right="Page 01" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 2 */}
      <PdfPage>
        <PdfHeader tier="pro" title="PORTFOLIO SEGMENT" meta={`${data.asOf} · 02/03`} />
        <PdfGoldRule />

        <PdfSectionTitle variant="sm">Factor · 팩터 노출</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Factor</th>
              <th className="right">Exposure</th>
              <th className="right">vs S&amp;P</th>
              <th className="right">MTD Contrib</th>
              <th className="right">YTD Contrib</th>
            </tr>
          </thead>
          <tbody>
            {data.factors.map((f) => (
              <tr key={f.factor}>
                <td><strong>{f.factor}</strong></td>
                <td className="right">{f.exposure}</td>
                <td className={`right ${f.vsBenchTone}`}>{f.vsBenchmark}</td>
                <td className={`right ${f.mtdTone}`}>{f.mtdContrib}</td>
                <td className={`right ${f.ytdTone}`}>{f.ytdContrib}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfSectionTitle variant="sm">Top 5 + Bottom 3 Holdings</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th className="right">Weight</th>
              <th className="right">MTD</th>
              <th className="right">YTD</th>
              <th className="right">Contrib MTD</th>
            </tr>
          </thead>
          <tbody>
            {data.topBottom.map((h) => (
              <tr
                key={h.ticker}
                style={h.bottom ? { borderTop: "1.5px solid var(--r-rule-strong)" } : undefined}
              >
                <td><PdfTicker>{h.ticker}</PdfTicker></td>
                <td>{h.name}</td>
                <td className="right">{h.weight}</td>
                <td className={`right ${h.mtdTone}`}>{h.mtd}</td>
                <td className={`right ${h.ytdTone}`}>{h.ytd}</td>
                <td className={`right ${h.contribTone}`}>{h.contrib}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <div style={{ marginTop: 18 }}>
          <PdfCallout flat label="CFO's Note">{data.cfoNote}</PdfCallout>
        </div>

        <PdfGovBlock />
        <PdfPageFooter left="Portfolio Segment · Pro · Not investment advice" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="pro" title="PORTFOLIO SEGMENT" meta={`${data.asOf} · 03/03`} />
        <PdfGoldRule />
        <PdfDisclaimer cadence="monthly" />
      </PdfPage>
    </>
  );
}
