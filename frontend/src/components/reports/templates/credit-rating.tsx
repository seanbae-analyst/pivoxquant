/**
 * Report 14 — Credit Rating (Premium · 3 pages · Quarterly)
 *
 * Source: /design_handoff_pdf_reports/reports/14_credit_rating.html
 *
 * Page 1: Cover (eyebrow + title + sub + 4-up cover meta).
 * Page 2: Pullquote + Rating Distribution alloc + Quarter Changes table (upgrades/downgrades).
 * Page 3: Watchlist cards (Negative outlook + downgrade notes) + CDS Spread Watch table
 *         + CFO's Note + sign row + governance + disclaimer.
 *
 * Compliance: Credit watch is descriptive; "ON WATCH" / "DOWNGRADE BIAS" are
 * agency-style classifications, not buy/sell/hold. POSITIVE / NEGATIVE / NEUTRAL only.
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
  PdfSectionTitle,
  PdfAllocList,
  PdfTable,
  PdfTicker,
  PdfFlexBetween,
  PdfCallout,
  PdfSignRow,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";

interface RatingChange {
  ticker: string;
  agency: string;
  prev: string;
  now: string;
  nowTone: "pos" | "neg" | "neutral";
  outlook: string;
  outlookTone: "pos" | "neg" | "warn";
  action: string;
  actionTone: "pos" | "neg" | "warn" | "neutral";
}
interface CdsRow {
  ticker: string;
  cds: string;
  delta: string;
  deltaTone: "pos" | "neg";
  vsImplied: string;
  vsImpliedTone: "pos" | "neg" | "neutral";
  signal: string;
  signalTone: "pos" | "neg" | "warn";
}

export interface CreditRatingData {
  doc: string;
  reviewed: string;
  upgrades: string;
  downgrades: string;
  onWatch: string;
  pullquote: string;
  distribution: { name: string; pct: number; pctDisplay: string; warn?: boolean; flat?: boolean }[];
  changes: RatingChange[];
  watchPrimary: { lbl: string; title: string; ticker: string; body: string };
  watchSecondary: { lbl: string; body: string }[];
  cds: CdsRow[];
  cfoNote: string;
}

const DEFAULT: CreditRatingData = {
  doc: "Q1 2026 · CR-2026-04",
  reviewed: "28",
  upgrades: "4",
  downgrades: "2",
  onWatch: "3",
  pullquote: "\"주식이 환상을 팔 때, 채권은 진실을 말한다.\" — 분기 신용 점검의 한 줄.",
  distribution: [
    { name: "AAA / AA", pct: 38, pctDisplay: "22% NAV" },
    { name: "A", pct: 62, pctDisplay: "38% NAV" },
    { name: "BBB", pct: 48, pctDisplay: "28% NAV" },
    { name: "BB · High Yield", pct: 14, pctDisplay: "8% NAV", warn: true, flat: true },
    { name: "NR · Not Rated", pct: 8, pctDisplay: "4% NAV", flat: true },
  ],
  changes: [
    { ticker: "NVDA", agency: "S&P", prev: "A+", now: "AA−", nowTone: "pos", outlook: "Stable", outlookTone: "pos", action: "▲ UPGRADE", actionTone: "pos" },
    { ticker: "MSFT", agency: "Moody's", prev: "Aaa", now: "Aaa", nowTone: "neutral", outlook: "Stable", outlookTone: "pos", action: "UNCHANGED", actionTone: "neutral" },
    { ticker: "META", agency: "S&P", prev: "AA−", now: "AA", nowTone: "pos", outlook: "Positive", outlookTone: "pos", action: "▲ UPGRADE", actionTone: "pos" },
    { ticker: "DIS", agency: "Moody's", prev: "A2", now: "A3", nowTone: "neg", outlook: "Negative", outlookTone: "warn", action: "▼ DOWNGRADE", actionTone: "neg" },
    { ticker: "UNH", agency: "Fitch", prev: "A+", now: "A+", nowTone: "neutral", outlook: "Negative", outlookTone: "neg", action: "⚠ ON WATCH", actionTone: "warn" },
    { ticker: "DKNG", agency: "S&P", prev: "B+", now: "B", nowTone: "neg", outlook: "Negative", outlookTone: "neg", action: "▼ DOWNGRADE", actionTone: "neg" },
    { ticker: "PLTR", agency: "S&P", prev: "BB+", now: "BBB−", nowTone: "pos", outlook: "Stable", outlookTone: "pos", action: "▲ UPGRADE · IG", actionTone: "pos" },
  ],
  watchPrimary: {
    lbl: "⚠ NEGATIVE OUTLOOK",
    title: "UNH · UnitedHealth · A+ → ?",
    ticker: "UNH",
    body: "Fitch 12개월 내 한 단계 강등 가능성. MLR 상승, DOJ 조사, MA 가입자 이탈. CDS 스프레드 6m +35bp. 주가 −18%이지만 채권 시장은 한 분기 먼저 신호. 비중 2.4% → 1.2% 검토.",
  },
  watchSecondary: [
    { lbl: "DKNG · Downgrade B+ → B", body: "High yield 영역 진입. 이자비용 +85bp, 차환 부담 가중. 주식 비중 1.8% 유지 가능하나 채권 노출 0%." },
    { lbl: "DIS · A2 → A3", body: "Streaming 비용 + 콘텐츠 부진. 두 분기 연속 강등은 펀더멘털 신호. 주가 사이드는 회복 중이나 채권 사이드는 비관적." },
  ],
  cds: [
    { ticker: "UNH", cds: "82bp", delta: "+35bp", deltaTone: "neg", vsImplied: "+22bp wide", vsImpliedTone: "neg", signal: "⚠ DOWNGRADE BIAS", signalTone: "neg" },
    { ticker: "DIS", cds: "68bp", delta: "+18bp", deltaTone: "neg", vsImplied: "+8bp", vsImpliedTone: "neutral", signal: "WATCH", signalTone: "warn" },
    { ticker: "DKNG", cds: "282bp", delta: "+62bp", deltaTone: "neg", vsImplied: "+48bp", vsImpliedTone: "neg", signal: "⚠ STRESS", signalTone: "neg" },
    { ticker: "META", cds: "28bp", delta: "−8bp", deltaTone: "pos", vsImplied: "−12bp tight", vsImpliedTone: "pos", signal: "▲ UPGRADE BIAS", signalTone: "pos" },
  ],
  cfoNote:
    "채권 시장은 두 분기 먼저 본다. UNH·DKNG 두 종목 비중 합산 4.2% → 다음 리밸런스에 2% 이하 검토. PLTR IG 진입은 무빙오프, 비중 +1%p 검토.",
};

export function CreditRating({ data = DEFAULT }: { data?: CreditRatingData }) {
  return (
    <>
      {/* PAGE 1 — COVER */}
      <PdfPage>
        <PdfHeader tier="premium" title="CREDIT RATING" meta={data.doc} />

        <div style={{ marginTop: "30mm" }}>
          <PdfCoverEyebrow>Credit Rating Review · Quarterly</PdfCoverEyebrow>
          <PdfCoverTitle>
            Q1 2026<br />
            <em>Credit Watch.</em>
          </PdfCoverTitle>
          <PdfCoverSub>
            Rating moves across holdings this quarter — upgrades, watch, downgrades. Bond-market signals the equity tape won&rsquo;t show you.
          </PdfCoverSub>
        </div>

        <div style={{ marginTop: "auto", paddingTop: "30mm" }}>
          <PdfCoverMetaGrid
            items={[
              { label: "Holdings Reviewed", value: data.reviewed },
              { label: "Upgrades", value: data.upgrades },
              { label: "Downgrades", value: data.downgrades },
              { label: "On Watch", value: data.onWatch },
            ]}
          />
        </div>

        <PdfCoverFoot />
      </PdfPage>

      {/* PAGE 2 */}
      <PdfPage>
        <PdfHeader tier="premium" title="CREDIT RATING" meta="Q1 2026 · 02/04" />
        <PdfGoldRule />

        <PdfPullquote>{data.pullquote}</PdfPullquote>

        <PdfSectionTitle>Rating Distribution · 분포</PdfSectionTitle>
        <PdfAllocList
          items={data.distribution.map((d) => ({
            name: <strong>{d.name}</strong>,
            pct: d.pct,
            pctDisplay: (
              <span style={{ color: d.warn ? "var(--r-warn)" : undefined }}>{d.pctDisplay}</span>
            ),
          }))}
        />

        <PdfSectionTitle variant="sm">Quarter Changes · 변동</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Agency</th>
              <th className="right">Prev</th>
              <th className="right">Now</th>
              <th className="right">Outlook</th>
              <th className="right">Action</th>
            </tr>
          </thead>
          <tbody>
            {data.changes.map((c) => (
              <tr key={c.ticker}>
                <td><PdfTicker>{c.ticker}</PdfTicker></td>
                <td>{c.agency}</td>
                <td className="right">{c.prev}</td>
                <td className={`right ${c.nowTone === "neutral" ? "" : c.nowTone}`}>{c.now}</td>
                <td className="right" style={{ color: c.outlookTone === "pos" ? "var(--r-pos)" : c.outlookTone === "neg" ? "var(--r-neg)" : "var(--r-warn)" }}>
                  {c.outlook}
                </td>
                <td className="right" style={{ color: c.actionTone === "pos" ? "var(--r-pos)" : c.actionTone === "neg" ? "var(--r-neg)" : c.actionTone === "warn" ? "var(--r-warn)" : "var(--r-ink-3)" }}>
                  {c.action}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Credit Rating · Premium" right="Page 02" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 3 — 2026-05-06 Strategy B Option 2: explicit disclaim-only PdfPage so
          chromium print engine never pushes the disclaimer onto a ghost sheet. */}
      <PdfPage>
        <PdfHeader tier="premium" title="CREDIT RATING" meta="Q1 2026 · 03/04" />
        <PdfGoldRule />

        <PdfSectionTitle>Watchlist · 끊어질 위험</PdfSectionTitle>

        <div style={{ border: "1.5px solid var(--r-neg)", padding: 22, borderRadius: 6, marginBottom: 14 }}>
          <PdfFlexBetween>
            <div>
              <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
                {data.watchPrimary.lbl}
              </div>
              <h3 style={{ fontSize: "var(--pq-text-quote)", margin: "6px 0", fontWeight: 500 }} className="font-serif" >
                {data.watchPrimary.title}
              </h3>
            </div>
            <PdfTicker>{data.watchPrimary.ticker}</PdfTicker>
          </PdfFlexBetween>
          <p style={{ fontSize: "var(--pq-text-body)", lineHeight: 1.65, color: "var(--r-ink-2)", marginTop: 12 }}>
            {data.watchPrimary.body}
          </p>
        </div>

        {data.watchSecondary.map((w, i) => (
          <div
            key={i}
            style={{ borderLeft: "3px solid var(--r-warn)", padding: 18, background: "var(--r-bg-soft)", marginBottom: 14, borderRadius: 4 }}
          >
            <div style={{ fontSize: "var(--pq-text-kicker)", letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }} className="font-mono" >
              {w.lbl}
            </div>
            <p style={{ fontSize: "var(--pq-text-eyebrow)", lineHeight: 1.6, color: "var(--r-ink-2)", marginTop: 6 }}>{w.body}</p>
          </div>
        ))}

        <PdfSectionTitle variant="sm">CDS Spread Watch · 시장이 매기는 가격</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Ticker</th>
              <th className="right">5y CDS</th>
              <th className="right">3m Δ</th>
              <th className="right">vs Rating Implied</th>
              <th className="right">Signal</th>
            </tr>
          </thead>
          <tbody>
            {data.cds.map((c) => (
              <tr key={c.ticker}>
                <td><PdfTicker>{c.ticker}</PdfTicker></td>
                <td className="right">{c.cds}</td>
                <td className={`right ${c.deltaTone}`}>{c.delta}</td>
                <td className="right" style={{ color: c.vsImpliedTone === "pos" ? "var(--r-pos)" : c.vsImpliedTone === "neg" ? "var(--r-neg)" : undefined }}>
                  {c.vsImplied}
                </td>
                <td className="right" style={{ color: c.signalTone === "pos" ? "var(--r-pos)" : c.signalTone === "neg" ? "var(--r-neg)" : "var(--r-warn)" }}>
                  {c.signal}
                </td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <div style={{ marginTop: 18 }}>
          <PdfCallout flat label="CFO's Note">{data.cfoNote}</PdfCallout>
        </div>

        <PdfSignRow left="분석자 · 홍길동" right="검토 일자 · Apr 26, 2026" />

        <PdfGovBlock />
        <PdfPageFooter left="Credit Rating · Premium · Not investment advice" right="Page 03" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 4 — DISCLAIMER (atomic disclaim-only sheet) */}
      <PdfPage>
        <PdfHeader tier="premium" title="CREDIT RATING" meta="Q1 2026 · 04/04" />
        <PdfGoldRule />
        <PdfDisclaimer cadence="quarterly" />
      </PdfPage>
    </>
  );
}
