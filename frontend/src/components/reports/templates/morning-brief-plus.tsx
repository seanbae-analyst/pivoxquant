/**
 * Report — Morning Brief Plus (Pro · 1 page · Daily · Pre-market)
 *
 * Source: frontend/public/samples/morning_brief_plus.pdf
 *
 * The pre-market briefing. Cover headline + 4-up macro KPI row (S&P FUTURES,
 * 10Y YIELD, DXY, VIX), top moves checklist, and the one observation for the
 * open. Lives outside the dashboard auth layout so the design can be reviewed
 * without logging in.
 *
 * Compliance: POSITIVE / NEGATIVE / NEUTRAL labels only. No buy/sell/hold.
 * Cadence is "daily" — disclaimer reflects pre-market timing.
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
  PdfCard,
  PdfCallout,
  PdfNotes,
  PdfPageFooter,
  PdfDisclaimer,
  PdfSectionTitle,
} from "../pdf-primitives";

export interface MorningBriefPlusData {
  asOf: string;            // "2026-04-28"
  briefTag: string;        // "MB-2026-04-28"
  /** S&P 500 futures level + delta */
  spFutures: string;       // "5,842.25"
  spFuturesDelta: string;  // "▲ 0.42%"
  /** US 10Y yield */
  tenYieldPct: string;     // "4.18%"
  tenYieldDelta: string;   // "▼ 2bps"
  /** US Dollar Index */
  dxy: string;             // "104.32"
  dxyDelta: string;        // "▲ 0.18%"
  /** CBOE VIX */
  vix: string;             // "14.22"
  vixDelta: string;        // "▼ 0.31"
  /** Three pre-market moves to observe */
  topMoves: { body: string; meta: string; checked: boolean }[];
  /** The one observation for the open */
  observation: string;
  /** Pre-market memo — what the user is watching today */
  memoToSelf: string;
}

const DEFAULT_DATA: MorningBriefPlusData = {
  asOf: "2026-04-28",
  briefTag: "MB-2026-04-28",
  spFutures: "5,842.25",
  spFuturesDelta: "▲ 0.42%",
  tenYieldPct: "4.18%",
  tenYieldDelta: "▼ 2bps",
  dxy: "104.32",
  dxyDelta: "▲ 0.18%",
  vix: "14.22",
  vixDelta: "▼ 0.31",
  topMoves: [
    {
      body: "AAPL — 프리마켓 +1.2%, 실적 컨센서스 상회 보도",
      meta: "POSITIVE",
      checked: true,
    },
    {
      body: "TSLA — 프리마켓 −2.4%, 중국 인도량 둔화 우려",
      meta: "NEGATIVE",
      checked: false,
    },
    {
      body: "10Y yield 4.18%로 하락, 그로스 섹터 우호 환경",
      meta: "NEUTRAL",
      checked: true,
    },
  ],
  observation:
    "오늘의 한 가지 관찰: VIX 14선 회귀 + 10Y 하락은 그로스 우호 신호. " +
    "단, 지수 선물 +0.42% 갭업은 프리마켓 흐름일 뿐, 9:30 ET 개장 후 " +
    "30분 흐름을 본 뒤 판단할 것.",
  memoToSelf:
    "장중 점검: (1) AAPL 갭 메우기 여부, (2) 10Y 4.20% 위쪽 재돌파 시 " +
    "리스크 자산 약세, (3) 12:00 ET 경제지표 발표 전 포지션 점검.",
};

export function MorningBriefPlus({ data = DEFAULT_DATA }: { data?: MorningBriefPlusData }) {
  return (
    <PdfPage>
      <PdfHeader
        tier="pro"
        title="MORNING BRIEF PLUS"
        meta={`${data.asOf} · ${data.briefTag}`}
      />

      <PdfEyebrow>Morning Brief · Before The Bell</PdfEyebrow>
      <PdfCoverTitle size={42}>
        Opens in <em>3 hours</em>—<br />
        today, in <em>five lines</em>.
      </PdfCoverTitle>
      <p
        style={{
          color: "var(--r-ink-3)",
          marginTop: 12,
          fontSize: 13,
          lineHeight: 1.55,
          fontFamily: "var(--font-serif)",
        }}
      >
        Pre-market macro snapshot, three moves that matter, one observation
        for the open. Read it with coffee.
      </p>

      <div style={{ marginTop: 24 }}>
        <PdfKpiRow
          cols={4}
          kpis={[
            {
              label: "S&P Futures",
              value: data.spFutures,
              delta: data.spFuturesDelta,
              deltaTone: "pos",
            },
            {
              label: "10Y Yield",
              value: data.tenYieldPct,
              delta: data.tenYieldDelta,
              deltaTone: "neg",
            },
            {
              label: "DXY",
              value: data.dxy,
              delta: data.dxyDelta,
            },
            {
              label: "VIX",
              value: data.vix,
              delta: data.vixDelta,
              deltaTone: "neg",
            },
          ]}
        />
      </div>

      <PdfTwoCol>
        <div>
          <PdfColTitle>Top Moves · 프리마켓</PdfColTitle>
          <PdfCheckList
            items={data.topMoves.map((m) => ({
              checked: m.checked,
              body: m.body,
              meta: m.meta,
            }))}
          />
        </div>
        <div>
          <PdfColTitle>Macro Snapshot</PdfColTitle>
          <PdfCard>
            <div className="pq-pdf-kpi-lbl">Tape Tone</div>
            <div
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 28,
                marginTop: 4,
              }}
            >
              POSITIVE
            </div>
            <div
              style={{
                fontSize: 11,
                color: "var(--r-ink-3)",
                marginTop: 8,
                lineHeight: 1.55,
              }}
            >
              Futures bid · yields easing · vol compressed.
              Risk-on tilt into the open.
            </div>
          </PdfCard>
        </div>
      </PdfTwoCol>

      <div style={{ marginTop: 18 }}>
        <PdfCallout flat label="At The Open · The One Observation">
          {data.observation}
        </PdfCallout>
      </div>

      <div style={{ marginTop: 18 }}>
        <PdfSectionTitle variant="sm">Memo to Self · Today</PdfSectionTitle>
        <PdfNotes>{data.memoToSelf}</PdfNotes>
      </div>

      <PdfPageFooter
        left="For information only · pivoxquant.com"
        right={`Morning Brief Plus · ${data.briefTag}`}
      />

      <PdfDisclaimer cadence="daily" />
    </PdfPage>
  );
}
