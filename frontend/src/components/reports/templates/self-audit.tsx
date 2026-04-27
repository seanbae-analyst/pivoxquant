/**
 * Report 07 — Self Audit (Pro · 2 pages · On Demand)
 *
 * Source: /design_handoff_pdf_reports/reports/07_self_audit.html
 *
 * Page 1: Cover headline + 4-up KPI (audit grade) + 8-rule compliance checklist
 *         + "what you said vs what you did" consistency table.
 * Page 2: Bias heatmap (alloc bars) + top-flag card + 3 audit findings cards
 *         + auditor's note + sign row + governance + disclaimer.
 *
 * Compliance: All findings are process audits, not investment advice.
 * No buy/sell/hold language. Cadence: ondemand (one-off).
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
  PdfTable,
  PdfTwoCol,
  PdfCard,
  PdfCallout,
  PdfFlexBetween,
  PdfDivider,
  PdfSignRow,
  PdfGovBlock,
  PdfPageFooter,
  PdfDisclaimer,
} from "../pdf-primitives";

export interface SelfAuditData {
  asOf: string; // "Apr 26, 2026 · SA-2026-04"
  intro: string;
  kpis: {
    score: { value: string; prev: string };
    rulesFollowed: { value: string; pct: string };
    decisionsLogged: { value: string; pct: string };
    biasFlags: { value: string; target: string };
  };
  rules: { num: string; text: string; status: string; statusTone: "pos" | "neg" | "warn" }[];
  consistency: { said: string; did: string; match: "✓" | "✗" }[];
  biasHeat: { name: string; pct: number; pctDisplay: string; tone: "pos" | "neg" | "neutral"; flat?: boolean }[];
  topFlag: { tag: string; title: string; body: string; counterRule: string };
  findings: {
    code: string;
    severity: "MAJOR" | "MINOR" | "OBSERVATION";
    due: string;
    dueTone?: "neg" | "neutral";
    title: string;
    body: string;
  }[];
  auditorNote: string;
}

const DEFAULT: SelfAuditData = {
  asOf: "Apr 26, 2026 · SA-2026-04",
  intro:
    "Every decision of the last 30 days, reviewed as an outside auditor would. Where rules broke, and why.",
  kpis: {
    score: { value: "B+", prev: "prev A−" },
    rulesFollowed: { value: "14/17", pct: "82%" },
    decisionsLogged: { value: "12/12", pct: "100%" },
    biasFlags: { value: "3", target: "target ≤ 2" },
  },
  rules: [
    { num: "R1", text: "모든 신규 진입 전 가설 메모 작성", status: "PASS", statusTone: "pos" },
    { num: "R2", text: "단일 종목 12% 한도", status: "PASS", statusTone: "pos" },
    { num: "R3", text: "단일 섹터 35% 한도 — Tech 42% 위반 (08/14 ~ 현재)", status: "FAIL · 12d", statusTone: "neg" },
    { num: "R4", text: "−15% 자동 손절 트리거", status: "PASS", statusTone: "pos" },
    { num: "R5", text: "어닝 직전 24h 신규 진입 금지 — 어닝 6h 전 추가", status: "FAIL · 1×", statusTone: "neg" },
    { num: "R6", text: "주간 리밸런스 화/금에만", status: "PASS", statusTone: "pos" },
    { num: "R7", text: "모든 매도 전 사후 메모 — 2건 누락", status: "FAIL · 2×", statusTone: "neg" },
    { num: "R8", text: "현금 비중 5–15% 유지", status: "PASS · 8.2%", statusTone: "pos" },
  ],
  consistency: [
    { said: '"Tech 비중 줄인다" (8/01 메모)', did: "Tech 42% → 44% (+2%p)", match: "✗" },
    { said: '"FX 헤지 25% 추가" (8/15 메모)', did: "미실행", match: "✗" },
    { said: '"평단 +3% 추가" (9/12 메모)', did: "9/18 +3.5%p 실행", match: "✓" },
    { said: '"수익률 추격 안 함" (지속 룰)', did: "단기 모멘텀 매수 발생", match: "✗" },
  ],
  biasHeat: [
    { name: "Confirmation", pct: 32, pctDisplay: "3/12", tone: "neutral" },
    { name: "Recency", pct: 58, pctDisplay: "7/12", tone: "neg" },
    { name: "Anchoring", pct: 42, pctDisplay: "5/12", tone: "neutral" },
    { name: "Loss Aversion", pct: 16, pctDisplay: "2/12", tone: "pos", flat: true },
    { name: "Overconfidence", pct: 38, pctDisplay: "4/12", tone: "neutral" },
    { name: "Herd", pct: 24, pctDisplay: "3/12", tone: "neutral", flat: true },
  ],
  topFlag: {
    tag: "RECENCY · 7건",
    title: "최근 1주 사건에 과반응",
    body: "30일 중 7건의 결정이 직전 7일 내 사건 트리거. 평균 보유 기간 18일 → 9일로 단축. 거래 비용·세금 누적 −0.42%p.",
    counterRule:
      'Counter-rule 제안: 신규 진입 전 "이 결정이 6개월 전에도 유효했나?" 자문.',
  },
  findings: [
    {
      code: "F1",
      severity: "MAJOR",
      due: "due in 7 days",
      dueTone: "neg",
      title: "Tech 섹터 42% → 35% 복귀",
      body: "R3 위반 12일째. 한도 복귀 일정과 매도 종목 명시. 다음 리밸런스에 −7%p.",
    },
    {
      code: "F2",
      severity: "MINOR",
      due: "due in 14 days",
      title: "매도 사후 메모 누락 2건 보충",
      body: "R7. 사후 메모 양식대로 작성, 재발 방지 룰 검토.",
    },
    {
      code: "F3",
      severity: "OBSERVATION",
      due: "advisory",
      dueTone: "neutral",
      title: "Recency 편향 패턴화",
      body: "4분기 연속 Top 1 편향. 룰 추가 제안: 신규 진입 24h 쿨오프, 직전 7일 내 사건 의존도 메모 명시.",
    },
  ],
  auditorNote:
    '룰 위반 자체보다 "위반을 어떻게 알아챘나"가 더 중요. 이번 분기는 자가 신고율 100%. 시스템은 작동 중.',
};

const TONE_STYLE: Record<"pos" | "neg" | "warn" | "neutral", string | undefined> = {
  pos: "var(--r-pos)",
  neg: "var(--r-neg)",
  warn: "var(--r-warn)",
  neutral: undefined,
};

export function SelfAudit({ data = DEFAULT }: { data?: SelfAuditData }) {
  return (
    <>
      {/* ═══════ PAGE 1 ═══════ */}
      <PdfPage>
        <PdfHeader tier="pro" title="SELF AUDIT" meta={data.asOf} />
        <PdfGoldRule />

        <PdfEyebrow>Self Audit · On Demand</PdfEyebrow>
        <PdfCoverTitle size={42}>
          Are your decisions <em>consistent</em>?—<br />
          you, seen by the auditor.
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
          {data.intro}
        </p>

        <div style={{ marginTop: 24 }}>
          <PdfKpiRow
            kpis={[
              { label: "Audit Score", value: data.kpis.score.value, delta: data.kpis.score.prev },
              { label: "Rules Followed", value: data.kpis.rulesFollowed.value, delta: data.kpis.rulesFollowed.pct, deltaTone: "warn" },
              { label: "Decisions Logged", value: data.kpis.decisionsLogged.value, delta: data.kpis.decisionsLogged.pct, deltaTone: "pos" },
              { label: "Bias Flags", value: data.kpis.biasFlags.value, delta: data.kpis.biasFlags.target, deltaTone: "neg" },
            ]}
          />
        </div>

        <PdfSectionTitle variant="sm">Rule Compliance · 룰 준수 점검</PdfSectionTitle>
        <PdfCheckList
          items={data.rules.map((r) => ({
            checked: r.statusTone === "pos",
            body: (
              <>
                <strong>{r.num} · {r.text.split(" — ")[0]}</strong>
                {r.text.includes(" — ") && <> — {r.text.split(" — ").slice(1).join(" — ")}</>}
              </>
            ),
            meta: <span style={{ color: TONE_STYLE[r.statusTone] }}>{r.status}</span>,
          }))}
        />

        <PdfSectionTitle variant="sm">Consistency Check · 말과 행동</PdfSectionTitle>
        <PdfTable>
          <thead>
            <tr>
              <th>What You Said</th>
              <th>What You Did</th>
              <th className="right">Match</th>
            </tr>
          </thead>
          <tbody>
            {data.consistency.map((c, i) => (
              <tr key={i}>
                <td>{c.said}</td>
                <td>{c.did}</td>
                <td className={`right ${c.match === "✓" ? "pos" : "neg"}`}>{c.match}</td>
              </tr>
            ))}
          </tbody>
        </PdfTable>

        <PdfPageFooter left="Self Audit · Pro" right="Page 01" />
        <PdfDisclaimer cadence="ondemand" />
      </PdfPage>

      {/* ═══════ PAGE 2 ═══════ */}
      <PdfPage>
        <PdfHeader tier="pro" title="SELF AUDIT" meta={`${data.asOf} · 02/02`} />
        <PdfGoldRule />

        <PdfSectionTitle variant="sm">Bias Heatmap · 편향 분포</PdfSectionTitle>

        <PdfTwoCol>
          <div>
            {data.biasHeat.map((b, i) => {
              const pctClamped = Math.max(0, Math.min(100, b.pct));
              return (
                <div key={i} className="pq-pdf-alloc-row">
                  <div><strong>{b.name}</strong></div>
                  <div className={`pq-pdf-alloc-bar${b.flat ? " flat" : ""}`}>
                    <i style={{ width: `${pctClamped}%` }} />
                  </div>
                  <div className="pq-pdf-alloc-pct" style={{ color: TONE_STYLE[b.tone] }}>
                    {b.pctDisplay}
                  </div>
                </div>
              );
            })}
          </div>
          <div>
            <div className="pq-pdf-col-title">Top Flag · 가장 큰 패턴</div>
            <PdfCard soft>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--r-ink-3)",
                  letterSpacing: "1.5px",
                  textTransform: "uppercase",
                }}
              >
                {data.topFlag.tag}
              </div>
              <h3
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 22,
                  margin: "8px 0",
                  fontWeight: 500,
                }}
              >
                {data.topFlag.title}
              </h3>
              <p
                style={{
                  fontSize: 12,
                  lineHeight: 1.6,
                  color: "var(--r-ink-2)",
                }}
              >
                {data.topFlag.body}
              </p>
              <PdfDivider />
              <div style={{ fontSize: 10, color: "var(--r-ink-3)" }}>
                <strong>{data.topFlag.counterRule}</strong>
              </div>
            </PdfCard>
          </div>
        </PdfTwoCol>

        <PdfSectionTitle variant="sm">Audit Findings · 시정 사항</PdfSectionTitle>

        {data.findings.map((f, i) => (
          <PdfCard key={i}>
            <PdfFlexBetween>
              <div className="pq-pdf-kpi-lbl">
                {f.code} · {f.severity}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color:
                    f.dueTone === "neg"
                      ? "var(--r-neg)"
                      : f.dueTone === "neutral"
                        ? "var(--r-ink-4)"
                        : undefined,
                }}
              >
                {f.due}
              </div>
            </PdfFlexBetween>
            <h3
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 18,
                margin: "8px 0 6px",
                fontWeight: 500,
              }}
            >
              {f.title}
            </h3>
            <p
              style={{
                fontSize: 12,
                lineHeight: 1.6,
                color: "var(--r-ink-3)",
              }}
            >
              {f.body}
            </p>
          </PdfCard>
        ))}

        <div style={{ marginTop: 18 }}>
          <PdfCallout flat label="Auditor's Note">
            {data.auditorNote}
          </PdfCallout>
        </div>

        <PdfSignRow
          left="감사관 (Self) · _____________"
          right="감사 일자 · _____________"
        />

        <PdfGovBlock />

        <PdfPageFooter
          left="Self Audit · Pro · Not investment advice"
          right="Page 02"
        />
        <PdfDisclaimer cadence="ondemand" />
      </PdfPage>
    </>
  );
}
