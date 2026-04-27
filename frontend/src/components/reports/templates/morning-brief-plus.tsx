/**
 * Report 02 — Morning Brief Plus (Free · 1 page · Daily)
 *
 * Source: /design_handoff_pdf_reports/reports/02_morning_brief_plus.html
 *
 * Pre-bell snapshot. Cover headline ("Opens in 3 hours — today, in five lines"),
 * 3-up KPI row (futures / yields / DXY+VIX), 5-headline overnight check list,
 * two-column today's calendar + holdings watch with alloc bars,
 * single bias callout, page footer + disclaimer.
 *
 * Compliance: NEUTRAL framing only. No buy/sell/hold. Macro/holdings
 * meta tags are observation labels, not recommendations.
 */

"use client";

import {
  PdfPage,
  PdfHeader,
  PdfEyebrow,
  PdfCoverTitle,
  PdfKpiRow,
  PdfTwoCol,
  PdfColTitle,
  PdfCheckList,
  PdfTable,
  PdfAllocList,
  PdfCallout,
  PdfPageFooter,
  PdfDisclaimer,
  PdfSectionTitle,
  PdfTicker,
} from "../pdf-primitives";

export interface MorningBriefPlusData {
  asOf: string; // "Apr 26, 2026 · 06:30 KST"
  futures: { value: string; delta: string };
  yield10y: { value: string; delta: string };
  dxyVix: { value: string; tilt: string };
  overnight: { tag: string; bold: string; body: string; checked: boolean }[];
  calendar: { time: string; event: string; cons: string }[];
  watchlist: { ticker: string; pct: number; pctDisplay: string; flat?: boolean; tone?: "pos" | "neg" }[];
  todayBias: string;
}

const DEFAULT: MorningBriefPlusData = {
  asOf: "Apr 26, 2026 · 06:30 KST",
  futures: { value: "+0.42%", delta: "5,287 ▲ 22.1" },
  yield10y: { value: "4.18%", delta: "▼ 3bp" },
  dxyVix: { value: "104.2 / 13.8", tilt: "risk-on tilt" },
  overnight: [
    {
      tag: "MACRO",
      bold: "Fed 위원 발언",
      body: "12월 인하 가능성 후퇴. 채권 강세.",
      checked: true,
    },
    {
      tag: "HOLDINGS",
      bold: "NVDA 시간외 +2.4%",
      body: "신규 칩 발표 임박 루머. 보유 종목 직접 영향.",
      checked: true,
    },
    {
      tag: "COMMODITY",
      bold: "유가 −1.8%",
      body: "OPEC+ 감산 합의 이견 보도.",
      checked: true,
    },
    {
      tag: "FX",
      bold: "BOJ 금리 동결",
      body: "엔화 약세 지속, USD/JPY 158 돌파.",
      checked: false,
    },
    {
      tag: "EARNINGS",
      bold: "META 가이던스 상향",
      body: "광고매출 +12% 가이드, 시간외 +3.1%.",
      checked: false,
    },
  ],
  calendar: [
    { time: "21:30", event: "CPI · YoY", cons: "3.1%" },
    { time: "22:00", event: "WMT · Earnings", cons: "EPS $0.52" },
    { time: "23:00", event: "Williams 발언 (NY Fed)", cons: "—" },
    { time: "06:00", event: "NVDA · After-hours", cons: "EPS $5.62" },
  ],
  watchlist: [
    { ticker: "NVDA", pct: 78, pctDisplay: "+2.4%", tone: "pos" },
    { ticker: "META", pct: 62, pctDisplay: "+3.1%", tone: "pos" },
    { ticker: "AAPL", pct: 48, pctDisplay: "+0.2%", flat: true },
    { ticker: "TSLA", pct: 32, pctDisplay: "−0.8%", flat: true, tone: "neg" },
  ],
  todayBias:
    "오늘은 관망. CPI 결과 보고 움직이자. 미리 뛰지 말 것. " +
    "장중 헤드라인보다 21:30 데이터가 우선.",
};

const TONE_COLOR: Record<"pos" | "neg" | "neutral", string | undefined> = {
  pos: "var(--r-pos)",
  neg: "var(--r-neg)",
  neutral: undefined,
};

export function MorningBriefPlus({ data = DEFAULT }: { data?: MorningBriefPlusData }) {
  return (
    <PdfPage>
      <PdfHeader tier="free" title="MORNING BRIEF PLUS" meta={data.asOf} />

      <PdfEyebrow>Morning Brief · Before the Bell</PdfEyebrow>
      <PdfCoverTitle size={38}>
        Opens in <em>3 hours</em>—<br />
        today, in <em>five lines</em>.
      </PdfCoverTitle>

      <div style={{ marginTop: 24 }}>
        <PdfKpiRow
          cols={3}
          kpis={[
            {
              label: "S&P Futures",
              value: data.futures.value,
              delta: data.futures.delta,
              deltaTone: "pos",
              small: true,
            },
            {
              label: "10Y Yield",
              value: data.yield10y.value,
              delta: data.yield10y.delta,
              deltaTone: "neg",
              small: true,
            },
            {
              label: "DXY · VIX",
              value: data.dxyVix.value,
              delta: data.dxyVix.tilt,
              small: true,
            },
          ]}
        />
      </div>

      <PdfSectionTitle variant="sm">Overnight · 새벽에 일어난 것</PdfSectionTitle>
      <PdfCheckList
        items={data.overnight.map((row) => ({
          checked: row.checked,
          body: (
            <span>
              <strong>{row.bold}</strong> — {row.body}
            </span>
          ),
          meta: row.tag,
        }))}
      />

      <div style={{ marginTop: 24 }}>
        <PdfTwoCol>
          <div>
            <PdfColTitle>Today&apos;s Calendar · 오늘 일정</PdfColTitle>
            <PdfTable>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th className="right">Cons.</th>
                </tr>
              </thead>
              <tbody>
                {data.calendar.map((row, i) => (
                  <tr key={i}>
                    <td>{row.time}</td>
                    <td>{row.event}</td>
                    <td className="right">{row.cons}</td>
                  </tr>
                ))}
              </tbody>
            </PdfTable>
          </div>
          <div>
            <PdfColTitle>Watch · 오늘 보유 종목 체크</PdfColTitle>
            <PdfAllocList
              items={data.watchlist.map((w) => ({
                name: <PdfTicker>{w.ticker}</PdfTicker>,
                pct: w.pct,
                pctDisplay: (
                  <span style={{ color: TONE_COLOR[w.tone ?? "neutral"] }}>
                    {w.pctDisplay}
                  </span>
                ),
              }))}
            />
          </div>
        </PdfTwoCol>
      </div>

      <div style={{ marginTop: 18 }}>
        <PdfCallout flat label="Today's Bias · 오늘의 한 줄">
          {data.todayBias}
        </PdfCallout>
      </div>

      <PdfPageFooter
        left="For information only · pivoxquant.com"
        right="Morning Brief Plus · Daily"
      />
      <PdfDisclaimer cadence="daily" />
    </PdfPage>
  );
}
