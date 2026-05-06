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

const DEFAULT: PortfolioSegmentData = {
  asOf: "April 2026 · PS-2026-04",
  nav: { value: "$1,242k", delta: "MTD +4.2%" },
  holdings: { value: "28", delta: "target 25-30" },
  avgPos: { value: "3.4%", delta: "max 11.5%" },
  activeShare: { value: "82%", delta: "vs S&P 500" },
  sectors: [
    { name: "Information Tech", pct: 84, pctDisplay: "42% / 35% lim", tone: "neg" },
    { name: "Healthcare", pct: 36, pctDisplay: "18%" },
    { name: "Communication", pct: 24, pctDisplay: "12%" },
    { name: "Consumer Disc.", pct: 20, pctDisplay: "10%", flat: true },
    { name: "Financials", pct: 16, pctDisplay: "8%", flat: true },
    { name: "Industrials", pct: 8, pctDisplay: "4%", flat: true },
    { name: "Cash", pct: 12, pctDisplay: "6%", flat: true },
  ],
  geography: [
    { name: "US", pct: 78, pctDisplay: "72%" },
    { name: "Korea", pct: 18, pctDisplay: "12%", flat: true },
    { name: "Europe", pct: 12, pctDisplay: "8%", flat: true },
    { name: "EM ex-Korea", pct: 6, pctDisplay: "2%", flat: true },
    { name: "Cash", pct: 9, pctDisplay: "6%", flat: true },
  ],
  fx: [
    { ccy: "USD", pct: "88%" },
    { ccy: "KRW", pct: "12%" },
    { ccy: "EUR", pct: "0%" },
  ],
  fxNote: "USD 단일 노출. 환헤지 없음. KRW −5% 시 NAV +0.6%.",
  factors: [
    { factor: "Quality", exposure: "+0.84", vsBenchmark: "+0.62", vsBenchTone: "pos", mtdContrib: "+0.42%", mtdTone: "pos", ytdContrib: "+2.18%", ytdTone: "pos" },
    { factor: "Momentum", exposure: "+0.42", vsBenchmark: "+0.38", vsBenchTone: "pos", mtdContrib: "+0.81%", mtdTone: "pos", ytdContrib: "+3.42%", ytdTone: "pos" },
    { factor: "Growth", exposure: "+0.92", vsBenchmark: "+0.72", vsBenchTone: "pos", mtdContrib: "+0.52%", mtdTone: "pos", ytdContrib: "+1.84%", ytdTone: "pos" },
    { factor: "Value", exposure: "−0.32", vsBenchmark: "−0.41", vsBenchTone: "neg", mtdContrib: "−0.18%", mtdTone: "neg", ytdContrib: "−0.92%", ytdTone: "neg" },
    { factor: "Low Vol", exposure: "−0.18", vsBenchmark: "−0.20", vsBenchTone: "neutral", mtdContrib: "+0.04%", mtdTone: "neutral", ytdContrib: "−0.24%", ytdTone: "neg" },
    { factor: "Size (Small)", exposure: "−0.62", vsBenchmark: "−0.58", vsBenchTone: "neutral", mtdContrib: "+0.12%", mtdTone: "neutral", ytdContrib: "+0.42%", ytdTone: "pos" },
  ],
  topBottom: [
    { ticker: "NVDA", name: "NVIDIA", weight: "11.5%", mtd: "+8.2%", mtdTone: "pos", ytd: "+42.1%", ytdTone: "pos", contrib: "+0.94%", contribTone: "pos" },
    { ticker: "PLTR", name: "Palantir", weight: "7.8%", mtd: "+12.4%", mtdTone: "pos", ytd: "+58.2%", ytdTone: "pos", contrib: "+0.97%", contribTone: "pos" },
    { ticker: "MSFT", name: "Microsoft", weight: "6.4%", mtd: "+3.8%", mtdTone: "pos", ytd: "+18.4%", ytdTone: "pos", contrib: "+0.24%", contribTone: "pos" },
    { ticker: "AVGO", name: "Broadcom", weight: "5.2%", mtd: "+6.1%", mtdTone: "pos", ytd: "+24.8%", ytdTone: "pos", contrib: "+0.32%", contribTone: "pos" },
    { ticker: "TSM", name: "Taiwan Semi", weight: "4.8%", mtd: "+4.2%", mtdTone: "pos", ytd: "+22.1%", ytdTone: "pos", contrib: "+0.20%", contribTone: "pos" },
    { ticker: "META", name: "Meta", weight: "3.1%", mtd: "−4.2%", mtdTone: "neg", ytd: "+8.1%", ytdTone: "pos", contrib: "−0.13%", contribTone: "neg", bottom: true },
    { ticker: "UNH", name: "UnitedHealth", weight: "2.4%", mtd: "−3.8%", mtdTone: "neg", ytd: "−12.4%", ytdTone: "neg", contrib: "−0.09%", contribTone: "neg" },
    { ticker: "DIS", name: "Disney", weight: "1.8%", mtd: "−2.1%", mtdTone: "neg", ytd: "−5.2%", ytdTone: "neg", contrib: "−0.04%", contribTone: "neg" },
  ],
  cfoNote:
    "알파의 78%가 종목 선정에서 발생, 22%가 섹터 틸트. 팩터로 보면 Quality + Growth 더블 노출. 다음 달: Tech 한도 위반 정상화, Value 노출 0.0 회복 검토.",
};

export function PortfolioSegment({ data = DEFAULT }: { data?: PortfolioSegmentData }) {
  return (
    <>
      {/* PAGE 1 */}
      <PdfPage>
        <PdfHeader tier="pro" title="PORTFOLIO SEGMENT" meta={`${data.asOf} · 01/02`} />
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
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--r-ink-3)" }}>{f.ccy}</div>
                  <div style={{ fontFamily: "var(--font-serif)", fontSize: 24, fontWeight: 500 }}>{f.pct}</div>
                </PdfFlexBetween>
              ))}
              <PdfDivider />
              <div style={{ fontSize: 10, color: "var(--r-ink-3)" }}>{data.fxNote}</div>
            </PdfCard>
          </div>
        </PdfTwoCol>

        <PdfPageFooter left="Portfolio Segment · Pro" right="Page 01" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 2 */}
      <PdfPage>
        <PdfHeader tier="pro" title="PORTFOLIO SEGMENT" meta={`${data.asOf} · 02/02`} />
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
        <PdfDisclaimer cadence="monthly" />
      </PdfPage>
    </>
  );
}
