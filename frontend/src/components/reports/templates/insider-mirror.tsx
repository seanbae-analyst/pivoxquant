/**
 * Report 10 — Insider Mirror (Pro · 2 pages · Weekly)
 *
 * Source: /design_handoff_pdf_reports/reports/10_insider_mirror.html
 *
 * Page 1: 4-up KPI (clusters / CEO+CFO / non-10b5-1 dispositions / mirror
 *         backtest hit rate) + Acquisitions table + Dispositions table.
 * Page 2: Featured observation card + 24m mirror vs S&P 500 chart + 3-up KPI
 *         + how-to-use callout + governance + disclaimer.
 *
 * §101 회피 (2026-05-08): Form 4 공시 정보 관찰만 표시. NEVER buy / sell /
 * hold / 추천 / 따라갈 만한 / 주의가 필요한 / 청산 / 적중률 wording. 모든
 * label 은 SEC 공시 사실의 descriptive classification ("CLUSTER", "FIRST IN",
 * "SOLO") 이며, 신호 톤은 POSITIVE / NEGATIVE / NEUTRAL 만 사용한다.
 * "12m hit rate" 는 과거 backtest 결과의 사실 기록 (미래 수익 보장 아님).
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
  PdfTable,
  PdfTicker,
  PdfCard,
  PdfFlexBetween,
  PdfThreeCol,
  PdfCallout,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";
import { EmptyState } from "../empty-state";

interface BuyRow {
  ticker: string;
  name: string;
  insider: string;
  role: string;
  amount: string;
  date: string;
  signal: string;
  signalTone: "pos" | "warn";
}
interface SellRow {
  ticker: string;
  name: string;
  insider: string;
  role: string;
  amount: string;
  plan: string;
  flag: string;
  flagTone: "neg" | "neutral";
}

export interface InsiderMirrorData {
  asOf: string;
  clusterBuys: { value: string; detail: string };
  ceoCfoPair: { value: string; detail: string };
  nonPlanSells: { value: string; detail: string };
  hitRate: { value: string; detail: string };
  buys: BuyRow[];
  sells: SellRow[];
  featured: {
    badge: string;
    headline: string;
    ticker: string;
    name: string;
    body: string;
    avgPrice: string;
    lastBuy: string;
    hitRate: string;
  };
  mirror24m: { value: string; delta: string };
  winRate: { value: string; detail: string };
  avgHold: { value: string; detail: string };
  howToUse: string;
}


export function InsiderMirror({ data }: { data?: InsiderMirrorData }) {
  // No fabricated fixture -- render the honest empty state when there is no
  // real artifact data instead of a fake sample.
  if (!data) {
    return <EmptyState type="insider_mirror" reason="no_positions" />;
  }
  return (
    <>
      {/* PAGE 1 */}
      <PdfPage>
        <PdfHeader tier="pro" title="INSIDER MIRROR" meta={data.asOf} />
        <PdfGoldRule />


        <PdfEyebrow>Insider Mirror · Weekly</PdfEyebrow>
        <PdfCoverTitle size={42}>
          SEC Form 4 — insider <em>acquisitions</em>
          <br />
          observed this week.
        </PdfCoverTitle>
        <p style={{ color: "var(--r-ink-3)", fontSize: "var(--pq-text-body)", lineHeight: 1.55, marginTop: 12 }}>
          Form 4 공시 정제 — Cluster acquisitions, CEO+CFO co-occurrences, first-time filers. 정보 관찰 자료이며 매수·매도 권유가 아닙니다.
        </p>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            kpis={[
              { label: "Cluster Buys", value: data.clusterBuys.value, delta: data.clusterBuys.detail, deltaTone: "pos" },
              { label: "CEO+CFO 동반", value: data.ceoCfoPair.value, delta: data.ceoCfoPair.detail, deltaTone: "pos" },
              { label: "10b5-1 제외 매각", value: data.nonPlanSells.value, delta: data.nonPlanSells.detail, deltaTone: "neg" },
              { label: "Mirror Backtest · 12m", value: data.hitRate.value, delta: data.hitRate.detail },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Top Acquisitions · 최근 인사이더 매수 공시 (Form 4)</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Insider</th>
              <th>Role</th>
              <th className="right">$ Amount</th>
              <th className="right">Date</th>
              <th className="right">Signal</th>
            </tr>
          </thead>
          <tbody>
            {data.buys.map((b) => (
              <tr key={b.ticker}>
                <td>
                  <PdfTicker>{b.ticker}</PdfTicker>{" "}
                  <span style={{ color: "var(--r-ink-3)" }}>{b.name}</span>
                </td>
                <td>{b.insider}</td>
                <td>{b.role}</td>
                <td className="right pos">{b.amount}</td>
                <td className="right">{b.date}</td>
                <td className="right" style={{ color: b.signalTone === "pos" ? "var(--r-pos)" : "var(--r-warn)" }}>
                  {b.signal}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfSectionTitle variant="sm">Dispositions · 최근 인사이더 매도 공시 (10b5-1 제외)</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Insider</th>
              <th>Role</th>
              <th className="right">$ Amount</th>
              <th className="right">Plan</th>
              <th className="right">Flag</th>
            </tr>
          </thead>
          <tbody>
            {data.sells.map((s) => (
              <tr key={s.ticker}>
                <td>
                  <PdfTicker>{s.ticker}</PdfTicker>{" "}
                  <span style={{ color: "var(--r-ink-3)" }}>{s.name}</span>
                </td>
                <td>{s.insider}</td>
                <td>{s.role}</td>
                <td className="right neg">{s.amount}</td>
                <td className="right" style={{ color: "var(--r-ink-3)" }}>{s.plan}</td>
                <td className="right" style={{ color: s.flagTone === "neg" ? "var(--r-neg)" : "var(--r-ink-3)" }}>
                  {s.flag}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Insider Mirror · Pro" right="Page 01" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 2 — 2026-05-06 Strategy B Option 2: explicit disclaim-only PdfPage so
          chromium print engine never pushes the disclaimer onto a ghost sheet. */}
      <PdfPage>
        <PdfHeader tier="pro" title="INSIDER MIRROR" meta={`${data.asOf} · 02/03`} />
        <PdfGoldRule />

        <PdfSectionTitle variant="sm">Featured Signal · 이번 주 단일 베스트</PdfSectionTitle>
        <PdfCard>
          <PdfFlexBetween>
            <div>
              <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
                {data.featured.badge}
              </div>
              <h3 style={{ fontSize: "var(--pq-text-quote)", margin: "6px 0", fontWeight: 500 }} className="font-serif" >
                {data.featured.headline}
              </h3>
            </div>
            <PdfTicker>{data.featured.ticker}</PdfTicker>
          </PdfFlexBetween>
          <p style={{ fontSize: "var(--pq-text-body)", lineHeight: 1.65, color: "var(--r-ink-2)", marginTop: 8 }}>
            {data.featured.body}
          </p>
          <div style={{ marginTop: 12 }}>
            <PdfThreeCol>
              <div>
                <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)", marginBottom: 6 }} className="font-mono" >Avg Price</div>
                <div style={{ fontSize: "var(--pq-text-eyebrow)" }} className="font-mono" >{data.featured.avgPrice}</div>
              </div>
              <div>
                <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)", marginBottom: 6 }} className="font-mono" >Last Insider Acquisition</div>
                <div style={{ fontSize: "var(--pq-text-eyebrow)" }} className="font-mono" >{data.featured.lastBuy}</div>
              </div>
              <div>
                <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)", marginBottom: 6 }} className="font-mono" >12m Backtest</div>
                <div style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--r-pos)" }} className="font-mono" >{data.featured.hitRate}</div>
              </div>
            </PdfThreeCol>
          </div>
        </PdfCard>

        {/* Mirror-vs-S&P 24m backtest chart omitted: no per-period mirror/
            benchmark series is wired into InsiderMirrorData. Fixed SVG path
            coordinates would be a fabricated curve (CEO 2026-05-31).
            Carry-over: wire backend mirror backtest series. The Mirror 24m /
            Win Rate / Avg Hold KPIs below use real data and are retained. */}

        <div style={{ marginTop: 12 }}>
          <PdfKpiRow
            cols={3}
            kpis={[
              { label: "Mirror 24m", value: data.mirror24m.value, delta: data.mirror24m.delta, deltaTone: "pos" },
              { label: "Win Rate", value: data.winRate.value, delta: data.winRate.detail },
              { label: "Avg Hold", value: data.avgHold.value, delta: data.avgHold.detail },
            ]}
          />
        </div>

        <div style={{ marginTop: 18 }}>
          <PdfCallout label="How to Use">{data.howToUse}</PdfCallout>
        </div>

        <PdfGovBlock />
        <PdfPageFooter left="Insider Mirror · Pro · Past activity ≠ future returns" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="pro" title="INSIDER MIRROR" meta={`${data.asOf} · 03/03`} />
        <PdfGoldRule />
        <PdfDisclaimer cadence="weekly" />
      </PdfPage>
    </>
  );
}
