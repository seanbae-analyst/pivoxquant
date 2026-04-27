/**
 * Report 08 — DD Checklist (Pro · 2 pages · On Demand)
 *
 * Source: /design_handoff_pdf_reports/reports/08_dd_checklist.html
 *
 * Page 1: Cover headline + 4-up KPI (ticker / price / target size / DD score)
 *         + Sections A (Business Quality) / B (Financials) / C (Valuation) — 5 items each.
 * Page 2: Sections D (Risk) / E (Process) — 5 items each + thesis card +
 *         decision 3-up + pre-entry promise callout + sign row + governance + disclaimer.
 *
 * Compliance: Process audit / pre-entry checklist. No buy/sell/hold language.
 * "PROCEED / HOLD / REJECT" labels are checklist gates, not investment advice.
 * Cadence: ondemand (one-off pre-entry diligence).
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
  PdfCheckList,
  PdfCard,
  PdfCallout,
  PdfThreeCol,
  PdfSignRow,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
} from "../pdf-primitives";

type Tone = "pos" | "neg" | "warn";

interface DdItem {
  num: string;
  text: string;
  detail?: string;
  status: string;
  tone: Tone;
  checked?: boolean;
}

export interface DdChecklistData {
  asOf: string;
  ticker: string;
  company: string;
  price: { value: string; delta: string };
  targetSize: { value: string; detail: string };
  ddScore: { value: string; verdict: string };
  sectionA: DdItem[];
  sectionB: DdItem[];
  sectionC: DdItem[];
  sectionD: DdItem[];
  sectionE: DdItem[];
  thesis: string;
  decisionScore: string;
  promise: string;
}

const TONE_STYLE: Record<Tone, string | undefined> = {
  pos: "var(--r-pos)",
  neg: "var(--r-neg)",
  warn: "var(--r-warn)",
};

const DEFAULT: DdChecklistData = {
  asOf: "Apr 26, 2026 · DD-2026-04",
  ticker: "PLTR",
  company: "Palantir Technologies",
  price: { value: "$28.40", delta: "+1.2% · MTD +18%" },
  targetSize: { value: "3.5%", detail: "$43,500 / $1.24M NAV" },
  ddScore: { value: "21/25", verdict: "PROCEED" },
  sectionA: [
    { num: "A1", text: "Moat 정의", detail: "데이터 락인 + 정부/방산 레퍼런스 + 유틸리티", status: "YES", tone: "pos", checked: true },
    { num: "A2", text: "Unit Economics", detail: "고객당 ACV $4.2M, 갱신률 121%", status: "YES", tone: "pos", checked: true },
    { num: "A3", text: "TAM 성장 가시성", detail: "AIP 도입 가속, 5y CAGR > 25%", status: "YES", tone: "pos", checked: true },
    { num: "A4", text: "경영진 캐피털 알로케이션", detail: "자사주 매입 이력 짧음, 재투자 위주", status: "PARTIAL", tone: "warn" },
    { num: "A5", text: "경쟁 vs Snowflake/Databricks", detail: "다른 레이어. 직접 충돌 적음", status: "YES", tone: "pos", checked: true },
  ],
  sectionB: [
    { num: "B1", text: "FCF 양수, 4Q 연속", status: "YES", tone: "pos", checked: true },
    { num: "B2", text: "Net Cash > 0", detail: "$4.2B", status: "YES", tone: "pos", checked: true },
    { num: "B3", text: "Gross Margin > 70%", status: "YES · 81%", tone: "pos", checked: true },
    { num: "B4", text: "SBC %매출 < 15%", status: "NO · 24%", tone: "neg" },
    { num: "B5", text: "Rule of 40", detail: "성장 30% + 마진 21% = 51", status: "YES", tone: "pos", checked: true },
  ],
  sectionC: [
    { num: "C1", text: "베이스 케이스 IRR > 12%", detail: "14.8%", status: "YES", tone: "pos", checked: true },
    { num: "C2", text: "베어 시나리오 −20% < downside", detail: "−34%", status: "NO", tone: "neg" },
    { num: "C3", text: "5y FCF Yield > 4%", detail: "5.2%", status: "YES", tone: "pos", checked: true },
    { num: "C4", text: "멀티플 vs 자기 5y avg", detail: "−18% 디스카운트", status: "YES", tone: "pos", checked: true },
    { num: "C5", text: "경쟁사 대비 R/G 비율", detail: "top decile", status: "YES", tone: "pos", checked: true },
  ],
  sectionD: [
    { num: "D1", text: "Single customer < 20%", status: "YES · 12%", tone: "pos", checked: true },
    { num: "D2", text: "정치/규제 리스크", detail: "정부 의존도 45%", status: "FLAG", tone: "warn" },
    { num: "D3", text: "Liquidity", detail: "ADV $800M, 슬리피지 무시", status: "YES", tone: "pos", checked: true },
    { num: "D4", text: "30d Volatility < 60%", detail: "48%", status: "YES", tone: "pos", checked: true },
    { num: "D5", text: "Short interest < 15%", detail: "6.2%", status: "YES", tone: "pos", checked: true },
  ],
  sectionE: [
    { num: "E1", text: "가설 메모 작성", detail: "9/12", status: "YES", tone: "pos", checked: true },
    { num: "E2", text: "반대 의견 검토", detail: "베어 리포트 3편", status: "YES", tone: "pos", checked: true },
    { num: "E3", text: "포지션 사이즈 룰", detail: "첫 진입 1.5%, max 3.5%", status: "YES", tone: "pos", checked: true },
    { num: "E4", text: "Exit 조건 명시", detail: "가설 깨지는 신호 3가지", status: "YES", tone: "pos", checked: true },
    { num: "E5", text: "한도 영향 시뮬", detail: "Tech 비중 43% → 한도 위반", status: "CONFLICT", tone: "warn" },
  ],
  thesis:
    "Palantir AIP는 \"데이터 통합 + 의사결정 자동화\"의 차세대 OS. 매출 25% 성장 + FCF 마진 30%대 + 갱신률 121%가 동시에 나오는 SaaS는 톱 5%. 베어는 SBC와 정부 의존, 베이스는 상업 부문 50% 돌파. 5y IRR 14.8% 베이스, 22% 불, −34% 베어. 단, 진입 시 Tech 한도 위반 → META 1.2%p 정리 동시 실행 조건부.",
  decisionScore: "21/25",
  promise:
    "다음 분기 하나의 약속 — 모든 신규 진입 전 가설 메모 작성, 예외 없음. 가설이 깨질 신호: ① 갱신률 < 110%, ② 정부 매출 비중 > 55%, ③ FCF 마진 < 20%. 둘 이상 발생 시 30일 내 청산.",
};

function toCheckItems(items: DdItem[]) {
  return items.map((it) => ({
    checked: !!it.checked,
    body: (
      <>
        <strong>
          {it.num} · {it.text}
        </strong>
        {it.detail ? <> — {it.detail}</> : null}
      </>
    ),
    meta: <span style={{ color: TONE_STYLE[it.tone] }}>{it.status}</span>,
  }));
}

export function DdChecklist({ data = DEFAULT }: { data?: DdChecklistData }) {
  return (
    <>
      {/* ═══════ PAGE 1 ═══════ */}
      <PdfPage>
        <PdfHeader tier="pro" title="DD CHECKLIST" meta={`${data.asOf} · 01/02`} />
        <PdfGoldRule />

        <PdfEyebrow>Due Diligence · Pre-Entry</PdfEyebrow>
        <PdfCoverTitle size={42}>
          {data.ticker}—<em>before you enter</em>
          <br />
          25 questions. No answer, no entry.
        </PdfCoverTitle>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            kpis={[
              {
                label: "Ticker",
                value: data.ticker,
                delta: data.company,
                small: true,
              },
              {
                label: "Last Price",
                value: data.price.value,
                delta: data.price.delta,
                deltaTone: "pos",
              },
              {
                label: "Target Size",
                value: data.targetSize.value,
                delta: data.targetSize.detail,
              },
              {
                label: "DD Score",
                value: data.ddScore.value,
                delta: data.ddScore.verdict,
                deltaTone: "pos",
              },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Section A · Business Quality (5)</PdfSectionTitle>
        <PdfCheckList items={toCheckItems(data.sectionA)} />

        <PdfSectionTitle variant="sm">Section B · Financials (5)</PdfSectionTitle>
        <PdfCheckList items={toCheckItems(data.sectionB)} />

        <PdfSectionTitle variant="sm">Section C · Valuation (5)</PdfSectionTitle>
        <PdfCheckList items={toCheckItems(data.sectionC)} />

        <PdfPageFooter left="DD Checklist · Pro" right="Page 01" />
        <PdfDisclaimer cadence="ondemand" />
      </PdfPage>

      {/* ═══════ PAGE 2 ═══════ */}
      <PdfPage>
        <PdfHeader tier="pro" title="DD CHECKLIST" meta={`${data.asOf} · 02/02`} />
        <PdfGoldRule />

        <PdfSectionTitle variant="sm">Section D · Risk (5)</PdfSectionTitle>
        <PdfCheckList items={toCheckItems(data.sectionD)} />

        <PdfSectionTitle variant="sm">Section E · Process (5)</PdfSectionTitle>
        <PdfCheckList items={toCheckItems(data.sectionE)} />

        <PdfSectionTitle variant="sm">Thesis · 한 문단</PdfSectionTitle>
        <PdfCard>
          <p
            style={{
              fontSize: 13,
              lineHeight: 1.7,
              color: "var(--r-ink-2)",
              fontFamily: "var(--font-serif)",
            }}
          >
            {data.thesis}
          </p>
        </PdfCard>

        <PdfSectionTitle variant="sm">Decision · 진입 / 보류 / 기각</PdfSectionTitle>
        <PdfThreeCol>
          <PdfCard soft>
            <div
              style={{
                textAlign: "center",
                padding: 8,
                border: "2px solid var(--r-ink)",
                borderRadius: 4,
              }}
            >
              <div className="pq-pdf-kpi-lbl">PROCEED</div>
              <div
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 34,
                  fontWeight: 500,
                  margin: "8px 0",
                }}
              >
                {data.decisionScore}
              </div>
              <div style={{ fontSize: 10, color: "var(--r-ink-3)" }}>
                진입 조건 충족
              </div>
            </div>
          </PdfCard>
          <PdfCard soft>
            <div style={{ textAlign: "center", padding: 8, opacity: 0.4 }}>
              <div className="pq-pdf-kpi-lbl">WAIT</div>
              <div
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 34,
                  fontWeight: 500,
                  margin: "8px 0",
                }}
              >
                15–20
              </div>
              <div style={{ fontSize: 10, color: "var(--r-ink-3)" }}>
                추가 정보 필요
              </div>
            </div>
          </PdfCard>
          <PdfCard soft>
            <div style={{ textAlign: "center", padding: 8, opacity: 0.4 }}>
              <div className="pq-pdf-kpi-lbl">REJECT</div>
              <div
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 34,
                  fontWeight: 500,
                  margin: "8px 0",
                }}
              >
                &lt;15
              </div>
              <div style={{ fontSize: 10, color: "var(--r-ink-3)" }}>기각</div>
            </div>
          </PdfCard>
        </PdfThreeCol>

        <div style={{ marginTop: 18 }}>
          <PdfCallout label="Pre-Entry Promise">{data.promise}</PdfCallout>
        </div>

        <PdfSignRow
          left="분석자 · _____________"
          right={`결정 일자 · ${data.asOf.split(" · ")[0]}`}
        />

        <PdfGovBlock />

        <PdfPageFooter
          left="DD Checklist · Pro · Process audit · Not investment advice"
          right="Page 02"
        />
        <PdfDisclaimer cadence="ondemand" />
      </PdfPage>
    </>
  );
}
