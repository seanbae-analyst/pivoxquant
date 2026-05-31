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
import { SampleDataBadge } from "../sample-data-badge";

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

const DEFAULT: InsiderMirrorData = {
  asOf: "Week of Apr 26 · IM-2026-04",
  clusterBuys: { value: "7", detail: "5+ insiders, 30d" },
  ceoCfoPair: { value: "3", detail: "co-occurrence observed" },
  nonPlanSells: { value: "12", detail: "non-10b5-1 list" },
  hitRate: { value: "63%", detail: "12m backtest, n=84" },
  buys: [
    { ticker: "CRWD", name: "CrowdStrike", insider: "George Kurtz", role: "CEO", amount: "USD 4.2M", date: "10/22", signal: "★★★ FIRST IN 18m", signalTone: "pos" },
    { ticker: "ANET", name: "Arista Networks", insider: "Jayshree Ullal", role: "CEO", amount: "USD 3.8M", date: "10/18", signal: "★★★ CLUSTER 6×", signalTone: "pos" },
    { ticker: "SHOP", name: "Shopify", insider: "Tobias Lütke + 4", role: "CEO + Dirs", amount: "USD 2.1M", date: "10/15", signal: "★★ CLUSTER 5×", signalTone: "pos" },
    { ticker: "UBER", name: "Uber Technologies", insider: "Prashanth Mahendra", role: "CFO", amount: "USD 1.4M", date: "10/12", signal: "★★ FIRST IN 24m", signalTone: "pos" },
    { ticker: "DKNG", name: "DraftKings", insider: "Jason Robins", role: "CEO", amount: "USD 890k", date: "10/09", signal: "★ SOLO", signalTone: "warn" },
  ],
  sells: [
    { ticker: "PANW", name: "Palo Alto Networks", insider: "Nikesh Arora", role: "CEO", amount: "−USD 48M", plan: "discretionary", flag: "⚠ NON-10b5-1", flagTone: "neg" },
    { ticker: "SNOW", name: "Snowflake", insider: "Frank Slootman", role: "Chair", amount: "−USD 22M", plan: "10b5-1", flag: "routine", flagTone: "neutral" },
    { ticker: "META", name: "Meta Platforms", insider: "Mark Zuckerberg", role: "CEO", amount: "−USD 185M", plan: "10b5-1", flag: "routine", flagTone: "neutral" },
  ],
  featured: {
    badge: "★★★ FIRST IN · 18 MONTHS",
    headline: "CRWD · CrowdStrike · George Kurtz · CEO · USD 4.2M",
    ticker: "CRWD",
    name: "CrowdStrike",
    body: "18개월 만의 첫 직접 매수. 평균 주가 대비 본인 평단보다 한참 아래에서 진입. 과거 첫 매수 시점 12m 후 평균 +28%. 7월 사건 이후 −34% 빠진 자리, 평균 주가 −41% 대비 본인 평단보다 한참 아래에서 진입. 단, 이번엔 평판 회복 비용 + 보안 리텐션이 변수.",
    avgPrice: "USD 268.40",
    lastBuy: "2024-04 · USD 1.8M",
    hitRate: "68% (n=11)",
  },
  mirror24m: { value: "+62.4%", delta: "vs S&P +28.1%" },
  winRate: { value: "63%", detail: "n = 84 signals" },
  avgHold: { value: "94 days", detail: "median 76d" },
  howToUse:
    "관찰은 관찰일 뿐. 시그널 등급(★★★ / ★★ / ★)은 SEC Form 4 공시 정제 결과의 분류이며 매수·매도 권유가 아닙니다. 90일 후 본인 가설을 자가 점검하고, 본인 룰에 따라 재평가하십시오.",
};

export function InsiderMirror({ data = DEFAULT }: { data?: InsiderMirrorData }) {
  // Sample mode = template fell back to its DEFAULT fixture (no real data).
  const isSample = data === DEFAULT;
  return (
    <>
      {/* PAGE 1 */}
      <PdfPage>
        <PdfHeader tier="pro" title="INSIDER MIRROR" meta={data.asOf} />
        <PdfGoldRule />

        {/* SAMPLE banner — sample mode only. */}
        {isSample && <SampleDataBadge />}

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

        <PdfSectionTitle variant="sm">Mirror Backtest · 과거 시그널 추적</PdfSectionTitle>
        <PdfCard>
          <PdfFlexBetween>
            <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
              Mirror vs S&amp;P 500 · Last 24m
            </div>
            <div style={{ display: "flex", gap: 14, fontSize: "var(--pq-text-eyebrow)", color: "var(--r-ink-3)", }} className="font-mono" >
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#0e0e0e" }} />Mirror Portfolio</span>
              <span><span style={{ display: "inline-block", width: 8, height: 8, marginRight: 5, background: "#c0c0c0" }} />S&amp;P 500</span>
            </div>
          </PdfFlexBetween>
          <svg viewBox="0 0 600 160" preserveAspectRatio="none" style={{ width: "100%", height: 160, marginTop: 12 }}>
            <defs>
              <linearGradient id="mirror-fade" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#0e0e0e" stopOpacity=".18" />
                <stop offset="1" stopColor="#0e0e0e" stopOpacity="0" />
              </linearGradient>
            </defs>
            <line x1="0" y1="40" x2="600" y2="40" stroke="#ececec" strokeWidth="1" />
            <line x1="0" y1="80" x2="600" y2="80" stroke="#ececec" strokeWidth="1" />
            <line x1="0" y1="120" x2="600" y2="120" stroke="#ececec" strokeWidth="1" />
            <path d="M0,130 L60,118 L120,108 L180,92 L240,98 L300,82 L360,68 L420,52 L480,42 L540,30 L600,22 L600,160 L0,160 Z" fill="url(#mirror-fade)" opacity=".5" />
            <path d="M0,130 L60,118 L120,108 L180,92 L240,98 L300,82 L360,68 L420,52 L480,42 L540,30 L600,22" stroke="#0e0e0e" strokeWidth="2" fill="none" />
            <path d="M0,130 L60,124 L120,118 L180,112 L240,108 L300,98 L360,92 L420,84 L480,78 L540,72 L600,68" stroke="#c0c0c0" strokeWidth="1.4" fill="none" strokeDasharray="3 3" />
          </svg>
        </PdfCard>

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
