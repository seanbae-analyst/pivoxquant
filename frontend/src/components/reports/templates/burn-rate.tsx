/**
 * Report 15 — Burn Rate (Premium · 2 pages · Monthly)
 *
 * Source: /design_handoff_pdf_reports/reports/15_burn_rate.html
 *
 * Page 1: 3-up KPI (holdings tracked / avg runway / combined cash)
 *         + Runway Ranking table (8 holdings).
 * Page 2: Critical cards (RIVN 7mo / LCID 5mo) + Watch card (RBLX) + CFO's Note
 *         + governance + disclaimer.
 *
 * Compliance: Cash runway tracking. "PROFITABLE / SAFE / WATCH / CRITICAL" are
 * descriptive cash status, not buy/sell/hold. Action lines describe portfolio
 * sizing rules, not investment recommendations.
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
  PdfCheckList,
  PdfCallout,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
  PdfDisclaimerMini,
} from "../pdf-primitives";

type BurnStatus = "PROFITABLE" | "SAFE" | "WATCH" | "CRITICAL";

interface BurnRow {
  ticker: string;
  name: string;
  cash: string;
  qBurn: string;
  qBurnTone: "pos" | "neg";
  runway: string;
  runwayTone?: "pos" | "warn" | "neg";
  status: BurnStatus;
  position: string;
}

export interface BurnRateData {
  asOf: string;
  tracked: { value: string; detail: string };
  avgRunway: { value: string; detail: string };
  combinedCash: { value: string; detail: string };
  rows: BurnRow[];
  critical: {
    ticker: string;
    name: string;
    runwayMonths: number;
    runwayLabel: string;
    runwayLabelTone: "warn" | "neg";
    cashBurnLine: string;
    note: string;
    action: string;
  }[];
  watch: {
    ticker: string;
    name: string;
    runway: string;
    cashBurnLine: string;
    note: string;
  };
  cfoNote: string;
}

const STATUS_TONE: Record<BurnStatus, string | undefined> = {
  PROFITABLE: "var(--r-pos)",
  SAFE: undefined,
  WATCH: "var(--r-warn)",
  CRITICAL: "var(--r-neg)",
};

const DEFAULT: BurnRateData = {
  asOf: "April 2026",
  tracked: { value: "8", detail: "unprofitable growth" },
  avgRunway: { value: "22 mo", detail: "2 below 12mo" },
  combinedCash: { value: "$48.2B", detail: "+$2.1B QoQ" },
  rows: [
    { ticker: "SHOP", name: "Shopify", cash: "$5.2B", qBurn: "+$180M", qBurnTone: "pos", runway: "∞", runwayTone: "pos", status: "PROFITABLE", position: "3.2%" },
    { ticker: "CRWD", name: "CrowdStrike", cash: "$3.8B", qBurn: "+$220M", qBurnTone: "pos", runway: "∞", runwayTone: "pos", status: "PROFITABLE", position: "2.1%" },
    { ticker: "PLTR", name: "Palantir", cash: "$4.0B", qBurn: "+$140M", qBurnTone: "pos", runway: "∞", runwayTone: "pos", status: "PROFITABLE", position: "1.8%" },
    { ticker: "U", name: "Unity", cash: "$1.6B", qBurn: "−$54M", qBurnTone: "neg", runway: "29 mo", status: "SAFE", position: "1.4%" },
    { ticker: "PATH", name: "UiPath", cash: "$1.8B", qBurn: "−$42M", qBurnTone: "neg", runway: "43 mo", status: "SAFE", position: "0.9%" },
    { ticker: "RBLX", name: "Roblox", cash: "$3.1B", qBurn: "−$210M", qBurnTone: "neg", runway: "15 mo", status: "WATCH", position: "0.7%" },
    { ticker: "RIVN", name: "Rivian", cash: "$7.9B", qBurn: "−$1.2B", qBurnTone: "neg", runway: "7 mo", runwayTone: "warn", status: "CRITICAL", position: "0.4%" },
    { ticker: "LCID", name: "Lucid", cash: "$3.2B", qBurn: "−$680M", qBurnTone: "neg", runway: "5 mo", runwayTone: "neg", status: "CRITICAL", position: "0.2%" },
  ],
  critical: [
    {
      ticker: "RIVN",
      name: "Rivian Automotive",
      runwayMonths: 7,
      runwayLabel: "7 months",
      runwayLabelTone: "warn",
      cashBurnLine: "cash $7.9B · burn $1.2B/q",
      note: "다음 분기 추가 자금 조달 (전환사채 or 증자) 가능성 높음. 희석 위험. 보유는 0.4%로 작지만 추가 매수 금지. 다음 실적 발표(Q3) 가이던스 핵심.",
      action: "자금 조달 발표 시 즉시 청산 검토",
    },
    {
      ticker: "LCID",
      name: "Lucid Group",
      runwayMonths: 5,
      runwayLabel: "5 months",
      runwayLabelTone: "neg",
      cashBurnLine: "cash $3.2B · burn $680M/q",
      note: "Saudi PIF 추가 출자 확률 높지만 시점 불확실. 5개월은 임계치. 현재 0.2% 비중도 sentimental. 정리 검토.",
      action: "다음 30일 내 청산",
    },
  ],
  watch: {
    ticker: "RBLX",
    name: "Roblox",
    runway: "15 months runway",
    cashBurnLine: "$3.1B / −$210M per quarter",
    note: "User growth 회복 중. 현금흐름 turn 신호 보일 때까지 비중 동결. 다음 분기 burn 둔화 확인 필수.",
  },
  cfoNote:
    "Cash is oxygen. 그로스 스토리에 빠지면 산소를 잊는다. 매월 점검 — 한 종목이라도 12개월 밑으로 떨어지면 자동 경고.",
};

export function BurnRate({ data = DEFAULT }: { data?: BurnRateData }) {
  return (
    <>
      {/* PAGE 1 */}
      <PdfPage>
        <PdfHeader tier="premium" title="BURN RATE" meta={`${data.asOf} · BR-2026-04 · 01/02`} />
        <PdfGoldRule />

        <PdfEyebrow>Burn Rate · For Growth Holdings</PdfEyebrow>
        <PdfCoverTitle size={42}>
          How long until
          <br />
          <em>they run out</em>?
        </PdfCoverTitle>
        <p style={{ color: "var(--r-ink-3)", fontSize: 13, lineHeight: 1.55, marginTop: 12, maxWidth: "140mm" }}>
          Cash burn and runway across growth names. Who survives the next round, who doesn&rsquo;t.
        </p>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            cols={3}
            kpis={[
              { label: "Holdings Tracked", value: data.tracked.value, delta: data.tracked.detail },
              { label: "Avg Runway", value: data.avgRunway.value, delta: data.avgRunway.detail, deltaTone: "warn" },
              { label: "Combined Cash", value: data.combinedCash.value, delta: data.combinedCash.detail, deltaTone: "pos" },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Runway Ranking · 활주로 순위</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>Holding</th>
              <th className="right">Cash</th>
              <th className="right">Q Burn</th>
              <th className="right">Runway</th>
              <th>Status</th>
              <th className="right">Position</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.ticker}>
                <td>
                  <PdfTicker>{r.ticker}</PdfTicker>
                  {r.name}
                </td>
                <td className="right">{r.cash}</td>
                <td className={`right ${r.qBurnTone}`}>{r.qBurn}</td>
                <td className="right" style={{ color: r.runwayTone === "warn" ? "var(--r-warn)" : r.runwayTone === "neg" ? "var(--r-neg)" : r.runwayTone === "pos" ? "var(--r-pos)" : undefined }}>
                  {r.runway}
                </td>
                <td>
                  <span style={{ color: STATUS_TONE[r.status] }}>{r.status}</span>
                </td>
                <td className="right">{r.position}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Burn Rate · Premium" right="Page 01" />
        <PdfDisclaimerMini />
      </PdfPage>

      {/* PAGE 2 */}
      <PdfPage>
        <PdfHeader tier="premium" title="BURN RATE" meta={`${data.asOf} · BR-2026-04 · 02/02`} />
        <PdfGoldRule />

        <PdfEyebrow>02 — Critical Watch</PdfEyebrow>
        <PdfSectionTitle>Critical · 12개월 미만 활주로</PdfSectionTitle>

        {data.critical.map((c) => {
          const fillPct = Math.max(8, Math.min(40, (c.runwayMonths / 24) * 100));
          return (
            <PdfCard key={c.ticker}>
              <PdfFlexBetween style={{ marginBottom: 8 }}>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }}>
                    {c.ticker} · {c.name}
                  </div>
                  <h3 style={{ fontFamily: "var(--font-serif)", fontSize: 24, margin: 0, fontWeight: 500 }}>
                    Runway:{" "}
                    <span style={{ color: c.runwayLabelTone === "warn" ? "var(--r-gold)" : "var(--r-neg)" }}>
                      {c.runwayLabel}
                    </span>
                  </h3>
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>{c.cashBurnLine}</div>
              </PdfFlexBetween>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "30mm 1fr 18mm",
                  alignItems: "center",
                  gap: 12,
                  padding: "9px 0",
                }}
              >
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>Runway gauge</div>
                <div style={{ height: 8, background: "var(--r-bg-soft)", borderRadius: 2, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${fillPct}%`,
                      height: "100%",
                      background: c.runwayLabelTone === "warn"
                        ? "linear-gradient(90deg, var(--r-neg), var(--r-warn))"
                        : "var(--r-neg)",
                      borderRadius: 2,
                    }}
                  />
                </div>
                <div style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 10 }}>
                  {c.runwayMonths} / 24 mo
                </div>
              </div>
              <p style={{ color: "var(--r-ink-3)", marginTop: 12, fontSize: 12, lineHeight: 1.6 }}>{c.note}</p>
              <div style={{ paddingTop: 8 }}>
                <PdfCheckList items={[{ checked: false, body: <><strong>Action</strong> — {c.action}</>, meta: "P1" }]} />
              </div>
            </PdfCard>
          );
        })}

        <PdfSectionTitle variant="sm">Watch · 12–18개월</PdfSectionTitle>
        <div style={{ background: "var(--r-bg-soft)", borderRadius: 6, padding: 16, marginBottom: 14 }}>
          <PdfFlexBetween>
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: 1.5, textTransform: "uppercase", color: "var(--r-ink-4)" }}>
                {data.watch.ticker} · {data.watch.name}
              </div>
              <strong>{data.watch.runway}</strong>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--r-ink-3)" }}>{data.watch.cashBurnLine}</div>
          </PdfFlexBetween>
          <p style={{ color: "var(--r-ink-3)", marginTop: 8, fontSize: 11, lineHeight: 1.55 }}>{data.watch.note}</p>
        </div>

        <div style={{ marginTop: 18 }}>
          <PdfCallout label="CFO's Note">{data.cfoNote}</PdfCallout>
        </div>

        <PdfGovBlock />
        <PdfPageFooter left="Burn Rate · Premium · Not investment advice" right="Page 02" />
        <PdfDisclaimer cadence="monthly" />
      </PdfPage>
    </>
  );
}
